from __future__ import annotations

import json
import re
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from ipo_financial_agent.config import Settings

T = TypeVar("T", bound=BaseModel)


class LLMConfigurationError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


class LLMTruncatedError(LLMResponseError):
    pass


def _estimate_tokens(*parts: str) -> int:
    """Conservative tokenizer-free estimate for mixed Chinese/English prompts."""
    units = 0.0
    for part in parts:
        for char in part:
            units += 1.0 if ord(char) > 127 else 0.25
    return max(1, int(units) + 256)


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < 0 or end <= start:
            raise LLMResponseError("LLM response does not contain a JSON object")
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"Invalid JSON from LLM: {exc}") from exc
    if not isinstance(value, dict):
        raise LLMResponseError("LLM JSON response must be an object")
    return value


class OpenAICompatibleClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.llm_configured:
            raise LLMConfigurationError(
                "LLM is not configured. Set OPENAI_COMPATIBLE_API_KEY and "
                "OPENAI_COMPATIBLE_MODEL in .env."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMConfigurationError(
                "The 'openai' package is required for LLM mode. Run: pip install -e ."
            ) from exc

        self.settings = settings
        kwargs: dict[str, Any] = {
            "api_key": settings.llm_api_key,
            "timeout": settings.llm_timeout_seconds,
        }
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        self.client = OpenAI(**kwargs)

    def _fit_output_budget(self, *, max_tokens: int, parts: list[str]) -> int:
        estimated_input = _estimate_tokens(*parts)
        available = (
            self.settings.llm_context_window_tokens
            - self.settings.llm_context_safety_tokens
            - estimated_input
        )
        if available < 256:
            raise LLMTruncatedError(
                "LLM context budget exceeded before request: "
                f"estimated_input_tokens={estimated_input}, "
                f"context_window_tokens={self.settings.llm_context_window_tokens}, "
                f"reserved_tokens={self.settings.llm_context_safety_tokens}. "
                "Reduce the input chunk or increase LLM_CONTEXT_WINDOW_TOKENS."
            )
        return min(max_tokens, available)

    def _with_retry(self, operation):
        last_error: Exception | None = None
        for attempt in range(1, self.settings.llm_max_retries + 1):
            try:
                return operation()
            except LLMTruncatedError:
                # 截断属于确定性的长度问题，交给上层拆分页面。
                raise
            except Exception as exc:  # API SDKs expose several provider-specific errors.
                last_error = exc
                if attempt >= self.settings.llm_max_retries:
                    raise
                time.sleep(min(2 ** (attempt - 1), 12))
        raise RuntimeError(str(last_error))

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int = 5000,
    ) -> T:
        schema = response_model.model_json_schema()
        schema_json = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))

        prompt = (
            f"{user_prompt}\n\n"
            "请严格按照接口指定的 JSON Schema 返回一个 JSON 对象。"
            "不得输出 Markdown、解释文字或思考过程。"
        )
        fitted_max_tokens = self._fit_output_budget(
            max_tokens=max_tokens,
            parts=[system_prompt, prompt, schema_json],
        )

        def request_and_validate() -> T:
            response = self.client.chat.completions.create(
                model=str(self.settings.llm_model),
                temperature=0.0,
                top_p=1.0,
                max_tokens=fitted_max_tokens,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_model.__name__,
                        "strict": True,
                        "schema": schema,
                    },
                },
                extra_body={
                    "chat_template_kwargs": {
                        "enable_thinking": False,
                    },
                },
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )

            choice = response.choices[0]
            content = choice.message.content or ""

            if choice.finish_reason == "length":
                completion_tokens = (
                    response.usage.completion_tokens
                    if response.usage is not None
                    else None
                )

                raise LLMTruncatedError(
                    "LLM structured output was truncated: "
                    f"completion_tokens={completion_tokens}, "
                    f"max_tokens={fitted_max_tokens}, "
                    f"output_chars={len(content)}"
                )

            payload = _extract_json_object(content)

            try:
                return response_model.model_validate(payload)
            except ValidationError as exc:
                raise LLMResponseError(
                    f"LLM JSON failed schema validation: {exc}"
                ) from exc

        return self._with_retry(request_and_validate)

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 6000,
    ) -> str:
        fitted_max_tokens = self._fit_output_budget(
            max_tokens=max_tokens,
            parts=[system_prompt, user_prompt],
        )

        def request():
            return self.client.chat.completions.create(
                model=str(self.settings.llm_model),
                temperature=max(0.1, min(self.settings.llm_temperature, 0.8)),
                top_p=0.8,
                max_tokens=fitted_max_tokens,
                extra_body={
                    "top_k": 20,
                    "chat_template_kwargs": {
                        "enable_thinking": False,
                    },
                },
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

        response = self._with_retry(request)
        return (response.choices[0].message.content or "").strip()

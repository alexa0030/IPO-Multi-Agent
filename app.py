from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st

from ipo_financial_agent.config import get_settings
from ipo_financial_agent.pipeline import IPOFinancialPipeline
from ipo_financial_agent.agents.team import AGENT_TEAM

st.set_page_config(page_title="HK IPO Due Diligence Team", layout="wide")
st.title("港股 IPO 多 Agent 尽调助手")
st.caption("输入公司名称与招股书，模拟投资团队完成公司、行业、财务、风控、质疑、写作与终审。")

with st.expander("查看虚拟投资团队与协作流程", expanded=False):
    st.dataframe(
        [
            {
                "Agent": item["name"],
                "职责": item["role"],
                "阶段": item["stage"],
                "工具": " / ".join(item["tools"]),
                "输出": item["output"],
            }
            for item in AGENT_TEAM
        ],
        use_container_width=True,
        hide_index=True,
    )

company = st.text_input("公司名称")
uploaded = st.file_uploader("上传招股书 PDF", type=["pdf"])
llm_mode = st.selectbox("大模型模式", ["auto", "on", "off"], index=0)
search_mode = st.selectbox(
    "公开信息检索",
    ["auto", "ddgs", "off"],
    index=0,
    help="auto 优先使用已配置的 Tavily；ddgs 无需 API Key，但受网络出口影响；off 仅分析招股书。",
)
search_max_queries = st.slider("本轮最大搜索主题数", 1, 12, 8)

if st.button("开始处理", type="primary", disabled=uploaded is None or not company.strip()):
    os.environ["IPO_SEARCH_PROVIDER"] = search_mode
    os.environ["IPO_SEARCH_MAX_QUERIES"] = str(search_max_queries)
    settings = get_settings(ROOT)
    pdf_bytes = uploaded.getvalue()
    safe_name = Path(uploaded.name).name
    suffix = Path(safe_name).suffix.lower() or ".pdf"
    stem = Path(safe_name).stem
    digest = hashlib.sha256(pdf_bytes).hexdigest()[:10]
    pdf_path = settings.upload_dir / f"{stem}_{digest}{suffix}"
    if not pdf_path.exists():
        pdf_path.write_bytes(pdf_bytes)
    with st.spinner("正在解析与分析……"):
        artifacts = IPOFinancialPipeline(settings).run(
            pdf_path=pdf_path,
            company=company.strip(),
            llm_mode=llm_mode,
        )
    st.success("处理完成")
    review_col, run_col = st.columns(2)
    with review_col:
        review_score = artifacts.metadata.get("report_review_score")
        st.metric("终审评分", review_score if review_score is not None else "未评分")
        st.metric(
            "终审结果",
            "通过" if artifacts.metadata.get("report_review_passed") else "需复核",
        )
    with run_col:
        st.metric("Agent 消息", artifacts.metadata.get("agent_message_count", 0))
        st.metric("证据条数", artifacts.metadata.get("research_evidence_count", 0))

    with st.expander("Agent 执行轨迹", expanded=True):
        messages_path = Path(artifacts.metadata.get("agent_messages_json", ""))
        if messages_path.is_file():
            messages = json.loads(messages_path.read_text(encoding="utf-8"))
            for item in messages:
                st.markdown(
                    f"**{item.get('sender', 'Agent')} → {item.get('receiver', 'all')}** "
                    f"`{item.get('message_type', 'info')}`  \n{item.get('content', '')}"
                )

    with st.expander("终审详情", expanded=False):
        review_path = Path(artifacts.metadata.get("report_review_json", ""))
        if review_path.is_file():
            st.json(json.loads(review_path.read_text(encoding="utf-8")))

    with st.expander("全部运行元数据", expanded=False):
        st.json(artifacts.metadata)
    excel_path = Path(artifacts.excel_path)
    final_report = artifacts.metadata.get("final_report_path") or artifacts.report_path
    report_path = Path(final_report) if final_report else None
    st.download_button(
        "下载 Excel 底稿",
        data=excel_path.read_bytes(),
        file_name=excel_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    if report_path and report_path.is_file():
        st.download_button(
            "下载 Markdown 报告",
            data=report_path.read_bytes(),
            file_name=report_path.name,
            mime="text/markdown",
        )
        st.markdown(report_path.read_text(encoding="utf-8"))

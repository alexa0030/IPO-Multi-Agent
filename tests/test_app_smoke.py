from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_demo_dashboard_renders_without_pdf_or_model_configuration():
    app = Path(__file__).resolve().parents[1] / "app.py"

    result = AppTest.from_file(str(app), default_timeout=15).run()

    assert not result.exception
    assert any("港股 IPO 尽调" in heading.value for heading in result.get("markdown"))
    assert result.radio[0].value == "演示总览"
    assert len(result.tabs) == 4


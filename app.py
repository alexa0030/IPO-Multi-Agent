from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st

from ipo_financial_agent.config import get_settings
from ipo_financial_agent.pipeline import IPOFinancialPipeline

st.set_page_config(page_title="IPO Financial Agent", layout="wide")
st.title("港股 IPO 招股书财务分析")

company = st.text_input("公司名称")
uploaded = st.file_uploader("上传招股书 PDF", type=["pdf"])
llm_mode = st.selectbox("大模型模式", ["auto", "on", "off"], index=0)

if st.button("开始处理", type="primary", disabled=uploaded is None or not company.strip()):
    settings = get_settings(ROOT)
    pdf_path = settings.upload_dir / uploaded.name
    pdf_path.write_bytes(uploaded.getvalue())
    with st.spinner("正在解析与分析……"):
        artifacts = IPOFinancialPipeline(settings).run(
            pdf_path=pdf_path,
            company=company.strip(),
            llm_mode=llm_mode,
        )
    st.success("处理完成")
    st.json(artifacts.metadata)
    excel_path = Path(artifacts.excel_path)
    report_path = Path(artifacts.report_path) if artifacts.report_path else None
    st.download_button(
        "下载 Excel 底稿",
        data=excel_path.read_bytes(),
        file_name=excel_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    if report_path and report_path.exists():
        st.download_button(
            "下载 Markdown 报告",
            data=report_path.read_bytes(),
            file_name=report_path.name,
            mime="text/markdown",
        )
        st.markdown(report_path.read_text(encoding="utf-8"))

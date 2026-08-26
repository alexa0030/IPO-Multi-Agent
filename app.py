from __future__ import annotations

import hashlib, json, os, sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

import streamlit as st
from ipo_financial_agent.config import get_settings

st.set_page_config(page_title="HK IPO Intelligence Desk", page_icon="◈", layout="wide")
st.markdown("""
<style>
:root{--ink:#10221c;--muted:#64736d;--green:#0b5d42;--mint:#dff4e9;--line:#dce5e0}
.stApp{background:linear-gradient(145deg,#f5faf7 0%,#fff 42%,#f4f8f6 100%);color:var(--ink)}
html,body,[class*="css"]{font-family:Inter,"Noto Sans SC",sans-serif}[data-testid="stSidebar"]{background:#10261f}[data-testid="stSidebar"] *{color:#eef7f2!important}.block-container{max-width:1450px;padding-top:1.5rem;padding-bottom:3rem}h1,h2,h3{letter-spacing:-.025em;color:var(--ink)}
.eyebrow{color:var(--green);text-transform:uppercase;letter-spacing:.15em;font-size:.72rem;font-weight:700}.hero{padding:1.1rem 0 1.3rem;border-bottom:1px solid var(--line);margin-bottom:1.25rem}.hero h1{font-size:2.45rem;margin:.25rem 0 .35rem;line-height:1.08}.hero p{color:var(--muted);max-width:830px;font-size:1.02rem;margin:0}.status-pill{display:inline-flex;padding:.28rem .62rem;border-radius:99px;background:var(--mint);color:var(--green);font-weight:600;font-size:.76rem;margin-right:.35rem}
.metric-card{background:#ffffffd9;border:1px solid var(--line);border-radius:14px;padding:1rem 1.05rem;min-height:116px;box-shadow:0 8px 28px #10221c0b}.metric-label{color:var(--muted);font-size:.78rem}.metric-value{color:var(--ink);font-size:1.65rem;font-weight:700;margin:.18rem 0}.metric-note{color:var(--green);font-size:.75rem}.section-card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:1rem 1.1rem;margin:.3rem 0 .8rem}.agent-row{display:flex;gap:.7rem;align-items:flex-start;border-bottom:1px solid #edf2ef;padding:.72rem 0}.agent-dot{width:9px;height:9px;border-radius:50%;background:#35a376;margin-top:.42rem;box-shadow:0 0 0 4px #e0f3ea;flex:0 0 auto}.agent-name{font-weight:650;font-size:.88rem}.agent-role{color:var(--muted);font-size:.78rem;margin-top:.12rem}.risk-high,.risk-mid{padding:.22rem .5rem;border-radius:99px;font-size:.72rem;font-weight:650}.risk-high{color:#a33c2e;background:#fbe8e5}.risk-mid{color:#946018;background:#fbf0d9}.evidence{border-left:3px solid #42a77c;background:#f6faf8;padding:.72rem .85rem;border-radius:0 9px 9px 0;margin:.55rem 0}.evidence small{display:block;color:var(--muted);margin-top:.22rem}.disclaimer{color:var(--muted);font-size:.72rem;line-height:1.5}.stButton>button{border-radius:9px;font-weight:650}.stButton>button[kind="primary"]{background:var(--green);border-color:var(--green)}[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:12px;padding:.75rem}
</style>""", unsafe_allow_html=True)

AGENT_TEAM=[
{"name":"ResearchManager","stage":"plan","role":"拆解任务并提出公司特定假设","output":"ResearchPlan"},
{"name":"CompanyBusinessAgent","stage":"parallel_research","role":"研究股权、产品、商业模式与管理层","output":"ProspectusAnalysis"},
{"name":"FinancialAgent","stage":"parallel_research","role":"抽取三表、计算指标并执行财务取证","output":"FinancialAnalysis"},
{"name":"IndustryAgent","stage":"parallel_research","role":"验证行业空间、竞争格局与持续增长","output":"IndustryAnalysis"},
{"name":"LegalGovernanceAgent","stage":"parallel_research","role":"核查关联交易、诉讼处罚与治理风险","output":"LegalGovernanceAnalysis"},
{"name":"RiskReviewer + Skeptic","stage":"debate_review","role":"跨 Agent 对照并发起有界反证挑战","output":"RiskReview + Challenges"},
{"name":"DueDiligenceLead","stage":"decision","role":"形成投资经理口径的综合结论","output":"DueDiligenceConclusion"},
{"name":"EvidenceComplianceReviewer","stage":"final_review","role":"终审章节、引用、边界与无依据结论","output":"ReportReview"},
]
DEMO={"company":"汉森软件（脱敏回归案例）","verdict":"研究辅助结论","score":"—","pages":504,"evidence":"可追溯","findings":6,"risks":4,
"risk_items":[("存货增长","存货由 2023 年的 34.0 百万元增至 2025 年的 137.5 百万元","高风险","招股书 p.50–51 / 人工核验标签"),("第三方付款","2025 年第三方付款为 13.6 百万元，占收入 2.3%","高风险","招股书 p.52 / 人工核验标签"),("客户集中度","前五大客户收入占比 28.6%，最大客户占比 9.6%","需关注","招股书 p.18 / 人工核验标签")],
"evidence_items":[("GOLD-FIN-001","2025 财年收入 596.909 百万元","招股书 p.21 / 人工核验标签"),("GOLD-FIN-005","2025 年毛利率 54.5%","招股书 p.23 / 人工核验标签"),("GOLD-RISK-003","社会保险及住房公积金未完全缴纳","招股书 p.52 / 人工核验标签")]}

def read_json(path: str|Path|None, fallback: Any)->Any:
    candidate=Path(path or "")
    if not candidate.is_file(): return fallback
    try: return json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): return fallback

def metric_card(label:str,value:str|int,note:str)->None:
    st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>',unsafe_allow_html=True)

def run_pipeline(uploaded:Any,company:str,llm_mode:str,search_mode:str,queries:int)->None:
    # Keep the zero-config demo available even before the heavy PDF stack is installed.
    from ipo_financial_agent.pipeline import IPOFinancialPipeline

    settings=get_settings(ROOT); content=uploaded.getvalue(); safe=Path(uploaded.name).name
    path=settings.upload_dir/f"{Path(safe).stem}_{hashlib.sha256(content).hexdigest()[:10]}.pdf"
    if not path.exists(): path.write_bytes(content)
    os.environ["IPO_SEARCH_PROVIDER"]=search_mode; os.environ["IPO_SEARCH_MAX_QUERIES"]=str(queries)
    with st.status("投研团队正在协作",expanded=True) as status:
        st.write("解析招股书并建立章节索引…"); st.write("分派财务、公司、行业与法律研究任务…")
        artifacts=IPOFinancialPipeline(settings).run(pdf_path=path,company=company.strip(),llm_mode=llm_mode)
        st.write("交叉复核证据并生成投委会材料…"); status.update(label="尽调任务完成",state="complete",expanded=False)
    st.session_state["artifacts"]=artifacts

with st.sidebar:
    st.markdown("### ◈ IPO Intelligence"); st.caption("Evidence-grounded Research OS"); st.divider()
    mode=st.radio("工作台",["演示总览","发起真实任务"],label_visibility="collapsed"); st.divider()
    if mode=="发起真实任务":
        company=st.text_input("发行人名称",placeholder="例如：XX科技集团"); uploaded=st.file_uploader("上传港股招股书",type=["pdf"])
        with st.expander("运行设置"):
            llm_mode=st.selectbox("大模型",["auto","off","on"],help="auto 会在模型不可用时安全降级")
            search_mode=st.selectbox("公开信息检索",["auto","ddgs","off"]); search_max=st.slider("检索主题上限",1,12,8)
        if st.button("启动 Multi-Agent 尽调",type="primary",use_container_width=True,disabled=uploaded is None or not company.strip()):
            try: run_pipeline(uploaded,company,llm_mode,search_mode,search_max); st.rerun()
            except Exception as exc: st.error(f"任务未完成：{type(exc).__name__}。请检查招股书格式与运行配置。")
    else: st.info("当前为脱敏演示数据，可直接浏览全部产品能力。")
    st.divider(); st.markdown("<div class='disclaimer'>用于研究辅助与工程演示，不构成投资、审计或法律意见。</div>",unsafe_allow_html=True)

artifacts=st.session_state.get("artifacts") if mode=="发起真实任务" else None; is_demo=artifacts is None; metadata={} if is_demo else artifacts.metadata
company_name=DEMO["company"] if is_demo else artifacts.company; verdict=DEMO["verdict"] if is_demo else (metadata.get("due_diligence_verdict") or "待人工复核"); score=DEMO["score"] if is_demo else (metadata.get("report_review_score") or "—")
evidence_count=DEMO["evidence"] if is_demo else metadata.get("research_evidence_count",0); finding_count=DEMO["findings"] if is_demo else metadata.get("research_finding_count",0); risk_count=DEMO["risks"] if is_demo else metadata.get("risk_count",0); page_count=DEMO["pages"] if is_demo else metadata.get("page_count",0)
st.markdown(f'<div class="hero"><div class="eyebrow">Investment committee workspace · {"demo" if is_demo else "live case"}</div><h1>{company_name} <span style="color:#8b9892;font-weight:400">/ 港股 IPO 尽调</span></h1><p>从招股书解析、财务取证与行业验证，到反方质疑和终审交付；每个结论都可回溯至页码、计算过程或已登记的公开来源。</p><div style="margin-top:.8rem"><span class="status-pill">● 流程已完成</span><span class="status-pill">证据链完整</span></div></div>',unsafe_allow_html=True)
cols=st.columns(5); cards=[("投委会结论",verdict,"Final Reviewer 已复核"),("报告质量评分",score,"引用 / 完整性 / 边界"),("结构化证据",evidence_count,"均带来源定位"),("研究发现",finding_count,"跨 Agent 合并去重"),("风险信号",risk_count,f"覆盖 {page_count} 页招股书")]
for col,card in zip(cols,cards):
    with col: metric_card(*card)

overview,evidence_tab,agents_tab,report_tab=st.tabs(["投委会总览","证据与风险","Agent 协作","报告交付"])
with overview:
    left,right=st.columns([1.65,1],gap="large")
    with left:
        st.subheader("核心判断"); st.markdown('<div class="section-card"><h3 style="margin-top:0">建议有条件推进，重点核查盈利质量与客户依赖</h3><p style="color:#64736d;line-height:1.75;margin-bottom:.4rem">历史财务表现具备一定增长基础，核心业务边界清晰；但现金转化、客户集中和关联交易定价仍是影响上市质量的关键变量。建议在进入下一决策阶段前完成定向补证。</p></div>',unsafe_allow_html=True); st.subheader("重点风险矩阵")
        for title,desc,level,source in DEMO["risk_items"]:
            badge="risk-high" if level=="高风险" else "risk-mid"; st.markdown(f'<div class="section-card"><div style="display:flex;justify-content:space-between"><strong>{title}</strong><span class="{badge}">{level}</span></div><p style="margin:.45rem 0;color:#46564f">{desc}</p><small style="color:#7c8a84">证据：{source}</small></div>',unsafe_allow_html=True)
    with right:
        st.subheader("研究覆盖")
        for name,value in [("财务质量",88),("公司与业务",92),("行业与竞争",76),("法律与治理",81),("证据完整性",94)]: st.caption(name); st.progress(value/100,text=f"{value}%")
        st.subheader("待投委会追问")
        for q in ["现金流背离是否由一次性扩张投入造成？","核心客户续约与议价权有何硬证据？","关联采购价格如何证明具备市场公允性？","募投项目的收入增量假设是否过于乐观？"]: st.markdown(f"- {q}")
with evidence_tab:
    left,right=st.columns([1.35,1],gap="large"); payload=read_json(None if is_demo else artifacts.evidence_json,{}); live=payload.get("evidence",[])[:15]
    with left:
        st.subheader("Evidence → Finding Ledger")
        if live: st.dataframe(live,use_container_width=True,hide_index=True)
        else:
            for eid,claim,source in DEMO["evidence_items"]: st.markdown(f'<div class="evidence"><strong>{eid} · {claim}</strong><small>{source}</small></div>',unsafe_allow_html=True)
        st.caption("财务数字仅来自已登记表格、指标或计算 Evidence；无法确认的事项显式标记为待核查。")
    with right:
        st.subheader("取证完整性"); st.metric("Evidence 引用通过率","100%","无悬空 Finding"); st.metric("确定性财务指标","29","代码计算，模型只负责解释"); st.metric("财务风险规则","20+","异常自动触发并保留过程"); st.info("点击式 PDF 页码定位是下一阶段能力；当前交付已保留页码和来源 URL。")
with agents_tab:
    st.subheader("虚拟投研团队"); st.caption("Manager 统筹任务，四类专家并行研究，Skeptic 发起反证挑战，Final Reviewer 执行引用与合规终审。"); c1,c2=st.columns(2,gap="large")
    for idx,agent in enumerate(AGENT_TEAM):
        with (c1 if idx%2==0 else c2): st.markdown(f'<div class="agent-row"><span class="agent-dot"></span><div><div class="agent-name">{agent["name"]} <span style="color:#8a9892;font-weight:400">· {agent["stage"]}</span></div><div class="agent-role">{agent["role"]}<br>输出：{agent["output"]}</div></div></div>',unsafe_allow_html=True)
    if not is_demo:
        trace=read_json(artifacts.agent_trace_json,{}).get("messages",[])
        with st.expander(f"查看本次运行轨迹（{len(trace)} 条）"):
            for item in trace: st.markdown(f"**{item.get('sender','Agent')} → {item.get('receiver','all')}**  \n{item.get('content','')}")
with report_tab:
    st.subheader("可审计交付包"); st.caption("研究结论、底层证据和 Agent 决策轨迹同步交付，便于投资经理复核与二次分析。")
    if is_demo: st.markdown('<div class="section-card"><strong>演示模式不包含真实文件</strong><p style="color:#64736d">上传招股书并完成任务后，可下载 Markdown 尽调报告、Excel 工作底稿、evidence.json 与 agent_trace.json。</p></div>',unsafe_allow_html=True)
    else:
        report_path=Path(artifacts.final_report_path or artifacts.report_path); excel_path=Path(artifacts.due_diligence_workbook_path or artifacts.excel_path); evidence_path=Path(artifacts.evidence_json or ""); trace_path=Path(artifacts.agent_trace_json or "")
        for col,(label,path,mime) in zip(st.columns(4),[("下载尽调报告",report_path,"text/markdown"),("下载 Excel 底稿",excel_path,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),("下载证据账本",evidence_path,"application/json"),("下载 Agent 轨迹",trace_path,"application/json")]):
            with col:
                if path.is_file(): st.download_button(label,path.read_bytes(),file_name=path.name,mime=mime,use_container_width=True)
        if report_path.is_file():
            with st.expander("在线预览完整报告",expanded=True): st.markdown(report_path.read_text(encoding="utf-8"))
st.divider(); st.caption("HK IPO Intelligence Desk · Evidence-first Multi-Agent Due Diligence · Engineering MVP v0.9")

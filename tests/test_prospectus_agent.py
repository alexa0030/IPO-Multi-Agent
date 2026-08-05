from ipo_financial_agent.agents.prospectus_agent import ProspectusAgent
from ipo_financial_agent.models import PageData


def test_business_selector_excludes_toc_and_grounds_summary() -> None:
    pages = [
        PageData(
            source_file="prospectus.pdf",
            page=10,
            text="目录 业务 风险因素 客户 供应商",
            tables=[],
        ),
        PageData(
            source_file="prospectus.pdf",
            page=13,
            text=(
                "概要 我们是全球数字打印控制系统供应商，"
                "主要提供打印控制系统、打印机及耗材和软件服务。"
            ),
            tables=[],
        ),
        PageData(
            source_file="prospectus.pdf",
            page=120,
            text="业务模式 我们的解决方案覆盖打印控制与耗材。",
            tables=[],
        ),
    ]

    result = ProspectusAgent().analyze(company="汉森软件", pages=pages)

    assert "全球数字打印控制系统供应商" in result.business_model
    assert result.business_model_evidence[0].page_number == 13
    assert all(item.page_number != 10 for item in result.business_model_evidence)


def test_offline_analysis_extracts_product_categories_and_masked_counterparties() -> None:
    pages = [
        PageData(
            source_file="prospectus.pdf",
            page=13,
            text=(
                "概要 我们是一家全链条数字打印解决方案供应商，"
                "主要提供打印控制系统、打印机及耗材、打印软件及服务。"
            ),
            tables=[],
        ),
        PageData(
            source_file="prospectus.pdf",
            page=140,
            text=(
                "业务 我们的前五大客户详情如下：客户A、客户B、客户C。"
                "来自前五大客户的收入占总收入28.6%。"
            ),
            tables=[],
        ),
        PageData(
            source_file="prospectus.pdf",
            page=148,
            text="业务 前五大供应商详情如下：供应商A、供应商B。",
            tables=[],
        ),
    ]

    result = ProspectusAgent().analyze(company="测试公司", pages=pages)

    assert {item.name for item in result.main_products} >= {
        "打印控制系统",
        "打印机及耗材",
        "打印软件及服务",
    }
    assert {item.name for item in result.customers} >= {"客户A", "客户B"}
    assert {item.name for item in result.suppliers} >= {"供应商A", "供应商B"}
    assert all(item.evidence for item in result.main_products)
    assert next(item for item in result.customers if item.name == "客户A").evidence[
        0
    ].page_number == 140


def test_company_dossier_is_universal_and_detects_industry_and_company_signals() -> None:
    pages = [
        PageData(source_file="x.pdf", page=30, text="历史、发展及公司架构 控股股东及实际控制人", tables=[]),
        PageData(source_file="x.pdf", page=50, text="公司完成一项收购并确认业务合并，交易不构成关联交易", tables=[]),
        PageData(source_file="x.pdf", page=80, text="主要产品采用直销模式，按照合同交付及验收后结算", tables=[]),
        PageData(source_file="x.pdf", page=90, text="前五大客户及前五大供应商，第一大客户收入占比较高", tables=[]),
        PageData(source_file="x.pdf", page=100, text="生产线产能、产量、销量、良率及主要原材料情况", tables=[]),
        PageData(source_file="x.pdf", page=110, text="主要附属公司及董事及高级管理层", tables=[]),
    ]

    result = ProspectusAgent().analyze(company="任意制造企业", pages=pages)

    assert "manufacturing" in result.dossier.industry_profiles
    assert "acquisition_or_disposal" in result.dossier.company_specific_signals
    assert "customer_concentration" in result.dossier.company_specific_signals
    assert result.dossier.coverage_gaps == []
    assert result.dossier.topic_page_map["capital_events"] == [50]


def test_one_page_can_support_multiple_dossier_topics() -> None:
    pages = [
        PageData(
            source_file="x.pdf",
            page=80,
            text=(
                "业务模式 主要产品采用直销模式，按照合同交付及验收后结算。"
                "前五大客户收入占比较高，信用期一般为90日。"
            ),
            tables=[],
        )
    ]

    selected = ProspectusAgent()._select_relevant_pages(pages, None)
    dossier = ProspectusAgent._build_dossier("任意公司", selected)

    assert dossier.topic_page_map["products_business_model"] == [80]
    assert dossier.topic_page_map["customers_suppliers"] == [80]


def test_dossier_parser_rejects_hallucinated_page_numbers() -> None:
    raw = '''{"findings":[
      {"statement":"完成一项收购。","page":"P50","evidence_quote":"公司完成收购","finding_type":"fact","confidence":0.9},
      {"statement":"虚构了一项出售。","page":"P50","evidence_quote":"公司完成出售","finding_type":"fact","confidence":0.9},
      {"statement":"不存在的披露。","page":999,"evidence_quote":"公司完成收购","finding_type":"fact","confidence":0.9}
    ],"open_questions":["核查交易对价支付情况。"]}'''
    findings, questions = ProspectusAgent._parse_dossier_topic(
        "capital_events", raw, [{"page": 50, "text": "公司完成收购。", "title": "capital_events"}]
    )

    assert len(findings) == 1
    assert findings[0].evidence[0].page_number == 50
    assert findings[0].statement == "公司完成收购"
    assert findings[0].evidence[0].content == "公司完成收购"
    assert findings[0].evidence[0].metadata["quote_verified"] is True
    assert questions == ["核查交易对价支付情况。"]


def test_dossier_parser_rejects_off_topic_and_labels_analysis() -> None:
    raw = '''{"findings":[
      {"statement":"客户集中度处于合理水平。","page":139,"evidence_quote":"前五大客户收入占总收入39.2%","finding_type":"fact","confidence":0.9},
      {"statement":"公司总部位于深圳。","page":139,"evidence_quote":"公司总部位于深圳","finding_type":"fact","confidence":0.9}
    ],"open_questions":[]}'''
    findings, _ = ProspectusAgent._parse_dossier_topic(
        "customers_suppliers",
        raw,
        [
            {
                "page": 139,
                "text": "前五大客户收入占总收入39.2%。公司总部位于深圳。",
                "title": "customers_suppliers",
            }
        ],
    )

    assert len(findings) == 1
    assert findings[0].finding_type == "analyst_inference"
    assert findings[0].statement == "客户集中度处于合理水平。"


def test_dossier_parser_rejects_third_party_subsidiary_relationship() -> None:
    raw = '''{"findings":[
      {"statement":"深创投持有30.43%的合伙权益。","page":106,"evidence_quote":"深圳红土的普通合伙人为深创投的全资附属公司，深圳市引导基金持有深圳红土30.43%的合伙权益。","finding_type":"fact","confidence":0.9},
      {"statement":"董事会由七名董事组成。","page":180,"evidence_quote":"本公司董事会目前由七名董事组成。","finding_type":"fact","confidence":0.9}
    ],"open_questions":[]}'''
    findings, _ = ProspectusAgent._parse_dossier_topic(
        "subsidiaries_management",
        raw,
        [
            {
                "page": 106,
                "text": "深圳红土的普通合伙人为深创投的全资附属公司，深圳市引导基金持有深圳红土30.43%的合伙权益。",
                "title": "subsidiaries_management",
            },
            {
                "page": 180,
                "text": "本公司董事会目前由七名董事组成。",
                "title": "subsidiaries_management",
            },
        ],
    )

    assert len(findings) == 1
    assert findings[0].evidence[0].page_number == 180
    assert findings[0].statement == "本公司董事会目前由七名董事组成。"


def test_dossier_open_questions_stay_within_topic_and_do_not_claim_omission() -> None:
    raw = '''{"findings":[],"open_questions":[
      "招股书未披露管理层的具体分工。",
      "招股书未披露收购对价。"
    ]}'''

    _, questions = ProspectusAgent._parse_dossier_topic(
        "subsidiaries_management",
        raw,
        [{"page": 180, "text": "董事及高级管理层", "title": "subsidiaries_management"}],
    )

    assert questions == ["当前候选页尚未核实管理层的具体分工。"]

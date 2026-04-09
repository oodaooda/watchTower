from app.routers.qa import (
    _extract_ticker,
    _extract_tickers,
    _extract_company_keywords,
    _build_plan,
    _safe_trace_params,
    _rank_news_items,
    _is_safe_article_url,
    _news_context_for_company,
    _synthesize_answer,
    _answer_question,
    _resolve_companies_from_plan,
    _classify_response_mode,
    _strip_numeric_sentences,
    _requested_metric_fields,
    _validate_readonly_sql,
    _ensure_limit,
    _extract_tables_from_sql,
    _should_use_quarterly_fallback,
    _synthesize_sql_answer,
    _is_transcript_question,
    _is_implicit_company_followup,
    _build_structured_non_news_answer,
    _execute_action,
)
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.db import Base
from app.core.models import Company, EarningsCallTranscript, EarningsCallTranscriptSegment, FavoriteCompany, PortfolioPosition


def test_extract_ticker_skips_common_words():
    assert _extract_ticker("what was it's earnings for the last 10 years") is None


def test_extract_ticker_does_not_promote_lowercase_tell_to_ticker():
    assert _extract_ticker("tell me about my portfolio") is None


def test_classify_response_mode_routes_conceptual_prompt_to_general():
    mode = _classify_response_mode("what is operating leverage", has_entities=False, parsed_mode=None)
    assert mode == "general"


def test_classify_response_mode_keeps_metric_fact_question_grounded():
    mode = _classify_response_mode("what is amd's last close price", has_entities=True, parsed_mode=None)
    assert mode == "grounded"


def test_requested_metric_fields_detects_close_price():
    fields = _requested_metric_fields("what is amd's last close price?")
    assert "close_price" in fields
    assert "pe_ttm" not in fields


def test_validate_readonly_sql_blocks_ddl():
    ok, reason = _validate_readonly_sql("DROP TABLE companies", {"companies"})
    assert ok is False
    assert reason in {"non_select_statement", "banned_sql_token"}


def test_validate_readonly_sql_allows_select_known_table():
    ok, reason = _validate_readonly_sql("SELECT ticker FROM companies LIMIT 5", {"companies"})
    assert ok is True
    assert reason == "ok"


def test_validate_readonly_sql_rejects_unknown_table():
    ok, reason = _validate_readonly_sql("SELECT * FROM unknown_table LIMIT 5", {"companies"})
    assert ok is False
    assert reason.startswith("table_not_allowed:")


def test_ensure_limit_adds_limit_when_missing():
    sql = _ensure_limit("SELECT ticker FROM companies", 100)
    assert "LIMIT 100" in sql


def test_extract_tables_from_sql_reads_from_and_join():
    tables = _extract_tables_from_sql(
        "SELECT c.ticker, p.close_price FROM companies c JOIN prices_annual p ON c.id=p.company_id"
    )
    assert "companies" in tables
    assert "prices_annual" in tables


def test_should_use_quarterly_fallback_when_report_date_query_returns_zero():
    sql = "SELECT * FROM financials_quarterly WHERE report_date >= CURRENT_DATE - INTERVAL '5 years'"
    assert _should_use_quarterly_fallback(sql, []) is True
    assert _should_use_quarterly_fallback(sql, [{"x": 1}]) is False


def test_extract_tables_from_sql_ignores_current_date_token():
    sql = "SELECT EXTRACT(YEAR FROM CURRENT_DATE) AS y FROM financials_quarterly fq JOIN companies c ON c.id=fq.company_id"
    tables = _extract_tables_from_sql(sql)
    assert "current_date" not in tables
    assert "financials_quarterly" in tables
    assert "companies" in tables


def test_synthesize_sql_answer_quarterly_is_conversational():
    rows = [
        {"ticker": "TSLA", "fiscal_year": 2025, "fiscal_period": "Q3", "revenue": 28095000000.0, "net_income": 1373000000.0},
        {"ticker": "TSLA", "fiscal_year": 2025, "fiscal_period": "Q2", "revenue": 22496000000.0, "net_income": 1172000000.0},
        {"ticker": "TSLA", "fiscal_year": 2025, "fiscal_period": "Q1", "revenue": 19335000000.0, "net_income": 409000000.0},
    ]
    answer = _synthesize_sql_answer("quarterly revenue tesla", rows, "SELECT ...")
    assert "Quarterly financial trend for TSLA" in answer
    assert "Revenue in this window ranges" in answer
    assert "Quarterly detail:" in answer


def test_strip_numeric_sentences_removes_numbered_claims():
    cleaned = _strip_numeric_sentences(
        "Operating leverage links fixed costs to margin expansion. It rose 25% last year. "
        "Higher fixed cost intensity increases sensitivity to revenue changes."
    )
    assert "25%" not in cleaned
    assert "fixed costs" in cleaned


def test_extract_keywords_from_company_name():
    keywords = _extract_company_keywords("what was apples earnings for the last 10 years")
    assert "apple" in keywords


def test_build_plan_for_broad_question_uses_multi_action_bundle():
    plan = _build_plan("Tell me about Tesla")
    assert "company_snapshot" in plan["actions"]
    assert "pe" in plan["actions"]
    assert "earnings_history" in plan["actions"]


def test_build_plan_extracts_compare_companies():
    plan = _build_plan("what can you tell me about nvda vs tsmc")
    assert plan["compare"] is True
    assert "NVDA" in [c.upper() for c in plan["companies"]]
    assert "TSMC" in [c.upper() for c in plan["companies"]]
    assert "CAN" not in [c.upper() for c in plan["companies"]]
    assert "YOU" not in [c.upper() for c in plan["companies"]]
    assert "VS" not in [c.upper() for c in plan["companies"]]


def test_safe_trace_params_redacts_unapproved_keys():
    safe = _safe_trace_params(
        {
            "company_id": 17,
            "years": 10,
            "secret": "do-not-expose",
            "sql": "raw query",
        }
    )
    assert safe["company_id"] == 17
    assert safe["years"] == 10
    assert "secret" not in safe
    assert "sql" not in safe


def test_build_plan_news_question_includes_news_context():
    plan = _build_plan("why was tesla down last week")
    assert "news_context" in plan["actions"]
    assert "DOWN" not in [c.upper() for c in plan["companies"]]
    assert "WEEK" not in [c.upper() for c in plan["companies"]]


def test_is_transcript_question_detects_transcript_prompt():
    assert _is_transcript_question("what did management say on the earnings call transcript") is True


def test_is_implicit_company_followup_detects_pronoun_prompt():
    assert _is_implicit_company_followup("Do you have access to their last earnings call?") is True
    assert _is_implicit_company_followup("Do you have access to AAPL last earnings call?") is False


def test_build_plan_transcript_prompt_prefers_transcript_action():
    plan = _build_plan("what did management say on the earnings call for nvda")
    assert "transcript_context" in plan["actions"]


def test_transcript_question_reports_gap_when_transcript_unavailable():
    company = SimpleNamespace(ticker="NVDA", name="NVIDIA Corporation")
    answer, sources = _build_structured_non_news_answer(
        question="What did management say on the earnings call transcript for NVDA?",
        companies=[company],
        payload_by_company={"NVDA": {"company_snapshot": {}, "transcript_context": {"available": False}}},
        unresolved=[],
        mode="grounded",
    )
    assert "transcript is unavailable" in answer
    assert "database" in sources


def test_execute_action_transcript_context_returns_citations_and_segments():
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        company = Company(ticker="NVDA", name="NVIDIA Corporation")
        db.add(company)
        db.commit()
        db.refresh(company)

        transcript = EarningsCallTranscript(
            company_id=company.id,
            ticker="NVDA",
            fiscal_year=2026,
            fiscal_quarter=1,
            source_provider="alpha_vantage",
            source_url="https://example.com/nvda-transcript",
            source_doc_id="NVDA-2026Q1",
            content_hash="abc",
            language="en",
            storage_mode="restricted",
        )
        db.add(transcript)
        db.flush()
        db.add_all(
            [
                EarningsCallTranscriptSegment(
                    transcript_id=transcript.id,
                    segment_index=0,
                    speaker="CEO",
                    section="prepared_remarks",
                    text="AI demand accelerated significantly across regions.",
                    token_count=7,
                ),
                EarningsCallTranscriptSegment(
                    transcript_id=transcript.id,
                    segment_index=1,
                    speaker="CFO",
                    section="q_and_a",
                    text="Gross margin expansion was driven by mix.",
                    token_count=8,
                ),
            ]
        )
        db.commit()

        result, citations, trace, queries = _execute_action(
            db=db,
            company=company,
            action="transcript_context",
            years=10,
            question="what did management say about demand and margin in the transcript?",
        )
        assert result["available"] is True
        assert result["fiscal_year"] == 2026
        assert isinstance(result["segments"], list) and len(result["segments"]) >= 1
        assert result["segments"][0]["segment_index"] == 0
        assert "earnings_call_transcripts" in citations
        assert "earnings_call_transcript_segments" in citations
        assert any(isinstance(c, str) and c.startswith("https://") for c in citations)
        assert "transcript context" in trace.lower()
        assert len(queries) >= 2


def test_build_plan_compare_infers_compare_mode():
    plan = _build_plan("compare nvda versus tsmc")
    assert plan["compare"] is True


def test_build_plan_latest_news_of_single_ticker_keeps_only_ticker():
    plan = _build_plan("what's the latest news of qcls?")
    assert [c.upper() for c in plan["companies"]] == ["QCLS"]


def test_build_plan_explicit_favorites_sets_use_favorites():
    plan = _build_plan("what are my favorite companies?")
    assert plan["use_favorites"] is True
    assert plan["favorites_reason"] == "explicit_portfolio_language"
    assert plan["companies"] == []


def test_build_plan_tell_me_about_my_portfolio_uses_favorites():
    plan = _build_plan("tell me about my portfolio")
    assert plan["companies"] == []
    assert plan["use_portfolio"] is True
    assert plan["portfolio_reason"] == "explicit_portfolio_language"


def test_build_plan_explicit_ticker_overrides_favorites_fallback():
    plan = _build_plan("what is AAPL p/e in my portfolio?")
    assert "AAPL" in [c.upper() for c in plan["companies"]]
    assert plan["use_favorites"] is False
    assert plan["use_portfolio"] is True


def test_extract_tickers_ignores_plain_words_in_news_question():
    tickers = _extract_tickers("what's the latest news you have on qcls")
    assert "QCLS" in tickers
    assert "ON" not in tickers
    assert "HAVE" not in tickers


def test_extract_tickers_does_not_infer_two_letter_token_from_followup():
    tickers = _extract_tickers("do you have access to their last earnings call")
    assert "DO" not in tickers


def test_rank_news_items_prioritizes_relevant_headlines():
    items = [
        {"title": "Factory outage in Europe", "summary": "Supply issue", "sentiment": "Neutral"},
        {"title": "Tesla deliveries beat estimates", "summary": "Demand and margin outlook", "sentiment": "Bullish"},
        {"title": "Macro rates update", "summary": "Fed commentary", "sentiment": "Neutral"},
    ]
    ranked = _rank_news_items(items, "why was tesla down last week", top_n=3)
    assert ranked[0]["title"] == "Tesla deliveries beat estimates"
    assert ranked[0]["relevance_score"] >= ranked[1]["relevance_score"]


def test_is_safe_article_url_blocks_local_and_non_http():
    assert _is_safe_article_url("https://example.com/news") is True
    assert _is_safe_article_url("http://127.0.0.1/test") is False
    assert _is_safe_article_url("http://10.0.0.25/test") is False
    assert _is_safe_article_url("file:///etc/passwd") is False


def test_news_context_falls_back_to_headlines_when_article_fetch_fails(monkeypatch):
    monkeypatch.setattr("app.routers.qa.settings.alpha_vantage_api_key", "test-key")
    monkeypatch.setattr(
        "app.routers.qa._get_company_news",
        lambda ticker, key, limit: [
            {
                "title": "Tesla faces demand concerns",
                "summary": "Mixed delivery outlook.",
                "url": "https://example.com/tesla-news",
                "source": "Example News",
                "sentiment": "Somewhat-Bearish",
            }
        ],
    )
    monkeypatch.setattr("app.routers.qa._fetch_article_excerpt", lambda url: None)

    company = SimpleNamespace(ticker="TSLA")
    context = _news_context_for_company(company, question="why was tesla down last week")
    assert len(context["items"]) == 1
    assert context["items"][0]["title"] == "Tesla faces demand concerns"
    assert context["articles"] == []


def test_news_synthesis_contains_structured_sections():
    company = SimpleNamespace(ticker="TSLA", name="Tesla, Inc.")
    payload = {
        "TSLA": {
            "company_snapshot": {
                "latest_fiscal_year": 2024,
                "revenue": 97690000000.0,
                "net_income": 7091000000.0,
                "close_price": 456.56,
            },
            "pe": {"pe_ttm": 223.8039},
            "revenue_history": {"history": [{"revenue": 4046025000.0}, {"revenue": 97690000000.0}]},
            "earnings_history": {"history": [{"net_income": -888663000.0}, {"net_income": 7091000000.0}]},
            "news_context": {
                "items": [{"title": "Tesla delivery miss", "source": "Example", "sentiment": "Bearish"}],
                "articles": [],
            },
        }
    }
    answer = _synthesize_answer(
        question="why was tesla down last week",
        companies=[company],
        plan={"actions": ["news_context"]},
        payload_by_company=payload,
        unresolved=[],
    )
    assert "Data signals:" in answer
    assert "News catalysts:" in answer
    assert "Confidence:" in answer


def test_answer_question_headlines_only_fallback_message(monkeypatch):
    company = SimpleNamespace(ticker="TSLA", name="Tesla, Inc.", id=17)

    monkeypatch.setattr(
        "app.routers.qa._build_plan",
        lambda question: {
            "companies": ["TSLA"],
            "years": 10,
            "actions": ["company_snapshot", "pe", "news_context"],
            "compare": False,
            "response_mode": "grounded",
        },
    )
    monkeypatch.setattr(
        "app.routers.qa._resolve_companies_from_plan",
        lambda db, question, plan: ([company], [], []),
    )

    def fake_execute_action(db, company_obj, action, years, question):
        if action == "company_snapshot":
            return (
                {
                    "ticker": "TSLA",
                    "company_name": "Tesla, Inc.",
                    "latest_fiscal_year": 2024,
                    "revenue": 97690000000.0,
                    "net_income": 7091000000.0,
                    "close_price": 456.56,
                },
                ["companies", "financials_annual", "prices_annual"],
                "snapshot",
                [],
            )
        if action == "pe":
            return (
                {"ticker": "TSLA", "pe_ttm": 223.8039, "fiscal_year": 2024},
                ["prices_annual"],
                "pe",
                [],
            )
        if action == "news_context":
            return (
                {
                    "ticker": "TSLA",
                    "items": [
                        {
                            "title": "Tesla demand concerns",
                            "source": "Example",
                            "sentiment": "Somewhat-Bearish",
                        }
                    ],
                    "articles": [],
                },
                ["news_sentiment"],
                "news",
                [],
            )
        return ({}, [], "noop", [])

    monkeypatch.setattr("app.routers.qa._execute_action", fake_execute_action)

    response = _answer_question("why was tesla down last week", db=SimpleNamespace())
    assert "Confidence:" in response.answer
    assert "relied on headline summaries only" in response.answer


def test_resolver_requires_confidence_threshold(monkeypatch):
    low_conf_company = SimpleNamespace(id=42, ticker="EHVVF", name="Ehave, Inc.")
    monkeypatch.setattr(
        "app.routers.qa._resolve_company_candidate",
        lambda db, question, candidate: (low_conf_company, 0.6, "single_contains_low_confidence"),
    )
    resolved, unresolved, diagnostics = _resolve_companies_from_plan(
        db=SimpleNamespace(),
        question="latest news you have",
        plan={"companies": ["HAVE"]},
    )
    assert resolved == []
    assert unresolved == ["HAVE"]
    assert diagnostics[0]["decision"] == "clarification_required"
    assert diagnostics[0]["resolved_ticker"] == "EHVVF"


def test_answer_question_returns_clarification_when_no_confident_resolution(monkeypatch):
    monkeypatch.setattr(
        "app.routers.qa._build_plan",
        lambda question: {"companies": ["HAVE"], "actions": ["company_snapshot"], "years": 10, "compare": False},
    )
    monkeypatch.setattr(
        "app.routers.qa._resolve_companies_from_plan",
        lambda db, question, plan: (
            [],
            ["HAVE"],
            [
                {
                    "candidate": "HAVE",
                    "resolved_ticker": "EHVVF",
                    "resolved_name": "Ehave, Inc.",
                    "confidence": 0.6,
                    "reason": "single_contains_low_confidence",
                    "decision": "clarification_required",
                }
            ],
        ),
    )
    response = _answer_question("latest news you have", db=SimpleNamespace())
    assert "Please clarify the ticker or full company name" in response.answer
    assert "HAVE -> Ehave, Inc. (EHVVF)" in response.answer
    assert response.data["clarification_needed"] is True


def test_answer_question_general_mode_without_ticker(monkeypatch):
    monkeypatch.setattr(
        "app.routers.qa._build_plan",
        lambda question: {
            "companies": [],
            "actions": [],
            "years": 10,
            "compare": False,
            "response_mode": "general",
        },
    )
    monkeypatch.setattr(
        "app.routers.qa._resolve_companies_from_plan",
        lambda db, question, plan: ([], [], []),
    )
    monkeypatch.setattr(
        "app.routers.qa._synthesize_general_context",
        lambda question: "Operating leverage explains how fixed costs amplify profit sensitivity.",
    )
    response = _answer_question("what is operating leverage", db=SimpleNamespace())
    assert "What data shows:" in response.answer
    assert "General context:" in response.answer
    assert "Gaps:" in response.answer
    assert "general_context" in response.citations


def test_answer_question_metric_focus_returns_close_price_line(monkeypatch):
    company = SimpleNamespace(ticker="AMD", name="ADVANCED MICRO DEVICES INC", id=43)
    monkeypatch.setattr(
        "app.routers.qa._build_plan",
        lambda question: {
            "companies": ["AMD"],
            "actions": ["company_snapshot", "pe"],
            "years": 10,
            "compare": False,
            "response_mode": "grounded",
        },
    )
    monkeypatch.setattr(
        "app.routers.qa._resolve_companies_from_plan",
        lambda db, question, plan: ([company], [], []),
    )

    def fake_execute_action(db, company_obj, action, years, question):
        if action == "company_snapshot":
            return (
                {
                    "ticker": "AMD",
                    "company_name": "ADVANCED MICRO DEVICES INC",
                    "latest_fiscal_year": 2024,
                    "revenue": 25785000000.0,
                    "net_income": 1641000000.0,
                    "close_price": 215.05,
                },
                ["companies", "financials_annual", "prices_annual"],
                "snapshot",
                [],
            )
        if action == "pe":
            return ({"ticker": "AMD", "pe_ttm": None, "fiscal_year": 2024}, ["prices_annual"], "pe", [])
        return ({}, [], "noop", [])

    monkeypatch.setattr("app.routers.qa._execute_action", fake_execute_action)

    response = _answer_question("what is amd's last close price?", db=SimpleNamespace())
    assert "last close price: $215.05" in response.answer


def test_answer_question_falls_back_when_sql_invalid(monkeypatch):
    company = SimpleNamespace(ticker="AMD", name="ADVANCED MICRO DEVICES INC", id=43)
    monkeypatch.setattr("app.routers.qa.settings.qa_sql_enabled", True)
    monkeypatch.setattr(
        "app.routers.qa._build_plan",
        lambda question: {
            "companies": ["AMD"],
            "actions": ["company_snapshot"],
            "years": 10,
            "compare": False,
            "response_mode": "grounded",
        },
    )
    monkeypatch.setattr(
        "app.routers.qa._resolve_companies_from_plan",
        lambda db, question, plan: ([company], [], []),
    )
    monkeypatch.setattr("app.routers.qa._get_schema_context", lambda db: {"tables": {"companies": []}})
    monkeypatch.setattr("app.routers.qa._plan_sql_with_llm", lambda question, schema, companies: "DROP TABLE companies")

    def fake_execute_action(db, company_obj, action, years, question):
        return (
            {
                "ticker": "AMD",
                "company_name": "ADVANCED MICRO DEVICES INC",
                "latest_fiscal_year": 2024,
                "close_price": 215.05,
            },
            ["companies", "prices_annual"],
            "snapshot",
            [],
        )

    monkeypatch.setattr("app.routers.qa._execute_action", fake_execute_action)
    response = _answer_question("what is amd's last close price?", db=SimpleNamespace())
    assert "last close price: $215.05" in response.answer


def test_answer_question_exposes_top_level_news_for_openclaw(monkeypatch):
    company = SimpleNamespace(ticker="QCLS", name="Q/C TECHNOLOGIES, INC.", id=6291)
    monkeypatch.setattr(
        "app.routers.qa._build_plan",
        lambda question: {
            "companies": ["QCLS"],
            "actions": ["company_snapshot", "pe", "news_context"],
            "years": 10,
            "compare": False,
            "response_mode": "grounded",
        },
    )
    monkeypatch.setattr(
        "app.routers.qa._resolve_companies_from_plan",
        lambda db, question, plan: ([company], [], []),
    )

    def fake_execute_action(db, company_obj, action, years, question):
        if action == "company_snapshot":
            return (
                {"ticker": "QCLS", "company_name": "Q/C TECHNOLOGIES, INC.", "close_price": 3.95},
                ["companies", "prices_annual"],
                "snapshot",
                [],
            )
        if action == "pe":
            return ({"ticker": "QCLS", "pe_ttm": -0.3543, "fiscal_year": 2024}, ["prices_annual"], "pe", [])
        if action == "news_context":
            return (
                {
                    "ticker": "QCLS",
                    "items": [
                        {
                            "title": "QCLS Surges on European Expansion News",
                            "url": "https://example.com/qcls1",
                            "source": "StocksToTrade",
                            "published_at": "2026-02-16T00:00:00Z",
                            "sentiment": "Somewhat-Bullish",
                            "relevance_score": 7,
                        },
                        {
                            "title": "QCLS Stock Surges Amid Financial Developments",
                            "url": "https://example.com/qcls2",
                            "source": "StocksToTrade",
                            "published_at": "2026-02-15T00:00:00Z",
                            "sentiment": "Bearish",
                            "relevance_score": 6,
                        },
                    ],
                    "articles": [],
                },
                ["news_sentiment"],
                "news",
                [],
            )
        return ({}, [], "noop", [])

    monkeypatch.setattr("app.routers.qa._execute_action", fake_execute_action)

    response = _answer_question("latest news about qcls", db=SimpleNamespace())
    assert len(response.news) >= 2
    assert response.news[0].url.startswith("https://")
    assert response.data["news"][0]["url"].startswith("https://")
    assert response.data["news"][0]["publishedAt"] == "2026-02-16T00:00:00Z"


def test_answer_question_uses_favorites_fallback_and_reports_plan(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        apple = Company(ticker="AAPL", name="Apple Inc.")
        microsoft = Company(ticker="MSFT", name="Microsoft Corporation")
        db.add_all([apple, microsoft])
        db.commit()
        db.refresh(apple)
        db.refresh(microsoft)
        db.add_all(
            [
                FavoriteCompany(company_id=apple.id, sort_order=1),
                FavoriteCompany(company_id=microsoft.id, sort_order=2),
            ]
        )
        db.commit()

        monkeypatch.setattr(
            "app.routers.qa._build_plan",
            lambda question: {
                "companies": [],
                "actions": ["company_snapshot", "pe"],
                "years": 10,
                "compare": False,
                "response_mode": "grounded",
                "use_favorites": True,
                "favorites_reason": "explicit_portfolio_language",
            },
        )
        monkeypatch.setattr(
            "app.routers.qa._resolve_companies_from_plan",
            lambda db, question, plan: ([], [], []),
        )
        monkeypatch.setattr("app.routers.qa._should_try_sql_path", lambda *args, **kwargs: False)

        def fake_execute_action(db, company_obj, action, years, question):
            if action == "company_snapshot":
                return (
                    {
                        "ticker": company_obj.ticker,
                        "company_name": company_obj.name,
                        "latest_fiscal_year": 2024,
                        "revenue": 1000000000.0,
                        "net_income": 100000000.0,
                        "close_price": 100.0,
                    },
                    ["companies", "financials_annual", "prices_annual"],
                    "snapshot",
                    [],
                )
            if action == "pe":
                return (
                    {"ticker": company_obj.ticker, "pe_ttm": 25.0, "fiscal_year": 2024},
                    ["prices_annual"],
                    "pe",
                    [],
                )
            return ({}, [], "noop", [])

        monkeypatch.setattr("app.routers.qa._execute_action", fake_execute_action)
        monkeypatch.setattr("app.routers.qa._render_answer_with_llm", lambda **kwargs: kwargs["fallback_answer"])

        response = _answer_question("what are my favorite assets?", db=db)
        assert "Favorite assets currently tracked:" in response.answer
        assert "Apple Inc. (AAPL)" in response.answer
        assert "Microsoft Corporation (MSFT)" in response.answer
        assert response.data["plan"]["use_favorites"] is True
        assert response.data["plan"]["companies_resolved"] == ["AAPL", "MSFT"]
        assert "favorite_companies" in response.citations


def test_answer_question_returns_clear_message_when_favorites_are_empty(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        monkeypatch.setattr(
            "app.routers.qa._build_plan",
            lambda question: {
                "companies": [],
                "actions": ["company_snapshot", "pe"],
                "years": 10,
                "compare": False,
                "response_mode": "grounded",
                "use_favorites": True,
                "favorites_reason": "explicit_portfolio_language",
            },
        )
        monkeypatch.setattr(
            "app.routers.qa._resolve_companies_from_plan",
            lambda db, question, plan: ([], [], []),
        )

        response = _answer_question("what are my favorites?", db=db)
        assert "No favorite assets are currently saved" in response.answer
        assert response.data["plan"]["favorites_total"] == 0
        assert response.citations == ["favorite_companies"]


def test_answer_question_favorites_news_returns_top_level_news(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        qcls = Company(ticker="QCLS", name="Q/C TECHNOLOGIES, INC.")
        db.add(qcls)
        db.commit()
        db.refresh(qcls)
        db.add(FavoriteCompany(company_id=qcls.id, sort_order=1))
        db.commit()

        monkeypatch.setattr(
            "app.routers.qa._build_plan",
            lambda question: {
                "companies": [],
                "actions": ["company_snapshot", "pe", "news_context"],
                "years": 10,
                "compare": False,
                "response_mode": "grounded",
                "use_favorites": True,
                "favorites_reason": "explicit_portfolio_language",
            },
        )
        monkeypatch.setattr(
            "app.routers.qa._resolve_companies_from_plan",
            lambda db, question, plan: ([], [], []),
        )
        monkeypatch.setattr("app.routers.qa._should_try_sql_path", lambda *args, **kwargs: False)

        def fake_execute_action(db, company_obj, action, years, question):
            if action == "company_snapshot":
                return (
                    {"ticker": "QCLS", "company_name": "Q/C TECHNOLOGIES, INC.", "close_price": 3.95},
                    ["companies", "prices_annual"],
                    "snapshot",
                    [],
                )
            if action == "pe":
                return ({"ticker": "QCLS", "pe_ttm": -0.3543, "fiscal_year": 2024}, ["prices_annual"], "pe", [])
            if action == "news_context":
                return (
                    {
                        "ticker": "QCLS",
                        "items": [
                            {
                                "title": "QCLS Surges on Expansion News",
                                "url": "https://example.com/qcls1",
                                "source": "Example",
                                "published_at": "2026-02-16T00:00:00Z",
                                "sentiment": "Somewhat-Bullish",
                                "relevance_score": 9,
                            }
                        ],
                        "articles": [],
                    },
                    ["news_sentiment"],
                    "news",
                    [],
                )
            return ({}, [], "noop", [])

        monkeypatch.setattr("app.routers.qa._execute_action", fake_execute_action)
        monkeypatch.setattr("app.routers.qa._render_answer_with_llm", lambda **kwargs: kwargs["fallback_answer"])

        response = _answer_question("what's the latest news on my portfolio?", db=db)
        assert response.data["plan"]["use_favorites"] is True
        assert len(response.news) == 1
        assert response.news[0].url == "https://example.com/qcls1"


def test_answer_question_favorites_scope_note_when_truncated(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        companies = []
        for idx in range(12):
            company = Company(ticker=f"T{idx:02d}", name=f"Test Company {idx}")
            db.add(company)
            companies.append(company)
        db.commit()
        for company in companies:
            db.refresh(company)
        db.add_all(
            [FavoriteCompany(company_id=company.id, sort_order=i + 1) for i, company in enumerate(companies)]
        )
        db.commit()

        monkeypatch.setattr(
            "app.routers.qa._build_plan",
            lambda question: {
                "companies": [],
                "actions": ["company_snapshot", "pe"],
                "years": 10,
                "compare": False,
                "response_mode": "grounded",
                "use_favorites": True,
                "favorites_reason": "explicit_portfolio_language",
            },
        )
        monkeypatch.setattr(
            "app.routers.qa._resolve_companies_from_plan",
            lambda db, question, plan: ([], [], []),
        )
        monkeypatch.setattr("app.routers.qa._should_try_sql_path", lambda *args, **kwargs: False)

        def fake_execute_action(db, company_obj, action, years, question):
            if action == "company_snapshot":
                return (
                    {
                        "ticker": company_obj.ticker,
                        "company_name": company_obj.name,
                        "latest_fiscal_year": 2024,
                        "revenue": 1000000.0,
                        "net_income": 500000.0,
                        "close_price": 10.0,
                    },
                    ["companies", "financials_annual", "prices_annual"],
                    "snapshot",
                    [],
                )
            if action == "pe":
                return (
                    {"ticker": company_obj.ticker, "pe_ttm": 20.0, "fiscal_year": 2024},
                    ["prices_annual"],
                    "pe",
                    [],
                )
            return ({}, [], "noop", [])

        monkeypatch.setattr("app.routers.qa._execute_action", fake_execute_action)
        monkeypatch.setattr("app.routers.qa._render_answer_with_llm", lambda **kwargs: kwargs["fallback_answer"])

        response = _answer_question("show my portfolio", db=db)
        assert response.data["plan"]["favorites_truncated"] is True
        assert response.data["plan"]["favorites_total"] == 12
        assert "Favorites scope note:" in response.answer


def test_answer_question_portfolio_summary_returns_mixed_holdings(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        aapl = Company(ticker="AAPL", name="Apple Inc.", asset_type="equity")
        vgt = Company(ticker="VGT", name="VGT ETF", asset_type="etf")
        db.add_all([aapl, vgt])
        db.commit()
        db.refresh(aapl)
        db.refresh(vgt)
        db.add_all(
            [
                PortfolioPosition(company_id=aapl.id, quantity=10, avg_cost_basis=150),
                PortfolioPosition(company_id=vgt.id, quantity=5, avg_cost_basis=400),
            ]
        )
        db.commit()

        monkeypatch.setattr("app.routers.portfolio.fetch_alpha_quotes", lambda tickers: {
            "AAPL": {"price": 200.0, "source": "alpha_vantage", "status": "live"},
            "VGT": {"price": 450.0, "source": "alpha_vantage", "status": "live"},
        })

        response = _answer_question("tell me about my portfolio", db=db)
        assert "Portfolio summary:" in response.answer
        assert "Grouped holdings:" in response.answer
        assert "AAPL (equity, 1 lot)" in response.answer
        assert "VGT (etf, 1 lot)" in response.answer
        assert response.data["plan"]["use_portfolio"] is True
        assert response.data["plan"]["portfolio_total_positions"] == 2
        assert "portfolio_positions" in response.citations


def test_answer_question_portfolio_gain_for_explicit_symbol(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        vgt = Company(ticker="VGT", name="VGT ETF", asset_type="etf")
        db.add(vgt)
        db.commit()
        db.refresh(vgt)
        db.add(PortfolioPosition(company_id=vgt.id, quantity=5, avg_cost_basis=400))
        db.commit()

        monkeypatch.setattr("app.routers.portfolio.fetch_alpha_quotes", lambda tickers: {
            "VGT": {"price": 450.0, "source": "alpha_vantage", "status": "live"},
        })

        response = _answer_question("what is my gain on VGT?", db=db)
        assert "VGT is up 250.00" in response.answer
        assert response.data["plan"]["use_portfolio"] is True
        assert "portfolio_positions" in response.citations


def test_answer_question_portfolio_gain_aggregates_duplicate_symbol_lots(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        vgt = Company(ticker="VGT", name="VGT ETF", asset_type="etf")
        db.add(vgt)
        db.commit()
        db.refresh(vgt)
        db.add_all(
            [
                PortfolioPosition(company_id=vgt.id, quantity=5, avg_cost_basis=400),
                PortfolioPosition(company_id=vgt.id, quantity=2, avg_cost_basis=420),
            ]
        )
        db.commit()

        monkeypatch.setattr("app.routers.portfolio.fetch_alpha_quotes", lambda tickers: {
            "VGT": {"price": 450.0, "source": "alpha_vantage", "status": "live"},
        })

        response = _answer_question("what is my gain on VGT?", db=db)
        assert "VGT is up 310.00" in response.answer
        assert "across 2 lots" in response.answer
        assert response.data["plan"]["use_portfolio"] is True
        assert "portfolio_positions" in response.citations


def test_answer_question_compares_etf_holdings_to_stock_holdings(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        aapl = Company(ticker="AAPL", name="Apple Inc.", asset_type="equity")
        vgt = Company(ticker="VGT", name="VGT ETF", asset_type="etf")
        db.add_all([aapl, vgt])
        db.commit()
        db.refresh(aapl)
        db.refresh(vgt)
        db.add_all(
            [
                PortfolioPosition(company_id=aapl.id, quantity=10, avg_cost_basis=150),
                PortfolioPosition(company_id=vgt.id, quantity=5, avg_cost_basis=400),
            ]
        )
        db.commit()

        monkeypatch.setattr("app.routers.portfolio.fetch_alpha_quotes", lambda tickers: {
            "AAPL": {"price": 200.0, "source": "alpha_vantage", "status": "live"},
            "VGT": {"price": 450.0, "source": "alpha_vantage", "status": "live"},
        })

        response = _answer_question("compare my ETF holdings to my stock holdings", db=db)
        assert "Portfolio asset mix:" in response.answer
        assert "ETF holdings" in response.answer
        assert "Stock holdings" in response.answer
        assert response.data["plan"]["use_portfolio"] is True


def test_answer_question_uses_context_company_for_transcript_followup(monkeypatch):
    company = SimpleNamespace(ticker="DOW", name="DOW INC.", id=77)
    monkeypatch.setattr(
        "app.routers.qa._build_plan",
        lambda question: {
            "companies": [],
            "actions": ["company_snapshot", "transcript_context"],
            "years": 10,
            "compare": False,
            "response_mode": "grounded",
        },
    )
    monkeypatch.setattr(
        "app.routers.qa._resolve_companies_from_plan",
        lambda db, question, plan: ([], [], []),
    )
    monkeypatch.setattr(
        "app.routers.qa._resolve_company_candidate",
        lambda db, question, candidate: (company, 1.0, "exact_ticker"),
    )

    def fake_execute_action(db, company_obj, action, years, question):
        if action == "company_snapshot":
            return (
                {
                    "ticker": "DOW",
                    "company_name": "DOW INC.",
                    "latest_fiscal_year": 2025,
                },
                ["companies"],
                "snapshot",
                [],
            )
        if action == "transcript_context":
            return (
                {
                    "available": True,
                    "ticker": "DOW",
                    "fiscal_year": 2025,
                    "fiscal_quarter": 4,
                    "source_provider": "alpha_vantage",
                    "source_url": "https://example.com/dow-transcript",
                    "segments": [{"segment_index": 0, "speaker": "CEO", "text": "Prepared remarks"}],
                },
                ["earnings_call_transcripts", "earnings_call_transcript_segments"],
                "transcript context",
                [],
            )
        return ({}, [], "noop", [])

    monkeypatch.setattr("app.routers.qa._execute_action", fake_execute_action)

    response = _answer_question(
        "great do you have access to their last earnings call?",
        db=SimpleNamespace(),
        context_company="DOW",
    )
    plan = response.data.get("plan", {})
    assert plan.get("companies_resolved") == ["DOW"]
    assert any("Applied context company fallback" in t for t in (response.trace or []))


def test_answer_question_uses_thread_context_for_transcript_followup(monkeypatch):
    company = SimpleNamespace(ticker="DOW", name="DOW INC.", id=77)
    monkeypatch.setattr(
        "app.routers.qa._build_plan",
        lambda question: {
            "companies": [],
            "actions": ["company_snapshot", "transcript_context"],
            "years": 10,
            "compare": False,
            "response_mode": "grounded",
        },
    )
    monkeypatch.setattr(
        "app.routers.qa._resolve_companies_from_plan",
        lambda db, question, plan: ([], [], []),
    )
    monkeypatch.setattr(
        "app.routers.qa._load_thread_context_company",
        lambda db, thread_id: company if thread_id == "thread-1" else None,
    )
    monkeypatch.setattr(
        "app.routers.qa._resolve_company_candidate",
        lambda db, question, candidate: (company, 1.0, "exact_ticker"),
    )

    def fake_execute_action(db, company_obj, action, years, question):
        if action == "company_snapshot":
            return (
                {
                    "ticker": "DOW",
                    "company_name": "DOW INC.",
                    "latest_fiscal_year": 2025,
                },
                ["companies"],
                "snapshot",
                [],
            )
        if action == "transcript_context":
            return (
                {
                    "available": True,
                    "ticker": "DOW",
                    "fiscal_year": 2025,
                    "fiscal_quarter": 4,
                    "source_provider": "alpha_vantage",
                    "segments": [{"segment_index": 0, "speaker": "CEO", "text": "Prepared remarks"}],
                },
                ["earnings_call_transcripts", "earnings_call_transcript_segments"],
                "transcript context",
                [],
            )
        return ({}, [], "noop", [])

    monkeypatch.setattr("app.routers.qa._execute_action", fake_execute_action)

    response = _answer_question(
        "do you have access to their last earnings call?",
        db=SimpleNamespace(),
        thread_id="thread-1",
    )
    plan = response.data.get("plan", {})
    assert plan.get("companies_resolved") == ["DOW"]
    assert any("fallback (thread)" in t.lower() for t in (response.trace or []))


def test_resolve_companies_compare_returns_both_when_confident(monkeypatch):
    nvda = SimpleNamespace(id=9, ticker="NVDA", name="NVIDIA CORP")
    amd = SimpleNamespace(id=43, ticker="AMD", name="ADVANCED MICRO DEVICES INC")

    def fake_resolver(db, question, candidate):
        key = candidate.upper()
        if key == "NVDA":
            return nvda, 1.0, "exact_ticker"
        if key == "AMD":
            return amd, 1.0, "exact_ticker"
        return None, 0.0, "no_name_match"

    monkeypatch.setattr("app.routers.qa._resolve_company_candidate", fake_resolver)
    resolved, unresolved, diagnostics = _resolve_companies_from_plan(
        db=SimpleNamespace(),
        question="nvda vs amd",
        plan={"companies": ["NVDA", "AMD"]},
    )
    assert [c.ticker for c in resolved] == ["NVDA", "AMD"]
    assert unresolved == []
    assert [d["decision"] for d in diagnostics] == ["resolved", "resolved"]

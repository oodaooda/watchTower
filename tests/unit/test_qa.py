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
)
from types import SimpleNamespace


def test_extract_ticker_skips_common_words():
    assert _extract_ticker("what was it's earnings for the last 10 years") is None


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


def test_build_plan_compare_infers_compare_mode():
    plan = _build_plan("compare nvda versus tsmc")
    assert plan["compare"] is True


def test_build_plan_latest_news_of_single_ticker_keeps_only_ticker():
    plan = _build_plan("what's the latest news of qcls?")
    assert [c.upper() for c in plan["companies"]] == ["QCLS"]


def test_extract_tickers_ignores_plain_words_in_news_question():
    tickers = _extract_tickers("what's the latest news you have on qcls")
    assert "QCLS" in tickers
    assert "ON" not in tickers
    assert "HAVE" not in tickers


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

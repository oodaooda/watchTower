from app.routers.qa import _extract_ticker, _extract_company_keywords


def test_extract_ticker_skips_common_words():
    assert _extract_ticker("what was it's earnings for the last 10 years") is None


def test_extract_keywords_from_company_name():
    keywords = _extract_company_keywords("what was apples earnings for the last 10 years")
    assert "apple" in keywords

from types import SimpleNamespace

from app.services.llm_usage import compute_usage_cost, extract_openai_usage


def test_extract_openai_usage_chat_completions():
    response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=30,
            total_tokens=150,
            prompt_tokens_details=SimpleNamespace(cached_tokens=20),
        )
    )
    usage = extract_openai_usage("chat_completions", response)
    assert usage["input_tokens"] == 120
    assert usage["output_tokens"] == 30
    assert usage["total_tokens"] == 150
    assert usage["cached_input_tokens"] == 20


def test_extract_openai_usage_responses_api():
    response = SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=400,
            output_tokens=50,
            total_tokens=450,
            input_tokens_details=SimpleNamespace(cached_tokens=80),
        )
    )
    usage = extract_openai_usage("responses", response)
    assert usage["input_tokens"] == 400
    assert usage["output_tokens"] == 50
    assert usage["total_tokens"] == 450
    assert usage["cached_input_tokens"] == 80


def test_compute_usage_cost_uses_per_million_rates():
    cost = compute_usage_cost(
        input_tokens=1_500_000,
        output_tokens=500_000,
        cached_input_tokens=250_000,
        input_per_million=2.0,
        output_per_million=8.0,
        cache_read_per_million=0.5,
    )
    assert round(cost, 6) == round((1.5 * 2.0) + (0.5 * 8.0) + (0.25 * 0.5), 6)

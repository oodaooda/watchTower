from app.modeling.forecaster import Assumptions, generate_forecast


def test_generate_forecast_basic():
    assumptions = Assumptions(
        scenario="base",
        revenue_cagr_start=0.1,
        revenue_cagr_floor=0.04,
        revenue_decay_quarters=8,
        gross_margin_target=0.5,
        gross_margin_glide_quarters=8,
        rnd_pct=0.1,
        sm_pct=0.1,
        ga_pct=0.05,
        tax_rate=0.2,
        interest_pct_revenue=0.01,
        dilution_pct_annual=0.02,
        seasonality_mode="off",
        driver_blend_start_weight=0.3,
        driver_blend_end_weight=0.7,
        driver_blend_ramp_quarters=4,
    )

    historical = [
        {"fiscal_year": 2023, "fiscal_period": "Q4", "revenue": 1000, "gross_profit": 500, "shares_outstanding": 100}
    ]

    rows = generate_forecast(assumptions, historical, kpis=[], horizon_quarters=4)
    assert len(rows) == 4
    assert rows[0]["revenue"] is not None
    assert rows[0]["gross_profit"] is not None

from app.valuation.dcf import dcf_two_stage


def test_dcf_two_stage_basic():
    result = dcf_two_stage(
        fcf0=100,
        g1=0.08,
        n=5,
        gT=0.03,
        r=0.09,
        fade=3,
        net_cash=10,
        shares_out=10,
    )
    assert "error" not in result
    assert result["equity_value"] > 0
    assert result["per_share"] is not None


def test_dcf_invalid_inputs():
    result = dcf_two_stage(fcf0=-1, g1=0.08, n=5, gT=0.03, r=0.09)
    assert "error" in result

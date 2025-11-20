"""Pydantic response/request schemas for watchTower API.

These map ORM rows to API-friendly shapes.
"""
from __future__ import annotations

from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict, Field

# ---------- Companies ----------
class CompanyOut(BaseModel):
    id: int
    ticker: str
    name: Optional[str] = None
    cik: Optional[int] = None
    sic: Optional[str] = None
    industry_name: Optional[str] = None
    exchange: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# ---------- Screening ----------
class ScreenResultItem(BaseModel):
    company_id: int
    ticker: str
    name: str
    industry: Optional[str] = None
    fiscal_year: int
    cash_debt_ratio: Optional[float] = None
    growth_consistency: Optional[int] = None
    rev_cagr_5y: Optional[float] = None
    ni_cagr_5y: Optional[float] = None
    fcf: Optional[float] = None
    fcf_cagr_5y: Optional[float] = None
    pe_ttm: Optional[float] = None
    price: Optional[float] = None
    cik: Optional[int] = None

# ---------- Financials ----------
class FinancialAnnualOut(BaseModel):
    fiscal_year: int
    source: Optional[str] = None

    # Income Statement
    revenue: Optional[float] = None
    cost_of_revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    research_and_development: Optional[float] = None
    selling_general_admin: Optional[float] = None
    sales_and_marketing: Optional[float] = None
    general_and_administrative: Optional[float] = None
    operating_income: Optional[float] = None
    interest_expense: Optional[float] = None
    other_income_expense: Optional[float] = None
    income_tax_expense: Optional[float] = None
    net_income: Optional[float] = None
    eps_diluted: Optional[float] = None
    # Balance Sheet
    assets_total: Optional[float] = None
    liabilities_current: Optional[float] = None
    liabilities_longterm: Optional[float] = None
    equity_total: Optional[float] = None
    inventories: Optional[float] = None
    accounts_receivable: Optional[float] = None
    accounts_payable: Optional[float] = None
    cash_and_sti: Optional[float] = None
    total_debt: Optional[float] = None
    shares_outstanding: Optional[float] = None
    # Cash Flow
    cfo: Optional[float] = None
    capex: Optional[float] = None
    fcf: Optional[float] = None  # computed in the router
    depreciation_amortization: Optional[float] = None
    share_based_comp: Optional[float] = None
    dividends_paid: Optional[float] = None
    share_repurchases: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

# ---------- financial Quarterly -------

class FinancialQuarterlyOut(BaseModel):
    fiscal_year: int
    fiscal_period: str
    source: Optional[str] = None
    revenue: Optional[float]
    cost_of_revenue: Optional[float] = None
    gross_profit: Optional[float]
    research_and_development: Optional[float] = None
    selling_general_admin: Optional[float] = None
    sales_and_marketing: Optional[float] = None
    general_and_administrative: Optional[float] = None
    operating_income: Optional[float]
    interest_expense: Optional[float] = None
    other_income_expense: Optional[float] = None
    income_tax_expense: Optional[float] = None
    net_income: Optional[float]
    eps_diluted: Optional[float] = None
    assets_total: Optional[float]
    liabilities_current: Optional[float] = None
    liabilities_longterm: Optional[float] = None
    equity_total: Optional[float]
    cash_and_sti: Optional[float]
    total_debt: Optional[float]
    shares_outstanding: Optional[float]
    cfo: Optional[float]
    capex: Optional[float]
    fcf: Optional[float]
    depreciation_amortization: Optional[float]
    share_based_comp: Optional[float]
    dividends_paid: Optional[float]
    share_repurchases: Optional[float]
    inventories: Optional[float]
    accounts_receivable: Optional[float]
    accounts_payable: Optional[float]

    model_config = ConfigDict(from_attributes=True)

    model_config = ConfigDict(from_attributes=True)


# ---------- Metrics ----------
class MetricsAnnualOut(BaseModel):
    fiscal_year: int
    pe_ttm: Optional[float] = None
    cash_debt_ratio: Optional[float] = None
    growth_consistency: Optional[int] = None
    rev_cagr_5y: Optional[float] = None
    ni_cagr_5y: Optional[float] = None
    piotroski_f: Optional[int] = None
    altman_z: Optional[float] = None

# ---------- Definitions / Glossary ----------
class DefinitionOut(BaseModel):
    key: str
    title: str
    body_md: str


# ---------- Company Profile ----------
class ProfileSeriesPoint(BaseModel):
    fiscal_year: int
    value: Optional[float] = None


class ProfileSeries(BaseModel):
    price: List[ProfileSeriesPoint] = Field(default_factory=list)
    revenue: List[ProfileSeriesPoint] = Field(default_factory=list)
    net_income: List[ProfileSeriesPoint] = Field(default_factory=list)
    cash: List[ProfileSeriesPoint] = Field(default_factory=list)
    debt: List[ProfileSeriesPoint] = Field(default_factory=list)
    shares: List[ProfileSeriesPoint] = Field(default_factory=list)


class RiskMetricsOut(BaseModel):
    alpha: Optional[float] = None
    alpha_annual: Optional[float] = None
    beta: Optional[float] = None
    benchmark: Optional[str] = None
    risk_free_rate: Optional[float] = None
    lookback_days: Optional[int] = None
    data_points: Optional[int] = None
    computed_at: Optional[str] = None


class CompanyProfileOut(BaseModel):
    company: CompanyOut
    latest_fiscal_year: Optional[int] = None
    price: Optional[float] = None
    market_cap: Optional[float] = None
    valuation: Dict[str, Optional[float]] = Field(default_factory=dict)
    financial_strength: Dict[str, Optional[float]] = Field(default_factory=dict)
    profitability: Dict[str, Optional[float]] = Field(default_factory=dict)
    growth: Dict[str, Optional[float]] = Field(default_factory=dict)
    quality: Dict[str, Optional[float]] = Field(default_factory=dict)
    balance_sheet: Dict[str, Optional[float]] = Field(default_factory=dict)
    cash_flow: Dict[str, Optional[float]] = Field(default_factory=dict)
    series: ProfileSeries = Field(default_factory=ProfileSeries)
    risk_metrics: Optional[RiskMetricsOut] = None


class FavoriteCompanyItem(BaseModel):
    company_id: int
    ticker: str
    name: Optional[str] = None
    industry: Optional[str] = None
    price: Optional[float] = None
    change_percent: Optional[float] = None
    pe: Optional[float] = None
    eps: Optional[float] = None
    market_cap: Optional[float] = None
    notes: Optional[str] = None
    source: Optional[str] = None

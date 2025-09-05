"""Pydantic response/request schemas for watchTower API.

These map ORM rows to API-friendly shapes.
"""
from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, ConfigDict

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

    # Income Statement
    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    eps_diluted: Optional[float] = None

    # Balance Sheet
    assets_total: Optional[float] = None
    equity_total: Optional[float] = None
    cash_and_sti: Optional[float] = None
    total_debt: Optional[float] = None
    shares_outstanding: Optional[float] = None

    # Cash Flow
    cfo: Optional[float] = None
    capex: Optional[float] = None
    fcf: Optional[float] = None  # computed in the router

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

"""SQLAlchemy ORM models for watchTower.

Tables:
- companies
- financials_annual
- prices_annual
- metrics_annual
- definitions
- fact_provenance
"""
from __future__ import annotations
from sqlalchemy.sql import func

from datetime import datetime, date
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Index,
    Column,
    PrimaryKeyConstraint,    
    )
from sqlalchemy.orm import Mapped, mapped_column, relationship



from app.core.db import Base
from datetime import datetime

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    ticker = Column(String, index=True, unique=False)
    name = Column(String)
    cik = Column(BigInteger, index=True, unique=False)  # keep non-unique; SEC symbols can map oddly
    sic = Column(String, nullable=True)
    industry_name = Column(String, nullable=True)
    exchange = Column(String, nullable=True)
    status = Column(String, default="active")
    delisted_on = Column(Date, nullable=True)
    currency = Column(String, default="USD")
    fiscal_year_end_month = Column(Integer, nullable=True)
    is_tracked = Column(Boolean, default=False)
    track_reason = Column(String, nullable=True)
    tracked_since = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    description = Column(String, nullable=True)




class FinancialAnnual(Base):
    __tablename__ = "financials_annual"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    fiscal_year = Column(Integer, nullable=False, index=True)
    fiscal_period = Column(String, nullable=False)
    report_date = Column(Date)

    # Income Statement
    revenue = Column(Numeric(20, 4))
    cost_of_revenue = Column(Numeric(20, 4))
    gross_profit = Column(Numeric(20, 4))
    research_and_development = Column(Numeric(20, 4))
    selling_general_admin = Column(Numeric(20, 4))
    sales_and_marketing = Column(Numeric(20, 4))
    general_and_administrative = Column(Numeric(20, 4))
    operating_income = Column(Numeric(20, 4))
    interest_expense = Column(Numeric(20, 4))
    other_income_expense = Column(Numeric(20, 4))
    income_tax_expense = Column(Numeric(20, 4))
    net_income = Column(Numeric(20, 4))



    #Balance Sheet
    assets_total = Column(Numeric(20, 4))
    liabilities_current = Column(Numeric(20, 4))
    liabilities_longterm = Column(Numeric(20, 4))
    equity_total = Column(Numeric(20, 4))
    inventories = Column(Numeric(20, 4))
    accounts_receivable = Column(Numeric(20, 4))
    accounts_payable = Column(Numeric(20, 4))
    cash_and_sti = Column(Numeric(20, 4))
    total_debt = Column(Numeric(20, 4))
    shares_outstanding = Column(Numeric(20, 4))

    # Cash Flow
    cfo = Column(Numeric(20, 4))
    capex = Column(Numeric(20, 4))
    depreciation_amortization = Column(Numeric(20, 4))
    share_based_comp = Column(Numeric(20, 4))
    dividends_paid = Column(Numeric(20, 4))
    share_repurchases = Column(Numeric(20, 4))
    fcf = Column(Numeric(20, 4))                     


    # NEW: map the columns you added with ALTER TABLE
    source = Column(String, nullable=False)
    xbrl_confidence = Column(Numeric(6, 4))

    __table_args__ = (
        Index("ix_financials_company_year", "company_id", "fiscal_year"),
        UniqueConstraint("company_id", "fiscal_year", name="uq_financials_company_year_idx"),
        UniqueConstraint("company_id", "fiscal_year", "source", name="uq_financials_company_year_source"),
    )

class FinancialQuarterly(Base):
    __tablename__ = "financials_quarterly"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    fiscal_year = Column(Integer, nullable=False, index=True)
    fiscal_period = Column(String, nullable=False)  # e.g. "Q1", "Q2", "Q3", "Q4"
    report_date = Column(Date)

    # Income Statement
    revenue = Column(Numeric(20, 4))
    cost_of_revenue = Column(Numeric(20, 4))
    gross_profit = Column(Numeric(20, 4))
    research_and_development = Column(Numeric(20, 4))
    selling_general_admin = Column(Numeric(20, 4))
    sales_and_marketing = Column(Numeric(20, 4))
    general_and_administrative = Column(Numeric(20, 4))
    operating_income = Column(Numeric(20, 4))
    interest_expense = Column(Numeric(20, 4))
    other_income_expense = Column(Numeric(20, 4))
    income_tax_expense = Column(Numeric(20, 4))
    net_income = Column(Numeric(20, 4))

    # Balance Sheet
    assets_total = Column(Numeric(20, 4))
    liabilities_current = Column(Numeric(20, 4))
    liabilities_longterm = Column(Numeric(20, 4))
    equity_total = Column(Numeric(20, 4))
    inventories = Column(Numeric(20, 4))
    accounts_receivable = Column(Numeric(20, 4))
    accounts_payable = Column(Numeric(20, 4))
    cash_and_sti = Column(Numeric(20, 4))
    total_debt = Column(Numeric(20, 4))
    shares_outstanding = Column(Numeric(20, 4))

    # Cash Flow
    cfo = Column(Numeric(20, 4))
    capex = Column(Numeric(20, 4))
    depreciation_amortization = Column(Numeric(20, 4))
    share_based_comp = Column(Numeric(20, 4))
    dividends_paid = Column(Numeric(20, 4))
    share_repurchases = Column(Numeric(20, 4))
    fcf = Column(Numeric(20, 4))

    # Meta
    source = Column(String, nullable=False)
    xbrl_confidence = Column(Numeric(6, 4))

    __table_args__ = (
        Index("ix_financials_q_company_year_period", "company_id", "fiscal_year", "fiscal_period"),
        UniqueConstraint("company_id", "fiscal_year", "fiscal_period", name="uq_financials_q_company_year_period"),
    )






# app/core/models.py
from sqlalchemy import Column, Integer, ForeignKey, Numeric, String, UniqueConstraint, Float

class PriceAnnual(Base):
    __tablename__ = "prices_annual"

    id = Column(Integer, primary_key=True, autoincrement=True)   
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    fiscal_year = Column(Integer, nullable=False, index=True)
    close_price = Column(Numeric(20, 4))
    eps = Column(Float) 
    pe_ttm = Column(Numeric(20, 4))
    source = Column(String)

    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_year", name="uq_prices_annual_company_year"),
    )




class MetricsAnnual(Base):
    __tablename__ = "metrics_annual"

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, primary_key=True)

    fcf: Mapped[float | None] = mapped_column(Numeric(20, 4))
    gross_margin: Mapped[float | None] = mapped_column(Numeric(8, 4))
    op_margin: Mapped[float | None] = mapped_column(Numeric(8, 4))
    roe: Mapped[float | None] = mapped_column(Numeric(8, 4))
    roic: Mapped[float | None] = mapped_column(Numeric(8, 4))
    debt_ebitda: Mapped[float | None] = mapped_column(Numeric(12, 4))
    interest_coverage: Mapped[float | None] = mapped_column(Numeric(12, 4))

    rev_yoy: Mapped[float | None] = mapped_column(Numeric(8, 4))
    ni_yoy: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rev_cagr_5y: Mapped[float | None] = mapped_column(Numeric(8, 4))
    ni_cagr_5y: Mapped[float | None] = mapped_column(Numeric(8, 4))

    growth_consistency: Mapped[int | None] = mapped_column(Integer)
    cash_debt_ratio: Mapped[float | None] = mapped_column(Numeric(12, 4))
    piotroski_f: Mapped[int | None] = mapped_column(Integer)
    altman_z: Mapped[float | None] = mapped_column(Numeric(12, 4))
    ttm_eps: Mapped[float | None] = mapped_column(Numeric(12, 4))

    data_quality_score: Mapped[float | None] = mapped_column(Numeric(6, 3))
    has_ttm: Mapped[bool | None] = mapped_column(Boolean, default=False)

    fcf = Column(Numeric(20,4), nullable=True)
    fcf_cagr_5y = Column(Numeric(20,6), nullable=True)
    shares_outstanding = Column(Numeric(20,4), nullable=True)

    __table_args__ = (
        Index("ix_metrics_pe", "fiscal_year", "company_id"),
        Index("ix_metrics_cashdebt", "cash_debt_ratio"),
        Index("ix_metrics_consistency", "growth_consistency"),
        Index("ix_metrics_cagr", "rev_cagr_5y", "ni_cagr_5y"),
        UniqueConstraint("company_id", "fiscal_year", name="uq_metrics_annual_company_year"),
    )


class Definition(Base):
    __tablename__ = "definitions"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    body_md: Mapped[str] = mapped_column(String)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    key_prefix = Column(String, nullable=False)
    key_hash = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    revoked_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_api_keys_active", "revoked_at"),
    )


class ModelingAssumption(Base):
    __tablename__ = "modeling_assumptions"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    scenario = Column(String, nullable=False)

    revenue_cagr_start = Column(Numeric(8, 4))
    revenue_cagr_floor = Column(Numeric(8, 4))
    revenue_decay_quarters = Column(Integer)

    gross_margin_target = Column(Numeric(8, 4))
    gross_margin_glide_quarters = Column(Integer)

    rnd_pct = Column(Numeric(8, 4))
    sm_pct = Column(Numeric(8, 4))
    ga_pct = Column(Numeric(8, 4))

    tax_rate = Column(Numeric(8, 4))
    interest_pct_revenue = Column(Numeric(8, 4))
    dilution_pct_annual = Column(Numeric(8, 4))

    seasonality_mode = Column(String, default="auto")
    driver_blend_start_weight = Column(Numeric(8, 4))
    driver_blend_end_weight = Column(Numeric(8, 4))
    driver_blend_ramp_quarters = Column(Integer)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "scenario", name="uq_modeling_assumptions_company_scenario"),
        Index("ix_modeling_assumptions_company", "company_id"),
    )


class ModelingKPI(Base):
    __tablename__ = "modeling_kpis"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    fiscal_year = Column(Integer, nullable=False, index=True)
    fiscal_period = Column(String, nullable=False)

    mau = Column(Numeric(20, 4))
    dau = Column(Numeric(20, 4))
    paid_subs = Column(Numeric(20, 4))
    paid_conversion_pct = Column(Numeric(8, 4))
    arpu = Column(Numeric(20, 4))
    churn_pct = Column(Numeric(8, 4))

    source = Column(String, default="manual")

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_year", "fiscal_period", name="uq_modeling_kpis_company_year_period"),
        Index("ix_modeling_kpis_company_year_period", "company_id", "fiscal_year", "fiscal_period"),
    )


class FavoriteCompany(Base):
    __tablename__ = "favorite_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    company = relationship("Company")


class CompanyRiskMetric(Base):
    __tablename__ = "company_risk_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)
    beta: Mapped[float | None] = mapped_column(Numeric(12, 6))
    alpha: Mapped[float | None] = mapped_column(Numeric(12, 6))
    alpha_annual: Mapped[float | None] = mapped_column(Numeric(12, 6))
    alpha_annual_1y: Mapped[float | None] = mapped_column(Numeric(12, 6))
    alpha_annual_6m: Mapped[float | None] = mapped_column(Numeric(12, 6))
    alpha_annual_3m: Mapped[float | None] = mapped_column(Numeric(12, 6))
    benchmark: Mapped[str] = mapped_column(String(32), default="SPY", nullable=False)
    risk_free_rate: Mapped[float | None] = mapped_column(Numeric(8, 6))
    lookback_days: Mapped[int | None] = mapped_column(Integer)
    data_points: Mapped[int | None] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    company = relationship("Company")


class FactProvenance(Base):
    __tablename__ = "fact_provenance"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    financial_id: Mapped[int] = mapped_column(
        ForeignKey("financials_annual.id", ondelete="CASCADE"), index=True
    )
    xbrl_tag: Mapped[str | None] = mapped_column(String)
    unit: Mapped[str | None] = mapped_column(String)
    accession: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        Index("ix_prov_financial", "financial_id"),
    )


# -------- Pharma Tracking --------

class PharmaCompany(Base):
    __tablename__ = "pharma_companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    ticker = Column(String, nullable=False, index=True, unique=True)
    lead_sponsor = Column(String, nullable=True)
    description = Column(String, nullable=True)
    last_refreshed = Column(DateTime, nullable=True)
    included_manually = Column(Boolean, default=False)

    company = relationship("Company")
    drugs = relationship("PharmaDrug", back_populates="pharma_company", cascade="all, delete-orphan")


class PharmaDrug(Base):
    __tablename__ = "pharma_drugs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pharma_company_id = Column(
        Integer,
        ForeignKey("pharma_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String, nullable=False)
    indication = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    pharma_company = relationship("PharmaCompany", back_populates="drugs")
    trials = relationship("PharmaTrial", back_populates="drug", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("pharma_company_id", "name", name="uq_pharma_drug_company_name"),
    )


class PharmaTrial(Base):
    __tablename__ = "pharma_trials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pharma_drug_id = Column(
        Integer,
        ForeignKey("pharma_drugs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nct_id = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=True)
    phase = Column(String, nullable=True)
    status = Column(String, nullable=True)
    condition = Column(String, nullable=True)
    estimated_completion = Column(Date, nullable=True)
    start_date = Column(Date, nullable=True)
    enrollment = Column(Integer, nullable=True)
    success_probability = Column(Numeric(5, 2), nullable=True)
    sponsor = Column(String, nullable=True)
    location = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    last_refreshed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    has_results = Column(Boolean, nullable=True)
    why_stopped = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    status_last_verified = Column(Date, nullable=True)

    drug = relationship("PharmaDrug", back_populates="trials")

    __table_args__ = (
        Index("ix_pharma_trial_phase_status", "phase", "status"),
    )


class PharmaDrugMetadata(Base):
    __tablename__ = "pharma_drug_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    drug_name = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    label = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    phase_override = Column(String, nullable=True)
    is_commercial = Column(Boolean, nullable=False, default=False)
    peak_sales = Column(Numeric(14, 2), nullable=True)
    peak_sales_currency = Column(String(3), nullable=True)
    peak_sales_year = Column(Integer, nullable=True)
    probability_override = Column(Numeric(5, 2), nullable=True)
    segment = Column(String, nullable=True)

    sales = relationship(
        "PharmaDrugSales",
        back_populates="metadata_entry",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("ticker", "drug_name", name="uq_pharma_drug_metadata_ticker_name"),
    )


class PharmaDrugSales(Base):
    __tablename__ = "pharma_drug_sales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metadata_id = Column(Integer, ForeignKey("pharma_drug_metadata.id", ondelete="CASCADE"), nullable=False, index=True)
    period_type = Column(String(16), nullable=False)
    period_year = Column(Integer, nullable=False)
    period_quarter = Column(Integer, nullable=True)
    revenue = Column(Numeric(16, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    source = Column(String, nullable=True)

    metadata_entry = relationship("PharmaDrugMetadata", back_populates="sales")

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
    operating_income = Column(Numeric(20, 4))
    interest_expense = Column(Numeric(20, 4))
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
    operating_income = Column(Numeric(20, 4))
    interest_expense = Column(Numeric(20, 4))
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

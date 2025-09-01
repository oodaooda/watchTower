// ui/src/types.ts
export type ScreenRow = {
  company_id: number;
  ticker: string;
  name: string;
  industry: string | null;
  fiscal_year: number;
  cash_debt_ratio: number | null;
  growth_consistency: number | null;
  rev_cagr_5y: number | null;
  ni_cagr_5y: number | null;
  fcf: number | null;
  fcf_cagr_5y: number | null;
  pe_ttm: number | null;
  // NEW (server now provides price)
  price?: number | null;
  // NEW (UI may enrich with valuation)
  fair_value_per_share?: number | null;
  upside_vs_price?: number | null;
};

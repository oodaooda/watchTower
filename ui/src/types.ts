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
  pe_ttm?: number | null;
};

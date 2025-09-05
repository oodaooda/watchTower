// ui/src/lib/api.ts
export const API_BASE =
  import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

/** Screener row shape consumed by ResultsTable */
export type ScreenRow = {
  company_id: number;
  fiscal_year: number;
  ticker: string;
  name: string;
  industry?: string | null;
  cash_debt_ratio?: number | null;
  growth_consistency?: number | null;
  rev_cagr_5y?: number | null;
  ni_cagr_5y?: number | null;
  fcf?: number | null;
  fcf_cagr_5y?: number | null;
  // valuation data merged into row (Price / FV / Upside / P/E)
  price?: number | null;
  fair_value_per_share?: number | null;
  upside_vs_price?: number | null;
  pe_ttm?: number | null;
};

/** Screener query params */
export type ScreenParams = Partial<{
  pe_max: number;
  cash_debt_min: number;
  growth_consistency_min: number;
  rev_cagr_min: number;
  ni_cagr_min: number;
  fcf_cagr_min: number;
  industry: string;
  year: number;
  limit: number;
  offset: number;
}>;

export async function fetchScreen(params: ScreenParams): Promise<ScreenRow[]> {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  });
  const res = await fetch(`${API_BASE}/screen?${q.toString()}`);
  if (!res.ok) throw new Error(`screen ${res.status}`);
  return res.json();
}

/** DCF response shape consumed by ValuationModal */
export type DCFProjection = { year: number; fcf: number; growth: number; pv_fcf: number };
export type DCFResponse = {
  base_fcf: number;
  enterprise_value: number;
  equity_value: number;
  fair_value_per_share: number | null;
  price: number | null;
  upside_vs_price: number | null;
  terminal_value_pv: number;
  projections: DCFProjection[];
  inputs?: {
    years?: number;
    discount_rate?: number;
    start_growth?: number;
    terminal_growth?: number;
  };
};

export async function fetchDCF(args: {
  ticker: string;
  years?: number;
  discount_rate?: number;
  start_growth?: number;
  terminal_growth?: number;
}): Promise<DCFResponse> {
  const q = new URLSearchParams({ ticker: args.ticker });
  if (args.years != null) q.set("years", String(args.years));
  if (args.discount_rate != null) q.set("discount_rate", String(args.discount_rate));
  if (args.start_growth != null) q.set("start_growth", String(args.start_growth));
  if (args.terminal_growth != null) q.set("terminal_growth", String(args.terminal_growth));

  const res = await fetch(`${API_BASE}/valuation/dcf?${q.toString()}`);
  if (!res.ok) throw new Error(`dcf ${res.status}`);
  return res.json();
}

/** Optional helper if you show Price/FV quickly in the table */
export async function fetchValuationSummary(tickers: string[]): Promise<
  Array<{ ticker: string; price: number | null; fair_value_per_share: number | null; upside_vs_price: number | null }>
> {
  const res = await fetch(
    `${API_BASE}/valuation/summary?tickers=${encodeURIComponent(tickers.join(","))}`
  );
  if (!res.ok) throw new Error(`valuation/summary ${res.status}`);
  return res.json();
}

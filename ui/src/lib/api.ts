// ui/src/lib/api.ts
// Base URL for the FastAPI server
export const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

/* ---------- Types ---------- */

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
  cik?: number | null;
  price?: number | null;
  fair_value_per_share?: number | null;
  upside_vs_price?: number | null;
};

export type DCFResponse = {
  ticker: string;
  base_year: number;

  // NEW
  price: number | null;
  upside_vs_price: number | null;
  inputs: {
    years: number;
    discount_rate: number;
    start_growth: number;
    terminal_growth: number;
      inputs: { years: number; discount_rate: number; start_growth: number; terminal_growth: number };
  balance_sheet: { cash_and_sti: number | null; total_debt: number | null; shares_outstanding: number | null };
  base_fcf: number;
  projections: { year: number; fcf: number; growth: number; discount_factor: number; pv_fcf: number }[];
  terminal_value: number;
  terminal_value_pv: number;
  enterprise_value: number;
  equity_value: number;
  fair_value_per_share: number | null;
  };

  balance_sheet: {
    cash_and_sti: number | null;
    total_debt: number | null;
    shares_outstanding: number | null;
  };
  base_fcf: number;
  projections: {
    year: number;
    fcf: number;
    growth: number;
    discount_factor: number;
    pv_fcf: number;
  }[];
  terminal_value: number;
  terminal_value_pv: number;
  enterprise_value: number;
  equity_value: number;
  fair_value_per_share: number | null;
};

/* ---------- Helpers ---------- */

function buildQS(params: Record<string, unknown>) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  return qs.toString();
}

/* ---------- API calls ---------- */

// GET /screen
export async function fetchScreen(
  params: Record<string, string | number | undefined>
) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  });
  const res = await fetch(`${API_BASE}/screen?${qs.toString()}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export type ValuationSummary = {
  ticker: string;
  price: number | null;
  fair_value_per_share: number | null;
  upside_vs_price: number | null;
};

export async function fetchValuationSummary(
  tickers: string
): Promise<ValuationSummary[]> {
  const url = `${API_BASE}/valuation/summary?tickers=${encodeURIComponent(
    tickers
  )}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}


// GET /valuation/dcf
export async function fetchDCF(args: {
  ticker: string;
  years?: number;
  discount_rate?: number;
  start_growth?: number;
  terminal_growth?: number;
}): Promise<DCFResponse> {
  const qs = new URLSearchParams({ ticker: args.ticker });
  if (args.years != null) qs.set("years", String(args.years));
  if (args.discount_rate != null) qs.set("discount_rate", String(args.discount_rate));
  if (args.start_growth != null) qs.set("start_growth", String(args.start_growth));
  if (args.terminal_growth != null) qs.set("terminal_growth", String(args.terminal_growth));
  const res = await fetch(`${API_BASE}/valuation/dcf?${qs.toString()}`);
  if (!res.ok) throw new Error("dcf fetch failed");
  return (await res.json()) as DCFResponse;
}

export async function fetchValuation(
  ticker: string,
  params: { g1?: number; n?: number; fade?: number; gT?: number; r?: number }
): Promise<ValuationResponse> {
  const qs = new URLSearchParams({
    ticker,
    ...Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null).map(([k, v]) => [k, String(v)])
    ),
  });
  const res = await fetch(`${API_BASE}/valuation?${qs.toString()}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
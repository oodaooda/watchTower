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

// -------- Company News --------

export type CompanyNewsItem = {
  id?: string | null;
  title?: string | null;
  url?: string | null;
  summary?: string | null;
  source?: string | null;
  image_url?: string | null;
  published_at?: string | null;
  sentiment?: string | null;
  tickers?: string[];
};

export async function fetchCompanyNews(identifier: string, limit = 12): Promise<CompanyNewsItem[]> {
  const res = await fetch(`${API_BASE}/prices/${identifier}/news?limit=${limit}`);
  if (!res.ok) throw new Error(`news ${res.status}`);
  const data = await res.json();
  return data?.items ?? [];
}

// -------- Pharma endpoints --------

export type PharmaCompanyListItem = {
  ticker: string;
  company_id: number;
  name: string;
  industry?: string | null;
  lead_sponsor?: string | null;
  last_refreshed?: string | null;
  drug_count: number;
  trial_count: number;
};

export type PharmaCompanyListResponse = {
  total: number;
  items: PharmaCompanyListItem[];
  limit: number;
  offset: number;
};

export async function fetchPharmaCompanies(params: { search?: string; limit?: number; offset?: number }): Promise<PharmaCompanyListResponse> {
  const q = new URLSearchParams();
  if (params.search) q.set("search", params.search);
  if (params.limit != null) q.set("limit", String(params.limit));
  if (params.offset != null) q.set("offset", String(params.offset));

  const res = await fetch(`${API_BASE}/pharma/companies?${q.toString()}`);
  if (!res.ok) throw new Error(`pharma/companies ${res.status}`);
  return res.json();
}

export type PharmaTrial = {
  id?: number;
  nct_id?: string;
  title?: string | null;
  phase?: string | null;
  status?: string | null;
  category?: string | null;
  is_active?: boolean;
  condition?: string | null;
  estimated_completion?: string | null;
  start_date?: string | null;
  enrollment?: number | null;
  success_probability?: number | null;
  sponsor?: string | null;
  location?: string | null;
  source_url?: string | null;
  last_refreshed?: string | null;
  has_results?: boolean | null;
  why_stopped?: string | null;
  outcome?: string | null;
  status_last_verified?: string | null;
  data_source?: string | null;
};

export type PharmaDrug = {
  id?: number;
  name: string;
  display_name?: string | null;
  label?: string | null;
  indication?: string | null;
  summary: {
    stage?: string | null;
    status?: string | null;
    probability?: number | null;
    probability_source?: string | null;
    peak_sales?: number | null;
    peak_sales_currency?: string | null;
    peak_sales_year?: number | null;
    expected_value?: number | null;
    expected_value_currency?: string | null;
    is_commercial?: boolean;
    label?: string | null;
    active_trial_count: number;
    total_trial_count: number;
    primary_nct_id?: string | null;
    primary_estimated_completion?: string | null;
    primary_success_probability?: number | null;
    primary_start_date?: string | null;
    notes?: string | null;
    metadata_source?: string | null;
    segment?: string | null;
    sales?: {
      annual: Array<{ year: number; revenue: number | null; currency?: string | null; source?: string | null }>;
      quarterly: Array<{ year: number; quarter?: number | null; revenue: number | null; currency?: string | null; source?: string | null }>;
    };
  };
  sales?: {
    annual: Array<{ year: number; revenue: number | null; currency?: string | null; source?: string | null }>;
    quarterly: Array<{ year: number; quarter?: number | null; revenue: number | null; currency?: string | null; source?: string | null }>;
  };
  active_trials: PharmaTrial[];
  historical_trials: PharmaTrial[];
};

export type PharmaCompanyDetail = {
  company: {
    id: number;
    ticker: string;
    name: string;
    industry?: string | null;
    lead_sponsor?: string | null;
    last_refreshed?: string | null;
  };
  drugs: PharmaDrug[];
  legacy_drugs?: PharmaDrug[];
  live_drugs?: PharmaDrug[] | null;
  summary: {
    total_drugs: number;
    total_trials: number;
    active_trials: number;
    active_drug_count: number;
    commercial_assets: number;
    expected_value_by_currency: Record<string, number>;
    peak_sales_by_currency: Record<string, number>;
    latest_annual_sales_by_currency: Record<string, number>;
    legacy_drug_count?: number;
    legacy_trial_count?: number;
  };
  analysis?: string | null;
};

export async function fetchPharmaCompany(identifier: string, opts?: { force_live?: boolean }): Promise<PharmaCompanyDetail> {
  const q = new URLSearchParams();
  if (opts?.force_live) q.set("force_live", "true");
  const res = await fetch(`${API_BASE}/pharma/${identifier}?${q.toString()}`);
  if (!res.ok) throw new Error(`pharma/company ${res.status}`);
  return res.json();
}

export async function refreshPharmaCompany(identifier: string): Promise<{ ticker: string; refreshed_trials: number }> {
  const res = await fetch(`${API_BASE}/pharma/${identifier}/refresh`, { method: "POST" });
  if (!res.ok) throw new Error(`pharma/refresh ${res.status}`);
  return res.json();
}

export async function pharmaChat(message: string): Promise<string> {
  const res = await fetch(`${API_BASE}/pharma/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`pharma/chat ${res.status}`);
  const data = await res.json();
  return data.response as string;
}

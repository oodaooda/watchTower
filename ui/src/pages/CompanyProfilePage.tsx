import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import type { ReactNode } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  AreaChart,
  Area,
  Legend,
  BarChart,
  Bar,
  TooltipProps,
} from "recharts";

type SeriesPoint = { fiscal_year: number; value: number | null };

type CompanySummary = {
  id: number;
  ticker: string;
  name?: string | null;
  industry_name?: string | null;
  description?: string | null;
};

type MetricMap = Record<string, number | null | undefined>;

type ProfileSeries = {
  price?: SeriesPoint[];
  revenue?: SeriesPoint[];
  net_income?: SeriesPoint[];
  cash?: SeriesPoint[];
  debt?: SeriesPoint[];
  shares?: SeriesPoint[];
};

type CompanyProfile = {
  company: CompanySummary;
  latest_fiscal_year?: number | null;
  price?: number | null;
  market_cap?: number | null;
  valuation: MetricMap;
  financial_strength: MetricMap;
  profitability: MetricMap;
  growth: MetricMap;
  quality: MetricMap;
  balance_sheet: MetricMap;
  cash_flow: MetricMap;
  series: ProfileSeries;
};

type PriceHistoryRange = "1d" | "5d" | "1m" | "ytd" | "5y" | "max";

type PriceHistoryPoint = { ts: string; close: number | null };

type PriceHistoryResponse = {
  ticker: string;
  range: PriceHistoryRange;
  interval: string;
  source: string;
  points: PriceHistoryPoint[];
};

const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const btn =
  "h-8 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900 " +
  "hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

const btnGhost =
  "h-8 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-200 " +
  "hover:bg-zinc-100/60 dark:hover:bg-zinc-800/60 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

const rangeBtn =
  "px-2 py-1 rounded-md text-xs font-medium transition-colors border";
const rangeBtnActive =
  "bg-sky-600 text-white border-sky-600 shadow-sm";
const rangeBtnInactive =
  "bg-transparent text-zinc-500 border-zinc-300 dark:border-zinc-700 hover:bg-zinc-200/40 dark:hover:bg-zinc-800/40";

const PRICE_RANGES: PriceHistoryRange[] = ["1d", "5d", "1m", "ytd", "5y", "max"];

const PRICE_RANGE_LABEL: Record<PriceHistoryRange, string> = {
  "1d": "1D",
  "5d": "5D",
  "1m": "1M",
  "ytd": "YTD",
  "5y": "5Y",
  "max": "MAX",
};

const currencyCompactFmt = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 2,
});

const currencyFullFmt = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

const percentFmt = new Intl.NumberFormat(undefined, {
  style: "percent",
  maximumFractionDigits: 1,
  minimumFractionDigits: 1,
});

const numberFmt = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 2,
});

const fmtIntradayTick = new Intl.DateTimeFormat(undefined, {
  hour: "numeric",
  minute: "2-digit",
});

const fmtDayTick = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
});

const fmtMonthYearTick = new Intl.DateTimeFormat(undefined, {
  month: "short",
  year: "numeric",
});

const fmtYearTick = new Intl.DateTimeFormat(undefined, { year: "numeric" });

const fmtTooltipFull = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

const fmtTooltipDate = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
});

type MetricFormat =
  | "currency"
  | "percent"
  | "ratio"
  | "number"
  | "score";

type MetricSpec = {
  key: string;
  label: string;
  format?: MetricFormat;
};

function formatMetric(value: number | null | undefined, spec: MetricSpec): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  switch (spec.format) {
    case "currency":
      return currencyFullFmt.format(value);
    case "percent":
      return percentFmt.format(value);
    case "ratio":
      return `${numberFmt.format(value)}×`;
    case "score":
      return numberFmt.format(value);
    case "number":
    default:
      return numberFmt.format(value);
  }
}

function formatCompactCurrency(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return currencyCompactFmt.format(value);
}

function titleCaseTicker(company: CompanySummary | null): string {
  if (!company) return "";
  return `${company.name ?? "Unknown"} (${company.ticker})`;
}

function mergeSeries(series: Array<[string, SeriesPoint[] | undefined]>): Array<Record<string, number | string | null>> {
  const map = new Map<number, Record<string, number | string | null>>();
  for (const [key, points] of series) {
    if (!points) continue;
    for (const p of points) {
      const fy = p.fiscal_year;
      const entry = map.get(fy) ?? { fiscal_year: fy };
      entry[key] = p.value ?? null;
      map.set(fy, entry);
    }
  }
  return Array.from(map.values()).sort((a, b) =>
    (a.fiscal_year as number) - (b.fiscal_year as number)
  );
}

export default function CompanyProfilePage() {
  const navigate = useNavigate();
  const { identifier } = useParams<{ identifier: string }>();

  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTicker, setSearchTicker] = useState(identifier ?? "");
  const [priceRange, setPriceRange] = useState<PriceHistoryRange>("5y");
  const [priceHistory, setPriceHistory] = useState<PriceHistoryPoint[]>([]);
  const [priceHistoryLoading, setPriceHistoryLoading] = useState(false);
  const [priceHistoryError, setPriceHistoryError] = useState<string | null>(null);

  useEffect(() => {
    setSearchTicker(identifier ?? "");
  }, [identifier]);

  useEffect(() => {
    setPriceRange("5y");
    setPriceHistory([]);
    setPriceHistoryError(null);
  }, [identifier]);

  useEffect(() => {
    if (!identifier) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(`${API}/companies/${identifier}/profile`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`profile ${res.status}`);
        }
        return res.json();
      })
      .then((json: CompanyProfile) => {
        if (!cancelled) setProfile(json);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message || "Unable to load profile");
          setProfile(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [identifier]);

  useEffect(() => {
    if (!identifier) return;
    let cancelled = false;
    setPriceHistoryLoading(true);
    setPriceHistoryError(null);

    fetch(`${API}/prices/${identifier}/history?range=${priceRange}`)
      .then(async (res) => {
        if (!res.ok) {
          const text = await res.text();
          let message = text || `prices ${res.status}`;
          try {
            const data = JSON.parse(text);
            message = data?.detail ?? data?.message ?? message;
          } catch {
            // ignore parse errors
          }
          throw new Error(message || `prices ${res.status}`);
        }
        return (res.json() as Promise<PriceHistoryResponse>);
      })
      .then((json) => {
        if (cancelled) return;
        const normalized = (json.points ?? []).map((p) => ({
          ts: p.ts,
          close: p.close === null || p.close === undefined ? null : Number(p.close),
        }));
        setPriceHistory(normalized);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setPriceHistoryError(err.message || "Unable to load price history.");
        setPriceHistory([]);
      })
      .finally(() => {
        if (!cancelled) setPriceHistoryLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [identifier, priceRange]);

  const priceChartData = useMemo(() => {
    return priceHistory
      .filter((p) => typeof p.close === "number" && !Number.isNaN(p.close))
      .map((p) => {
        const date = parsePriceDate(p.ts);
        return {
          ts: date.getTime(),
          close: Number(p.close),
          date,
        };
      })
      .filter((p) => Number.isFinite(p.ts))
      .sort((a, b) => a.ts - b.ts);
  }, [priceHistory]);

  const priceChartHasData = priceChartData.length > 0;

  const revenueIncomeData = useMemo(() => {
    return mergeSeries([
      ["Revenue", profile?.series?.revenue],
      ["Net Income", profile?.series?.net_income],
    ]).map((row) => ({
      label: String(row.fiscal_year),
      revenue: row["Revenue"] ?? null,
      netIncome: row["Net Income"] ?? null,
    }));
  }, [profile]);

  const cashDebtData = useMemo(() => {
    return mergeSeries([
      ["Cash", profile?.series?.cash],
      ["Debt", profile?.series?.debt],
    ]).map((row) => ({
      label: String(row.fiscal_year),
      cash: row["Cash"] ?? null,
      debt: row["Debt"] ?? null,
    }));
  }, [profile]);

  const sharesData = useMemo(() => {
    return (profile?.series?.shares ?? []).map((p) => ({
      label: String(p.fiscal_year),
      shares: p.value,
    }));
  }, [profile]);

  function handleSearch(evt: FormEvent<HTMLFormElement>) {
    evt.preventDefault();
    const raw = searchTicker.trim();
    if (!raw) return;
    navigate(`/companies/${raw.toUpperCase()}/profile`);
  }

  return (
    <div className="w-full max-w-6xl mx-auto px-4 md:px-6 lg:px-8 py-4 space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          <button className={btn} onClick={() => navigate("/")} aria-label="Back to Screener">
            ← Back to Screener
          </button>
          {profile?.company?.id ? (
            <>
              <button
                className={btnGhost}
                onClick={() => navigate(`/financials/${profile.company.id}`)}
              >
                ← Financials
              </button>
              <button
                className={btnGhost}
                onClick={() => navigate(`/pharma/${profile.company.ticker}`)}
              >
                Pharma Insights →
              </button>
            </>
          ) : null}
        </div>
        <form className="flex items-center gap-2" onSubmit={handleSearch}>
          <input
            value={searchTicker}
            onChange={(e) => setSearchTicker(e.target.value)}
            placeholder="Jump to ticker (e.g. AAPL)"
            className="h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/40"
          />
          <button type="submit" className={btn}>
            Go
          </button>
        </form>
      </div>

      {loading ? (
        <div className="text-sm text-zinc-500">Loading profile…</div>
      ) : error ? (
        <div className="rounded-xl border border-red-400/40 bg-red-50/60 dark:bg-red-900/20 px-4 py-3 text-sm text-red-600 dark:text-red-300">
          {error}
        </div>
      ) : profile ? (
        <>
          <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 md:p-6">
            <div className="flex flex-col md:flex-row md:items-start md:justify-between md:gap-6">
              <div className="space-y-2">
                <h1 className="text-2xl font-bold">{titleCaseTicker(profile.company)}</h1>
                {profile.company.industry_name && (
                  <div className="text-sm text-zinc-500">
                    Industry: {profile.company.industry_name}
                  </div>
                )}
                {profile.company.description && (
                  <p className="text-sm text-zinc-500 leading-relaxed max-w-2xl">
                    {profile.company.description}
                  </p>
                )}
              </div>
              <div className="mt-4 md:mt-0 grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <Stat label="Latest Fiscal Year" value={profile.latest_fiscal_year ?? null} />
                <Stat label="Market Cap" value={formatCompactCurrency(profile.market_cap)} />
                <Stat label="Share Price" value={formatCompactCurrency(profile.price)} />
                <Stat
                  label="Ticker"
                  value={profile.company.ticker}
                  alignRight={false}
                />
              </div>
            </div>
          </div>

          <ChartCard
            title="Price History"
            hasData={priceChartHasData}
            loading={priceHistoryLoading}
            headerRight={
              <div className="flex flex-col items-end gap-1">
                <div className="flex items-center gap-1">
                  {PRICE_RANGES.map((rng) => (
                    <button
                      key={rng}
                      type="button"
                      onClick={() => setPriceRange(rng)}
                      className={`${rangeBtn} ${
                        priceRange === rng ? rangeBtnActive : rangeBtnInactive
                      }`}
                    >
                      {PRICE_RANGE_LABEL[rng]}
                    </button>
                  ))}
                </div>
                {priceHistoryError && (
                  <span className="text-[11px] text-red-500">{priceHistoryError}</span>
                )}
              </div>
            }
          >
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={priceChartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="4 4" className="stroke-zinc-200 dark:stroke-zinc-800" />
                <XAxis
                  dataKey="ts"
                  type="number"
                  scale="time"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(value) =>
                    formatPriceTick(value as number, priceRange)
                  }
                  minTickGap={16}
                  tick={{ fontSize: 12 }}
                  allowDuplicatedCategory={false}
                />
                <YAxis
                  tickFormatter={(v) => formatCompactCurrency(v as number)}
                  tick={{ fontSize: 12 }}
                />
                <Tooltip content={<PriceTooltip range={priceRange} />} />
                <Line
                  type="monotone"
                  dataKey="close"
                  stroke="#1d4ed8"
                  strokeWidth={2}
                  dot={priceRange === "1d"}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <div className="grid gap-4 lg:grid-cols-3">
            <MetricCard
              title="Valuation"
              metrics={[
                { key: "price", label: "Price", format: "currency" },
                { key: "fair_value_per_share", label: "Fair Value", format: "currency" },
                { key: "upside_vs_price", label: "Upside", format: "percent" },
                { key: "pe_ttm", label: "P/E (TTM)", format: "number" },
              ]}
              data={profile.valuation}
            />
            <MetricCard
              title="Financial Strength"
              metrics={[
                { key: "cash_debt_ratio", label: "Cash-to-Debt", format: "ratio" },
                { key: "debt_to_equity", label: "Debt-to-Equity", format: "ratio" },
                { key: "debt_ebitda", label: "Debt/EBITDA", format: "ratio" },
                { key: "interest_coverage", label: "Interest Coverage", format: "number" },
              ]}
              data={profile.financial_strength}
            />
            <MetricCard
              title="Profitability"
              metrics={[
                { key: "gross_margin", label: "Gross Margin", format: "percent" },
                { key: "op_margin", label: "Operating Margin", format: "percent" },
                { key: "roe", label: "ROE", format: "percent" },
                { key: "roic", label: "ROIC", format: "percent" },
              ]}
              data={profile.profitability}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <MetricCard
              title="Growth"
              metrics={[
                { key: "rev_cagr_5y", label: "Revenue CAGR (5y)", format: "percent" },
                { key: "ni_cagr_5y", label: "Net Income CAGR (5y)", format: "percent" },
                { key: "rev_yoy", label: "Revenue YoY", format: "percent" },
                { key: "ni_yoy", label: "Net Income YoY", format: "percent" },
              ]}
              data={profile.growth}
            />
            <MetricCard
              title="Quality & Risk"
              metrics={[
                { key: "piotroski_f", label: "Piotroski F-Score", format: "score" },
                { key: "altman_z", label: "Altman Z-Score", format: "number" },
                { key: "growth_consistency", label: "Growth Consistency", format: "score" },
                { key: "data_quality_score", label: "Data Quality", format: "number" },
              ]}
              data={profile.quality}
            />
            <MetricCard
              title="Cash Flow Snapshot"
              metrics={[
                { key: "cfo", label: "Cash from Operations", format: "currency" },
                { key: "capex", label: "CapEx", format: "currency" },
                { key: "fcf", label: "Free Cash Flow", format: "currency" },
                { key: "dividends_paid", label: "Dividends Paid", format: "currency" },
                { key: "share_repurchases", label: "Share Repurchases", format: "currency" },
              ]}
              data={profile.cash_flow}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <div className="lg:col-span-3">
              <MetricCard
                title="Balance Sheet"
                metrics={[
                  { key: "cash_and_sti", label: "Cash & STI", format: "currency" },
                  { key: "total_debt", label: "Total Debt", format: "currency" },
                  { key: "assets_total", label: "Total Assets", format: "currency" },
                  { key: "equity_total", label: "Total Equity", format: "currency" },
                  { key: "liabilities_current", label: "Current Liabilities", format: "currency" },
                  { key: "liabilities_longterm", label: "Long-term Liabilities", format: "currency" },
                  { key: "inventories", label: "Inventories", format: "currency" },
                  { key: "accounts_receivable", label: "Accounts Receivable", format: "currency" },
                  { key: "accounts_payable", label: "Accounts Payable", format: "currency" },
                ]}
                data={profile.balance_sheet}
                dense
              />
            </div>

            <ChartCard
              title="Revenue & Net Income"
              hasData={revenueIncomeData.length > 0}
              compact
            >
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={revenueIncomeData}>
                  <defs>
                    <linearGradient id="rev" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#2563eb" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="ni" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={(v) => formatCompactCurrency(v as number)} tick={{ fontSize: 11 }} />
                  <Tooltip
                    formatter={(value, key) =>
                      formatCompactCurrency(typeof value === "number" ? value : Number(value))
                    }
                    labelFormatter={(label) => `FY ${label}`}
                  />
                  <Area
                    type="monotone"
                    dataKey="revenue"
                    name="Revenue"
                    stroke="#2563eb"
                    fill="url(#rev)"
                    strokeWidth={2}
                  />
                  <Area
                    type="monotone"
                    dataKey="netIncome"
                    name="Net Income"
                    stroke="#22c55e"
                    fill="url(#ni)"
                    strokeWidth={2}
                  />
                  <Legend verticalAlign="top" height={24} />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Cash vs Debt" hasData={cashDebtData.length > 0} compact>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={cashDebtData}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={(v) => formatCompactCurrency(v as number)} tick={{ fontSize: 11 }} />
                  <Tooltip
                    formatter={(value, key) =>
                      formatCompactCurrency(typeof value === "number" ? value : Number(value))
                    }
                    labelFormatter={(label) => `FY ${label}`}
                  />
                  <Legend verticalAlign="top" height={24} />
                  <Bar dataKey="cash" name="Cash" fill="#22c55e" />
                  <Bar dataKey="debt" name="Debt" fill="#ef4444" />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Shares Outstanding" hasData={sharesData.length > 0} compact>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={sharesData}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={(v) => numberFmt.format(v as number)} tick={{ fontSize: 11 }} />
                  <Tooltip
                    formatter={(value) => numberFmt.format(typeof value === "number" ? value : Number(value))}
                    labelFormatter={(label) => `FY ${label}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="shares"
                    name="Shares"
                    stroke="#7c3aed"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>
        </>
      ) : (
        <div className="text-sm text-zinc-500">Enter a ticker to load its profile.</div>
      )}
    </div>
  );
}

function Stat({ label, value, alignRight = true }: { label: string; value: ReactNode; alignRight?: boolean }) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className={`text-sm font-semibold mt-1 ${alignRight ? "text-right" : ""}`}>{value ?? "—"}</div>
    </div>
  );
}

function formatPriceTick(value: number, range: PriceHistoryRange): string {
  const date = new Date(value);
  switch (range) {
    case "1d":
      return fmtIntradayTick.format(date);
    case "5d":
    case "1m":
    case "ytd":
      return fmtDayTick.format(date);
    case "5y":
      return fmtMonthYearTick.format(date);
    case "max":
      return fmtYearTick.format(date);
    default:
      return fmtDayTick.format(date);
  }
}

function formatPriceTooltip(value: number, range: PriceHistoryRange): string {
  const date = new Date(value);
  switch (range) {
    case "1d":
      return fmtTooltipFull.format(date);
    case "5d":
    case "1m":
    case "ytd":
    case "5y":
    case "max":
      return fmtTooltipDate.format(date);
    default:
      return fmtTooltipDate.format(date);
  }
}

function parsePriceDate(ts: string): Date {
  if (!ts) return new Date(NaN);
  if (ts.endsWith("Z") || ts.includes("+")) return new Date(ts);
  if (ts.includes("T")) return new Date(ts);
  if (ts.includes(" ")) return new Date(ts.replace(" ", "T"));
  return new Date(`${ts}T00:00:00`);
}

function MetricCard({
  title,
  metrics,
  data,
  dense = false,
}: {
  title: string;
  metrics: MetricSpec[];
  data: MetricMap;
  dense?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 space-y-3">
      <div className="text-[12px] font-semibold uppercase tracking-wide text-zinc-500">
        {title}
      </div>
      <div className={`grid gap-2 ${dense ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1"}`}>
        {metrics.map((spec) => {
          const rawValue = data?.[spec.key];
          const display = formatMetric(rawValue ?? null, spec);
          const isNegative =
            rawValue !== null &&
            rawValue !== undefined &&
            typeof rawValue === "number" &&
            rawValue < 0;
          return (
            <div key={spec.key} className="flex items-center justify-between text-sm">
              <span className="text-[13px] text-zinc-500">{spec.label}</span>
              <span className={`font-semibold tabular-nums ${isNegative ? "text-red-500" : "text-zinc-900 dark:text-zinc-50"}`}>
                {display}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ChartCard({
  title,
  children,
  hasData,
  compact = false,
  headerRight,
  loading = false,
}: {
  title: string;
  children: ReactNode;
  hasData: boolean;
  compact?: boolean;
  headerRight?: ReactNode;
  loading?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="text-[12px] font-semibold uppercase tracking-wide text-zinc-500">
          {title}
        </div>
        {headerRight}
      </div>
      {loading && (
        <div className="text-[11px] text-zinc-400 dark:text-zinc-500">Loading…</div>
      )}
      {hasData ? (
        <div className={compact ? "h-[220px]" : "h-[280px]"}>{children}</div>
      ) : (
        <div className="h-[160px] flex items-center justify-center text-sm text-zinc-500">
          No data available.
        </div>
      )}
    </div>
  );
}

type PriceTooltipPropsEx = TooltipProps<number, string> & { range: PriceHistoryRange };

function PriceTooltip({ active, payload, range }: PriceTooltipPropsEx) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0];
  if (typeof point.value !== "number") return null;
  const ts = point.payload?.date instanceof Date
    ? point.payload.date.getTime()
    : typeof point.payload?.ts === "number"
    ? point.payload.ts
    : Number(point.payload?.ts ?? 0);

  if (!Number.isFinite(ts)) return null;

  const dateLabel = formatPriceTooltip(ts, range);
  const priceLabel = currencyFullFmt.format(point.value);

  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white/95 dark:bg-zinc-900/95 px-3 py-2 shadow-sm space-y-1">
      <div className="text-xs font-semibold text-zinc-700 dark:text-zinc-200">{dateLabel}</div>
      <div className="text-xs text-sky-600 dark:text-sky-400 font-semibold">Close: {priceLabel}</div>
    </div>
  );
}

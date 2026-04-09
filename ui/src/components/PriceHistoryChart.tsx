import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";


type RangeOption = "1d" | "5d" | "1m" | "3m" | "ytd" | "1y" | "5y" | "max";
type EodRangeOption = Extract<RangeOption, "1m" | "3m" | "ytd" | "1y" | "max">;

const RANGES: { value: EodRangeOption; label: string }[] = [
  { value: "1m", label: "1M" },
  { value: "3m", label: "3M" },
  { value: "ytd", label: "YTD" },
  { value: "1y", label: "1Y" },
  { value: "max", label: "MAX" },
];

type PricePoint = { ts: number; close: number };
type ChangeSummary = {
  start_date: string;
  end_date: string;
  change: number;
  change_pct?: number | null;
};

type PriceHistoryPayload = {
  points: PricePoint[];
  summary: {
    "1d"?: ChangeSummary | null;
    "1m"?: ChangeSummary | null;
    "1y"?: ChangeSummary | null;
  };
};

function fmtCurrency(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
}

function fmtPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 2, signDisplay: "auto" }).format(value);
}

export async function fetchPriceHistory(ticker: string, range: RangeOption): Promise<PriceHistoryPayload> {
  const base = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
  const res = await fetch(`${base}/prices/${ticker}/history?range=${range}`);
  if (!res.ok) throw new Error(`price-history ${res.status}`);
  const json = await res.json();
  return {
    points: (json.points ?? []).map((p: any) => ({ ts: new Date(p.ts).getTime(), close: Number(p.close) })),
    summary: json.summary ?? {},
  };
}

export default function PriceHistoryChart({ ticker }: { ticker: string }) {
  const [range, setRange] = useState<EodRangeOption>("1y");
  const [data, setData] = useState<PricePoint[]>([]);
  const [summary, setSummary] = useState<PriceHistoryPayload["summary"]>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const payload = await fetchPriceHistory(ticker, range);
        if (!cancelled) {
          setData(payload.points);
          setSummary(payload.summary);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [ticker, range]);

  const summaryCards = useMemo(
    () => [
      { label: "1D", value: fmtCurrency(summary["1d"]?.change), pct: fmtPercent(summary["1d"]?.change_pct) },
      { label: "1M", value: fmtCurrency(summary["1m"]?.change), pct: fmtPercent(summary["1m"]?.change_pct) },
      { label: "1Y", value: fmtCurrency(summary["1y"]?.change), pct: fmtPercent(summary["1y"]?.change_pct) },
    ],
    [summary],
  );

  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">EOD Price History</h2>
        <div className="flex gap-1">
          {RANGES.map((opt) => (
            <button
              key={opt.value}
              className={`px-2 py-1 rounded-md text-xs font-medium border ${range === opt.value ? "bg-sky-600 text-white border-sky-600" : "border-zinc-300 dark:border-zinc-700 text-zinc-500"}`}
              onClick={() => setRange(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {summaryCards.map((card) => (
          <div key={card.label} className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-3">
            <div className="text-xs uppercase tracking-wide text-zinc-500">{card.label} Change</div>
            <div className="mt-1 text-lg font-semibold">{card.value}</div>
            <div className="text-sm text-zinc-500">{card.pct}</div>
          </div>
        ))}
      </div>
      {loading ? (
        <div className="text-sm text-zinc-500">Loading price data…</div>
      ) : error ? (
        <div className="text-sm text-red-500">{error}</div>
      ) : data.length === 0 ? (
        <div className="text-sm text-zinc-500">No price points for this range.</div>
      ) : (
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="4 4" className="stroke-zinc-200 dark:stroke-zinc-800" />
              <XAxis
                dataKey="ts"
                type="number"
                scale="time"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(value) => new Date(value as number).toLocaleDateString()}
                minTickGap={16}
              />
              <YAxis tickFormatter={(v) => `$${v.toFixed(2)}`} />
              <Tooltip
                labelFormatter={(value) => new Date(value as number).toLocaleString()}
                formatter={(value: number) => `$${value.toFixed(2)}`}
              />
              <Line type="monotone" dataKey="close" stroke="#2563eb" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

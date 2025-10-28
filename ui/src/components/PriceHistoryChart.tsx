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


type RangeOption = "1d" | "5d" | "1m" | "ytd" | "5y" | "max";

const RANGES: { value: RangeOption; label: string }[] = [
  { value: "1d", label: "1D" },
  { value: "5d", label: "5D" },
  { value: "1m", label: "1M" },
  { value: "ytd", label: "YTD" },
  { value: "5y", label: "5Y" },
  { value: "max", label: "MAX" },
];

type PricePoint = { ts: number; close: number };

export async function fetchPriceHistory(ticker: string, range: RangeOption): Promise<PricePoint[]> {
  const base = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
  const res = await fetch(`${base}/prices/${ticker}/history?range=${range}`);
  if (!res.ok) throw new Error(`price-history ${res.status}`);
  const json = await res.json();
  return (json.points ?? []).map((p: any) => ({ ts: new Date(p.ts).getTime(), close: Number(p.close) }));
}

export default function PriceHistoryChart({ ticker }: { ticker: string }) {
  const [range, setRange] = useState<RangeOption>("5y");
  const [data, setData] = useState<PricePoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const points = await fetchPriceHistory(ticker, range);
        if (!cancelled) setData(points);
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

  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Price History</h2>
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

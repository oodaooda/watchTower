import { useEffect, useRef, useState } from "react";
import FilterBar from "./components/FilterBar";
import ResultsTable from "./components/ResultsTable";
import ThemeToggle from "./components/ThemeToggle";
import { fetchScreen, fetchValuationSummary } from "./lib/api";
import type { ScreenRow } from "./types";

type MergedRow = ScreenRow;

export default function App() {
  const [rows, setRows] = useState<MergedRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reqSeq = useRef(0);

  async function run(params: Record<string, string | number | undefined>) {
    const mySeq = ++reqSeq.current;
    setLoading(true);
    setError(null);
    try {
      // 1) base screen (now includes price)
      const base = (await fetchScreen({ limit: 100, ...params })) as ScreenRow[];
      if (reqSeq.current !== mySeq) return;
      setRows(base);

      // 2) valuation summary (fair value + upside; price only as fallback)
      if (base.length) {
        const tickers = base.map((r) => r.ticker).join(",");
        let vals: Awaited<ReturnType<typeof fetchValuationSummary>> = [];
        try {
          vals = await fetchValuationSummary(tickers);
        } catch {
          vals = [];
        }
        if (reqSeq.current !== mySeq) return;

        const vmap = new Map(vals.map((v) => [v.ticker.toUpperCase(), v]));
        setRows((prev) =>
          prev.map((r) => {
            const v = vmap.get(r.ticker.toUpperCase());
            return {
              ...r,
              // keep server price; use valuation price only if server price is null/undefined
              price: r.price ?? v?.price ?? null,
              fair_value_per_share: v?.fair_value_per_share ?? null,
              upside_vs_price: v?.upside_vs_price ?? null,
            };
          })
        );
      }
    } catch (e: any) {
      if (reqSeq.current === mySeq) setError(e?.message ?? "Failed to load data");
    } finally {
      if (reqSeq.current === mySeq) setLoading(false);
    }
  }

  useEffect(() => {
    run({ cash_debt_min: 0.8, growth_consistency_min: 7 });
  }, []);

  return (
    <div className="min-h-screen bg-white text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <div className="max-w-6xl mx-auto p-4">
        <div className="flex items-center gap-3 mb-4">
          <h1 className="text-2xl font-bold">watchTower — Screener</h1>
          <ThemeToggle />
        </div>
        <FilterBar onRun={run} />
        {error && (
          <div className="my-3 rounded-lg border border-rose-600/30 bg-rose-950/30 px-3 py-2 text-rose-300">
            {error}
          </div>
        )}
        <ResultsTable rows={rows} loading={loading} />
      </div>
    </div>
  );
}

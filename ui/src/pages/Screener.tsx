// ui/src/App.tsx
import { useEffect, useRef, useState } from "react";
import FilterBar from "../components/FilterBar";
import ResultsTable from "../components/ResultsTable";
import { fetchScreen, fetchValuationSummary } from "../lib/api";
import type { ScreenRow } from "../types";

type MergedRow = ScreenRow & {
  fair_value_per_share?: number | null;
  upside_vs_price?: number | null;
};

const pageSize = 10;

export default function App() {
  const [rows, setRows] = useState<MergedRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [lastParams, setLastParams] = useState<Record<string, any>>({});
  const reqSeq = useRef(0);

  async function run(params: Record<string, any>, resetPage = true) {
    const mySeq = ++reqSeq.current;
    if (resetPage) setPage(1);
    setLoading(true);
    setError(null);
    try {
      const res = await fetchScreen({
        limit: pageSize,
        offset: (resetPage ? 0 : (page - 1) * pageSize),
        ...params,
      });

      if (reqSeq.current !== mySeq) return;

      setRows(res.items);
      setTotalPages(Math.max(1, Math.ceil(res.total_count / pageSize)));
      setLastParams(params);

      // fetch valuations and merge
      if (res.items.length) {
        const tickers = [...new Set(res.items.map((r: ScreenRow) => r.ticker))];
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
    run({ cash_debt_min: 0.8, growth_consistency_min: 7 }, true);
  }, []);

  function handleRun(params: Record<string, any>) {
    run(params, true);
  }

  function handlePageChange(newPage: number) {
    setPage(newPage);
    run(lastParams, false);
  }

  return (
    <>
      {/* simple page label, header is provided by AppShell */}
      <h2 className="text-xl font-semibold mb-3">Screener</h2>

      <FilterBar onRun={handleRun} />

      {error && (
        <div className="my-3 rounded-lg border border-rose-600/30 bg-rose-950/30 px-3 py-2 text-rose-300">
          {error}
        </div>
      )}

      <ResultsTable rows={rows} loading={loading} />

      {/* Pagination */}
      <div className="flex items-center justify-between mt-4">
        <button
          onClick={() => handlePageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="px-3 py-1.5 rounded bg-zinc-800 text-white disabled:opacity-50"
        >
          ← Prev
        </button>
        <span>
          Page {page} of {totalPages}
        </span>
        <button
          onClick={() => handlePageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          className="px-3 py-1.5 rounded bg-zinc-800 text-white disabled:opacity-50"
        >
          Next →
        </button>
      </div>
    </>
  );
}

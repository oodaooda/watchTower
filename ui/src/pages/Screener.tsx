// ui/src/pages/ScreenerPage.tsx
import { useEffect, useMemo, useState } from "react";
import ResultsTable, { SortKey, SortDir } from "../components/ResultsTable";
import FilterBar from "../components/FilterBar";

type ScreenRow = {
  company_id: number;
  ticker: string;
  name: string;
  industry?: string | null;
  description?: string | null;
  fiscal_year?: number | null;
  pe_ttm?: number | null;
  cash_debt_ratio?: number | null;
  growth_consistency?: number | null;
  rev_cagr_5y?: number | null;
  ni_cagr_5y?: number | null;
  fcf_cagr_5y?: number | null;
  price?: number | null;
};

type ScreenResponse = { total_count: number; items: ScreenRow[] };

type FilterParams = {
  pe_max?: number;
  cash_debt_min?: number;
  growth_consistency_min?: number;
  rev_cagr_min?: number;
  ni_cagr_min?: number;
  fcf_cagr_min?: number;
  industry?: string;        // empty/undefined => all
};

type ValSummary = {
  ticker: string;
  fair_value_per_share?: number | null;
  upside_vs_price?: number | null;
};

const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export default function ScreenerPage() {
  // paging
  const [page, setPage] = useState(1);
  const pageSize = 10;

  // search + filters
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<FilterParams>({});

  // server sort
  const [sortKey, setSortKey] = useState<SortKey>("ticker");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  // data
  const [rows, setRows] = useState<(ScreenRow & ValSummary)[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  // Fetch + (optional) valuation merge
  useEffect(() => {
    const params = new URLSearchParams();
    params.set("limit", String(pageSize));
    params.set("offset", String((page - 1) * pageSize));
    if (search) params.set("q", search);

    // include ALL filters that are set
    (Object.entries(filters) as [keyof FilterParams, any][]).forEach(([k, v]) => {
      if (v !== undefined && v !== "") params.set(k, String(v));
    });

    params.set("sort_key", sortKey);
    params.set("sort_dir", sortDir);

    let cancelled = false;
    setLoading(true);

    (async () => {
      try {
        const r = await fetch(`${API}/screen?${params.toString()}`);
        const json: ScreenResponse = await r.json();

        // optional: merge valuation summary (preserve server order)
        const tickers = json.items.map((x) => x.ticker).filter(Boolean);
        let valMap: Record<string, ValSummary> = {};
        if (tickers.length) {
          try {
            const rv = await fetch(
              `${API}/valuation/summary?tickers=${encodeURIComponent(tickers.join(","))}`
            );
            const vals: ValSummary[] = await rv.json();
            valMap = Object.fromEntries(vals.map((v) => [v.ticker, v]));
          } catch {
            // ignore valuation failures
          }
        }

        const merged = json.items.map((r) => ({ ...r, ...(valMap[r.ticker] ?? {}) }));
        if (!cancelled) {
          setRows(merged);
          setTotal(json.total_count);
        }
      } catch {
        if (!cancelled) {
          setRows([]);
          setTotal(0);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [page, pageSize, search, filters, sortKey, sortDir]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / pageSize)),
    [total, pageSize]
  );

  // header click: ask server to re-sort globally
  function handleSort(k: SortKey) {
    setSortDir((d) => (k === sortKey ? (d === "asc" ? "desc" : "asc") : "asc"));
    setSortKey(k);
    setPage(1);
  }

  return (
    //<div className="w-full max-w-none px-4 md:px-8 lg:px-12 xl:px-16 py-4">
    //<div className="w-full max-w-[1800px] mx-auto px-3 sm:px-4 md:px-6 lg:px-8 py-2">
    <div className="mt-6 w-full max-w-[1800px] mx-auto rounded-2xl  border-zinc-200 dark:border-zinc-800 overflow-hidden">

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        onSearch={(q) => {
          setSearch(q);
          setPage(1);
        }}
        onRunFilters={(p) => {
          setFilters(p);   // <<— keep every filter from the bar
          setPage(1);
        }}
      />

      <ResultsTable
        rows={rows as any}
        loading={loading}
        filterText={search}    // client-side *text* filter only
        sortKey={sortKey}
        sortDir={sortDir}
        onRequestSort={handleSort}
      />

      <div className="flex items-center justify-between mt-3">
        <button
          disabled={page <= 1}
          onClick={() => setPage((x) => Math.max(1, x - 1))}
          className="rounded-xl border border-zinc-700 px-4 py-2 disabled:opacity-50"
        >
          ← Prev
        </button>
        <div className="text-sm text-zinc-400">Page {page} of {totalPages}</div>
        <button
          disabled={page >= totalPages}
          onClick={() => setPage((x) => Math.min(totalPages, x + 1))}
          className="rounded-xl border border-zinc-700 px-4 py-2 disabled:opacity-50"
        >
          Next →
        </button>
      </div>
    </div>
  );
}

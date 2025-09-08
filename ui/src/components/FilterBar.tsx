// ui/src/components/FilterBar.tsx
import { useEffect, useState } from "react";

type FilterParams = {
  pe_max?: number;
  cash_debt_min?: number;
  growth_consistency_min?: number;
  rev_cagr_min?: number;
  ni_cagr_min?: number;
  fcf_cagr_min?: number;
  industry?: string;
};

type Props = {
  // search is independent of filters
  search: string;
  onSearchChange: (v: string) => void;
  onSearch: (query: string) => void;

  // filters-only action (no q/tickers mixed in)
  onRunFilters: (params: FilterParams) => void;
};

const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const btnPrimary =
  "h-9 px-4 rounded-md bg-black text-white font-medium " +
  "inline-flex items-center justify-center " +
  "hover:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

const btnSecondary =
  "h-9 px-3 rounded-md border border-zinc-300 text-zinc-900 " +
  "dark:border-white/10 dark:text-white hover:bg-zinc-100 dark:hover:bg-zinc-800";

const inputCls =
  "w-full h-9 rounded-md px-3 border bg-white text-zinc-900 placeholder-zinc-500 " +
  "focus:outline-none focus:ring-2 focus:ring-sky-500/30 " +
  "dark:bg-zinc-800 dark:text-white dark:placeholder-white/60 dark:border-white/10 " +
  "dark:focus:ring-sky-400/30";

function handleKeyDown(e: React.KeyboardEvent, action: () => void) {
  if (e.key === "Enter") {
    e.preventDefault();
    action();
  }
}

export default function FilterBar({
  search,
  onSearchChange,
  onSearch,
  onRunFilters,
}: Props) {
  // local filter state (doesn't affect Search)
  const [peMax, setPeMax] = useState<number | undefined>(undefined);
  const [cashDebtMin, setCashDebtMin] = useState<number | undefined>(0.8);
  const [growthMin, setGrowthMin] = useState<number | undefined>(7);
  const [revCagr, setRevCagr] = useState<number | undefined>(undefined);
  const [niCagr, setNiCagr] = useState<number | undefined>(undefined);
  const [fcfCagr, setFcfCagr] = useState<number | undefined>(undefined);
  const [industry, setIndustry] = useState<string>("");

  // Industry dropdown data
  const [industries, setIndustries] = useState<string[]>([]);
  const [loadingIndustries, setLoadingIndustries] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoadingIndustries(true);
      try {
        const r = await fetch(`${API}/industries`);
        const data = await r.json();
        // Accept either [{ industry, count }, ...] OR string[] OR { items: [...] }
        const arr: any[] = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
        const names = arr
          .map((x) => (typeof x === "string" ? x : x?.industry))
          .filter((s: unknown): s is string => typeof s === "string" && s.length > 0 && s !== "NONE");

        const uniqueSorted = Array.from(new Set(names)).sort((a, b) => a.localeCompare(b));
        if (alive) setIndustries(uniqueSorted);
      } catch {
        if (alive) setIndustries([]);
      } finally {
        if (alive) setLoadingIndustries(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  function runFilters(paramsOverride?: Partial<FilterParams>) {
    onRunFilters({
      pe_max: peMax,
      cash_debt_min: cashDebtMin,
      growth_consistency_min: growthMin,
      rev_cagr_min: revCagr,
      ni_cagr_min: niCagr,
      fcf_cagr_min: fcfCagr,
      industry: industry || undefined,
      ...paramsOverride,
    });
  }

  function resetFilters() {
    setPeMax(undefined);
    setCashDebtMin(0.8);
    setGrowthMin(7);
    setRevCagr(undefined);
    setNiCagr(undefined);
    setFcfCagr(undefined);
    setIndustry("");
    onRunFilters({ cash_debt_min: 0.8, growth_consistency_min: 7 });
  }

  function runSearchOnly() {
    onSearch(search);
  }

  return (
  
    <div className="rounded-xl p-3 mb-3 border border-zinc-200 bg-white shadow-sm
                dark:border-white/10 dark:bg-white/5">
      {/* First cell: SEARCH (independent) */}
      <div className="grid grid-cols-2 md:grid-cols-8 gap-2">
        <div className="md:col-span-2">
          <label className="text-xs mb-1 block">Search (all companies)</label>
          <input
            type="text"
            placeholder="Ticker(s) or Company (e.g. AAPL, TSLA or 'semiconductors')"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            onKeyDown={(e) => handleKeyDown(e, runSearchOnly)}
            className={inputCls}
          />
        </div>

        {/* Filters */}
        <div>
          <label className="text-xs mb-1 block">P/E ≤</label>
          <input
            type="number"
            placeholder="e.g. 20"
            value={peMax ?? ""}
            onChange={(e) => setPeMax(e.target.value ? Number(e.target.value) : undefined)}
            onKeyDown={(e) => handleKeyDown(e, () => runFilters())}
            className={inputCls}
          />
        </div>

        <div>
          <label className="text-xs mb-1 block">Cash/Debt ≥</label>
          <input
            type="number"
            step="0.01"
            value={cashDebtMin ?? ""}
            onChange={(e) => setCashDebtMin(e.target.value ? Number(e.target.value) : undefined)}
            onKeyDown={(e) => handleKeyDown(e, () => runFilters())}
            className={inputCls}
          />
        </div>

        <div>
          <label className="text-xs mb-1 block">Growth Consistency ≥</label>
          <input
            type="number"
            value={growthMin ?? ""}
            onChange={(e) => setGrowthMin(e.target.value ? Number(e.target.value) : undefined)}
            onKeyDown={(e) => handleKeyDown(e, () => runFilters())}
            className={inputCls}
          />
        </div>

        <div>
          <label className="text-xs mb-1 block">Rev CAGR 5y ≥</label>
          <input
            type="number"
            step="0.01"
            placeholder="0.05 = 5%"
            value={revCagr ?? ""}
            onChange={(e) => setRevCagr(e.target.value ? Number(e.target.value) : undefined)}
            onKeyDown={(e) => handleKeyDown(e, () => runFilters())}
            className={inputCls}
          />
        </div>

        <div>
          <label className="text-xs mb-1 block">NI CAGR 5y ≥</label>
          <input
            type="number"
            step="0.01"
            placeholder="0.05 = 5%"
            value={niCagr ?? ""}
            onChange={(e) => setNiCagr(e.target.value ? Number(e.target.value) : undefined)}
            onKeyDown={(e) => handleKeyDown(e, () => runFilters())}
            className={inputCls}
          />
        </div>

        <div>
          <label className="text-xs mb-1 block">FCF CAGR 5y ≥</label>
          <input
            type="number"
            step="0.01"
            placeholder="0.05 = 5%"
            value={fcfCagr ?? ""}
            onChange={(e) => setFcfCagr(e.target.value ? Number(e.target.value) : undefined)}
            onKeyDown={(e) => handleKeyDown(e, () => runFilters())}
            className={inputCls}
          />
        </div>

        {/* Industry → dropdown */}
        <div>
          <label className="text-xs mb-1 block">Industry</label>
          <select
            value={industry}
            onChange={(e) => {
              const next = e.target.value;
              setIndustry(next);
              // apply immediately with selected industry
              runFilters({ industry: next || undefined });
            }}
            disabled={loadingIndustries}
            className={inputCls}
          >
            <option value="">All</option>
            {industries.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          {loadingIndustries && (
            <div className="mt-1 text-xs text-zinc-500">Loading…</div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className={btnPrimary} onClick={runSearchOnly}>
          Search
        </button>
        <button type="button" className={btnSecondary} onClick={() => runFilters()}>
          Run screen
        </button>
        <button type="button" className={btnSecondary} onClick={resetFilters}>
          Reset filters
        </button>
      </div>
    </div>
  );
}

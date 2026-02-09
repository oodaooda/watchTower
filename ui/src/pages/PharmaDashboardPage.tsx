import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import BackButton from "../components/BackButton";
import { fetchPharmaCompanies, PharmaCompanyListItem } from "../lib/api";

const btn =
  "h-8 px-3 rounded-xl font-medium inline-flex items-center justify-center bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900 hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

export default function PharmaDashboardPage() {
  const [items, setItems] = useState<PharmaCompanyListItem[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const limit = 25;
  const [total, setTotal] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchPharmaCompanies({ search, limit, offset });
        if (!cancelled) {
          setItems(res.items);
          setTotal(res.total);
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
  }, [search, offset]);

  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="mt-6 space-y-4">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <h1 className="text-2xl font-bold">Pharma Pipeline</h1>
        <div className="flex gap-2">
          <BackButton />
        </div>
      </div>

      <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <input
            value={search}
            onChange={(e) => {
              setOffset(0);
              setSearch(e.target.value);
            }}
            placeholder="Search ticker..."
            className="w-full sm:w-64 h-10 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/40"
          />
          <div className="text-sm text-zinc-500">{total} companies</div>
        </div>

        {loading ? (
          <div className="mt-6 text-sm text-zinc-500">Loading…</div>
        ) : error ? (
          <div className="mt-6 text-sm text-red-500">{error}</div>
        ) : items.length === 0 ? (
          <div className="mt-6 text-sm text-zinc-500">No pharma companies found.</div>
        ) : (
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-left text-sm min-w-[720px]">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-zinc-500">
                  <th className="py-2">Ticker</th>
                  <th className="py-2">Name</th>
                  <th className="py-2">Lead Sponsor</th>
                  <th className="py-2 text-right">Drugs</th>
                  <th className="py-2 text-right">Trials</th>
                  <th className="py-2">Last Refresh</th>
                  <th></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {items.map((item) => (
                  <tr key={item.ticker}>
                    <td className="py-3 font-semibold text-zinc-900 dark:text-zinc-100">
                      <Link className="text-sky-500" to={`/pharma/${item.ticker}`}>
                        {item.ticker}
                      </Link>
                    </td>
                    <td className="py-3 text-zinc-600 dark:text-zinc-400">{item.name}</td>
                    <td className="py-3 text-zinc-600 dark:text-zinc-400">{item.lead_sponsor ?? "—"}</td>
                    <td className="py-3 text-right tabular-nums">{item.drug_count}</td>
                    <td className="py-3 text-right tabular-nums">{item.trial_count}</td>
                    <td className="py-3 text-zinc-500 text-sm">
                      {item.last_refreshed ? new Date(item.last_refreshed).toLocaleDateString() : "—"}
                    </td>
                    <td className="py-3 text-right">
                      <Link className="text-xs text-sky-500" to={`/pharma/${item.ticker}`}>
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4 flex items-center justify-end gap-3">
          <button
            className="text-sm px-3 py-1 rounded-xl border border-zinc-300 dark:border-zinc-700 disabled:opacity-40"
            onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
            disabled={offset <= 0}
          >
            ← Prev
          </button>
          <div className="text-xs text-zinc-500">
            Page {Math.floor(offset / limit) + 1} of {totalPages}
          </div>
          <button
            className="text-sm px-3 py-1 rounded-xl border border-zinc-300 dark:border-zinc-700 disabled:opacity-40"
            onClick={() => setOffset((prev) => prev + limit)}
            disabled={offset + limit >= total}
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}

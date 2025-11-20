import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE } from "../lib/api";

type Favorite = {
  company_id: number;
  ticker: string;
  name?: string | null;
  industry?: string | null;
  price?: number | null;
  change_percent?: number | null;
  pe?: number | null;
  eps?: number | null;
  market_cap?: number | null;
  notes?: string | null;
  source?: string | null;
};

const btn =
  "h-9 px-4 rounded-xl font-medium inline-flex items-center justify-center bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900 hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-sky-500/30 disabled:opacity-40";

function formatCurrency(v?: number | null) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(v);
}

function formatNumber(v?: number | null) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 2 }).format(v);
}

function formatPercent(v?: number | null) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat(undefined, { style: "percent", signDisplay: "auto", maximumFractionDigits: 2 }).format(v);
}

export default function FavoritesPage() {
  const [items, setItems] = useState<Favorite[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newTicker, setNewTicker] = useState("");
  const [adding, setAdding] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchFavorites = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/favorites`);
      if (!res.ok) throw new Error(`fetch ${res.status}`);
      const data: Favorite[] = await res.json();
      setItems(data || []);
      setLastUpdated(new Date());
    } catch (e: any) {
      setError(e.message || "Failed to load favorites");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFavorites();
    const id = setInterval(fetchFavorites, 60_000);
    return () => clearInterval(id);
  }, [fetchFavorites]);

  const handleAdd = async (evt: React.FormEvent) => {
    evt.preventDefault();
    const ticker = newTicker.trim().toUpperCase();
    if (!ticker) return;
    setAdding(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/favorites`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `add ${res.status}`);
      }
      setNewTicker("");
      await fetchFavorites();
    } catch (e: any) {
      setError(e.message || "Failed to add favorite");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (ticker: string) => {
    if (!ticker) return;
    try {
      const res = await fetch(`${API_BASE}/favorites/${ticker}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`delete ${res.status}`);
      await fetchFavorites();
    } catch (e: any) {
      setError(e.message || "Failed to remove favorite");
    }
  };

  const statusText = useMemo(() => {
    if (loading) return "Refreshing…";
    if (!lastUpdated) return "—";
    return `Updated ${lastUpdated.toLocaleTimeString()}`;
  }, [loading, lastUpdated]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Favorite Companies</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Track tickers with live price deltas (refreshes automatically every 60 seconds).
          </p>
        </div>
        <div className="text-sm text-zinc-500 dark:text-zinc-400">{statusText}</div>
      </div>

      <form onSubmit={handleAdd} className="flex flex-wrap items-center gap-2">
        <input
          className="h-9 px-3 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-sm uppercase"
          placeholder="Add ticker (e.g., AAPL)"
          value={newTicker}
          maxLength={10}
          onChange={(e) => setNewTicker(e.target.value.toUpperCase().replace(/[^A-Z0-9.-]/g, ""))}
        />
        <button type="submit" className={btn} disabled={adding || !newTicker.trim()}>
          {adding ? "Adding…" : "Add"}
        </button>
        {error && <span className="text-sm text-red-500">{error}</span>}
      </form>

      <div className="overflow-auto rounded-2xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900/60 text-left text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-3 py-3">Ticker</th>
              <th className="px-3 py-3">Company</th>
              <th className="px-3 py-3">Industry</th>
              <th className="px-3 py-3 text-right">Price</th>
              <th className="px-3 py-3 text-right">Change</th>
              <th className="px-3 py-3 text-right">P/E (TTM)</th>
              <th className="px-3 py-3 text-right">EPS</th>
              <th className="px-3 py-3 text-right">Market Cap</th>
              <th className="px-3 py-3 text-right">Source</th>
              <th className="px-3 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td className="px-3 py-6 text-center text-zinc-500" colSpan={10}>
                  {loading ? "Loading favorites…" : "No favorites yet — add a ticker above."}
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr
                  key={item.company_id}
                  className="border-t border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50/70 dark:hover:bg-zinc-900/40"
                >
                  <td className="px-3 py-3 font-semibold">{item.ticker}</td>
                  <td className="px-3 py-3">{item.name || "—"}</td>
                  <td className="px-3 py-3">{item.industry || "—"}</td>
                  <td className="px-3 py-3 text-right">{formatCurrency(item.price)}</td>
                  <td className="px-3 py-3 text-right">
                    <span className={item?.change_percent && item.change_percent > 0 ? "text-emerald-500" : item?.change_percent && item.change_percent < 0 ? "text-red-500" : ""}>
                      {formatPercent(item.change_percent)}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right">{formatNumber(item.pe)}</td>
                  <td className="px-3 py-3 text-right">{formatNumber(item.eps)}</td>
                  <td className="px-3 py-3 text-right">{formatNumber(item.market_cap)}</td>
                  <td className="px-3 py-3 text-right text-xs text-zinc-500">
                    {item.source === "alpha_vantage" ? "Live" : "Cached"}
                  </td>
                  <td className="px-3 py-3 text-right">
                    <button
                      className="text-sm text-red-500 hover:underline"
                      onClick={() => handleDelete(item.ticker)}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

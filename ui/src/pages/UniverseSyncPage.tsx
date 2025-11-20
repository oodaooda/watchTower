import { useState } from "react";
import { API_BASE } from "../lib/api";
import { Link } from "react-router-dom";

type PreviewItem = { ticker: string; name?: string | null; cik?: string | number | null; exchange?: string | null };
type UpdatedItem = {
  ticker: string;
  name_old?: string | null;
  name_new?: string | null;
  cik_old?: string | number | null;
  cik_new?: string | number | null;
};

export default function UniverseSyncPage() {
  const [preview, setPreview] = useState<{ new: PreviewItem[]; updated: UpdatedItem[]; existing: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<string | null>(null);
  const [mode, setMode] = useState<"new" | "updates">("new");
  const [trackNew, setTrackNew] = useState(true);
  const [trackRetickered, setTrackRetickered] = useState(true);
  const [runAnnual, setRunAnnual] = useState(true);
  const [runQuarterly, setRunQuarterly] = useState(true);
  const [backfillStatus, setBackfillStatus] = useState<string | null>(null);
  const [backfillResults, setBackfillResults] = useState<any[] | null>(null);

  const currentList = preview ? (mode === "new" ? preview.new || [] : preview.updated || []) : [];

  const fetchPreview = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/universe/sec/preview`);
      if (!res.ok) throw new Error(`preview ${res.status}`);
      const data = await res.json();
      setPreview(data);
      setSelected(new Set((data.new || []).map((r: PreviewItem) => r.ticker)));
      setMode("new");
    } catch (e: any) {
      setError(e.message || "Failed to fetch preview");
    } finally {
      setLoading(false);
    }
  };

  const apply = async () => {
    if (!preview) return;
    const tickers = Array.from(selected);
    if (tickers.length === 0) {
      setResult("No tickers selected.");
      return;
    }
    const updatesSet = new Set((preview.updated || []).map((r) => r.ticker));
    const includeUpdates = tickers.some((t) => updatesSet.has(t));
    setApplying(true);
    setError(null);
    setResult(null);
    setBackfillResults(null);
    setBackfillStatus(null);
    try {
      const res = await fetch(`${API_BASE}/universe/sec/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tickers,
          update_names: includeUpdates,
          track_new: trackNew,
          track_retickered: trackRetickered,
        }),
      });
      if (!res.ok) throw new Error(`apply ${res.status}`);
      const data = await res.json();
      const skipped = data.skipped_conflicts ? `, skipped ${data.skipped_conflicts} (CIK conflicts)` : "";
      const retickered = data.retickered ? `, retickered ${data.retickered}` : "";
      setResult(`Inserted ${data.inserted || 0}, updated ${data.updated || 0}${retickered}${skipped}`);

      // Optional backfill after apply
      if ((runAnnual || runQuarterly) && tickers.length) {
        setBackfillStatus("Running backfill…");
        const bfRes = await fetch(`${API_BASE}/universe/sec/backfill`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tickers,
            annual: runAnnual,
            quarterly: runQuarterly,
            only_if_missing: true,
            sleep_seconds: 0.75,
          }),
        });
        if (!bfRes.ok) throw new Error(`backfill ${bfRes.status}`);
        const bfData = await bfRes.json();
        setBackfillResults(bfData.results || []);
        setBackfillStatus("Backfill finished");
      }
    } catch (e: any) {
      setError(e.message || "Failed to apply updates");
    } finally {
      setApplying(false);
    }
  };

  const toggle = (t: string) => {
    const next = new Set(selected);
    if (next.has(t)) next.delete(t);
    else next.add(t);
    setSelected(next);
  };

  const selectAllCurrent = () => {
    const next = new Set(selected);
    currentList.forEach((row: any) => {
      if (row?.ticker) next.add(row.ticker);
    });
    setSelected(next);
  };

  const clearCurrent = () => {
    if (!currentList.length) return;
    const next = new Set(selected);
    currentList.forEach((row: any) => {
      if (row?.ticker) next.delete(row.ticker);
    });
    setSelected(next);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link to="/" className="text-sm text-sky-600 hover:underline">
          ← Back to Screener
        </Link>
        <h1 className="text-2xl font-bold">Universe Sync (SEC)</h1>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={fetchPreview}
          className="px-3 py-2 rounded-lg bg-sky-600 text-white hover:bg-sky-700 disabled:opacity-60"
          disabled={loading}
        >
          {loading ? "Checking…" : "Fetch & Compare"}
        </button>
        <button
          onClick={apply}
          className="px-3 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-60"
          disabled={applying || !preview}
        >
          {applying ? "Applying…" : "Insert Selected"}
        </button>
        {result && <span className="text-sm text-emerald-600">{result}</span>}
        {error && <span className="text-sm text-red-500">{error}</span>}
      </div>

      {preview ? (
        <div className="space-y-2">
          <div className="text-sm text-zinc-600 dark:text-zinc-400">
            {preview.new?.length || 0} new tickers, {preview.updated?.length || 0} updates, {preview.existing} existing.
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setMode("new")}
              className={`px-3 py-2 rounded-lg text-sm border ${
                mode === "new" ? "bg-sky-600 text-white border-sky-600" : "border-zinc-300 dark:border-zinc-700"
              }`}
            >
              New ({preview.new?.length || 0})
            </button>
            <button
              onClick={() => setMode("updates")}
              className={`px-3 py-2 rounded-lg text-sm border ${
                mode === "updates" ? "bg-sky-600 text-white border-sky-600" : "border-zinc-300 dark:border-zinc-700"
              }`}
            >
              Updates ({preview.updated?.length || 0})
            </button>
            <div className="flex items-center gap-2">
              <button
                onClick={selectAllCurrent}
                className="px-2 py-1 rounded-md text-xs border border-zinc-300 dark:border-zinc-700"
                disabled={!currentList.length}
              >
                Select all ({mode})
              </button>
              <button
                onClick={clearCurrent}
                className="px-2 py-1 rounded-md text-xs border border-zinc-300 dark:border-zinc-700"
                disabled={!currentList.length}
              >
                Clear ({mode})
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <label className="inline-flex items-center gap-2">
                <input type="checkbox" checked={trackNew} onChange={(e) => setTrackNew(e.target.checked)} />
                Track new
              </label>
              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={trackRetickered}
                  onChange={(e) => setTrackRetickered(e.target.checked)}
                />
                Track retickered
              </label>
              <label className="inline-flex items-center gap-2">
                <input type="checkbox" checked={runAnnual} onChange={(e) => setRunAnnual(e.target.checked)} />
                Backfill annual
              </label>
              <label className="inline-flex items-center gap-2">
                <input type="checkbox" checked={runQuarterly} onChange={(e) => setRunQuarterly(e.target.checked)} />
                Backfill quarterly
              </label>
            </div>
          </div>
          <div className="overflow-auto border border-zinc-200 dark:border-zinc-800 rounded-xl">
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 dark:bg-zinc-900/60">
                <tr>
                  <th className="px-3 py-2 text-left">Select</th>
                  <th className="px-3 py-2 text-left">Ticker</th>
                  <th className="px-3 py-2 text-left">Name</th>
                  <th className="px-3 py-2 text-left">CIK</th>
                  {mode === "new" ? <th className="px-3 py-2 text-left">Exchange</th> : <th className="px-3 py-2 text-left">Changes</th>}
                </tr>
              </thead>
              <tbody>
                {mode === "new"
                  ? (preview.new || []).map((row: PreviewItem) => (
                      <tr key={row.ticker} className="border-t border-zinc-200 dark:border-zinc-800">
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            checked={selected.has(row.ticker)}
                            onChange={() => toggle(row.ticker)}
                          />
                        </td>
                        <td className="px-3 py-2 font-semibold">{row.ticker}</td>
                        <td className="px-3 py-2">{row.name}</td>
                        <td className="px-3 py-2">{row.cik}</td>
                        <td className="px-3 py-2">{row.exchange || "—"}</td>
                      </tr>
                    ))
                  : (preview.updated || []).map((row: UpdatedItem) => (
                      <tr key={row.ticker} className="border-t border-zinc-200 dark:border-zinc-800">
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            checked={selected.has(row.ticker)}
                            onChange={() => toggle(row.ticker)}
                          />
                        </td>
                        <td className="px-3 py-2 font-semibold">{row.ticker}</td>
                        <td className="px-3 py-2">
                          <div className="flex flex-col">
                            <span className="line-through text-zinc-500">{row.name_old || "—"}</span>
                            <span>{row.name_new || "—"}</span>
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex flex-col">
                            <span className="line-through text-zinc-500">{row.cik_old || "—"}</span>
                            <span>{row.cik_new || "—"}</span>
                          </div>
                        </td>
                        <td className="px-3 py-2">Name/CIK change</td>
                      </tr>
                ))}
              </tbody>
            </table>
          </div>
          {backfillStatus && <div className="text-sm text-zinc-600 dark:text-zinc-400">{backfillStatus}</div>}
          {backfillResults && backfillResults.length > 0 && (
            <div className="overflow-auto border border-zinc-200 dark:border-zinc-800 rounded-xl">
              <table className="min-w-full text-sm">
                <thead className="bg-zinc-50 dark:bg-zinc-900/60">
                  <tr>
                    <th className="px-3 py-2 text-left">Ticker</th>
                    <th className="px-3 py-2 text-left">Annual</th>
                    <th className="px-3 py-2 text-left">Quarterly</th>
                    <th className="px-3 py-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {backfillResults.map((r: any) => (
                    <tr key={r.ticker} className="border-t border-zinc-200 dark:border-zinc-800">
                      <td className="px-3 py-2 font-semibold">{r.ticker}</td>
                      <td className="px-3 py-2">{r.annual_ran ? "ran" : "—"}</td>
                      <td className="px-3 py-2">{r.quarterly_ran ? "ran" : "—"}</td>
                      <td className="px-3 py-2">
                        {r.error ? <span className="text-red-500">{r.error}</span> : r.skipped ? "skipped" : "ok"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="text-sm text-zinc-500">Click “Fetch & Compare” to load the latest SEC list.</div>
      )}
    </div>
  );
}

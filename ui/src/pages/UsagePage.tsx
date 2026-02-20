import { useEffect, useMemo, useState } from "react";
import {
  fetchUsagePrices,
  fetchUsageSummary,
  LLMModelPrice,
  upsertUsagePrice,
  UsageSummary,
} from "../lib/api";

const card =
  "rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950";

const btn =
  "h-9 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900 " +
  "hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

const btnGhost =
  "h-9 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-200 " +
  "hover:bg-zinc-100/60 dark:hover:bg-zinc-800/60 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

const STORAGE_KEY = "watchtower_settings_admin_token";

function fmtInt(v: number) {
  return new Intl.NumberFormat().format(v || 0);
}

function fmtMoney(v: number) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(v || 0);
}

function defaultLookback(granularity: "hour" | "day" | "week" | "month" | "year") {
  return { hour: 48, day: 30, week: 12, month: 12, year: 5 }[granularity];
}

export default function UsagePage() {
  const [adminToken, setAdminToken] = useState("");
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [prices, setPrices] = useState<LLMModelPrice[]>([]);
  const [granularity, setGranularity] = useState<"hour" | "day" | "week" | "month" | "year">("day");
  const [lookback, setLookback] = useState<number>(30);
  const [modelFilter, setModelFilter] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [newModel, setNewModel] = useState("gpt-4.1");
  const [newInputPrice, setNewInputPrice] = useState(0);
  const [newOutputPrice, setNewOutputPrice] = useState(0);
  const [newCachePrice, setNewCachePrice] = useState(0);
  const [newActive, setNewActive] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);

  const loadAll = async (token: string) => {
    setLoading(true);
    try {
      setError(null);
      const [usageData, priceData] = await Promise.all([
        fetchUsageSummary(token, {
          granularity,
          lookback,
          model: modelFilter.trim() || undefined,
          provider: "openai",
        }),
        fetchUsagePrices(token),
      ]);
      setSummary(usageData);
      setPrices(priceData);
    } catch (err) {
      setError((err as Error).message || "Failed to load usage data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) || "";
    if (!stored) return;
    setAdminToken(stored);
    loadAll(stored);
  }, []);

  useEffect(() => {
    if (!adminToken) return;
    const refreshMs = 15000;
    if (!autoRefresh) return;
    const id = window.setInterval(() => {
      void loadAll(adminToken);
    }, refreshMs);
    return () => window.clearInterval(id);
  }, [adminToken, autoRefresh, granularity, lookback, modelFilter]);

  const handleSaveToken = () => {
    localStorage.setItem(STORAGE_KEY, adminToken);
    if (adminToken) void loadAll(adminToken);
  };

  const handleGranularityChange = (value: "hour" | "day" | "week" | "month" | "year") => {
    setGranularity(value);
    setLookback(defaultLookback(value));
  };

  const filteredPrices = useMemo(() => {
    const q = modelFilter.trim().toLowerCase();
    if (!q) return prices;
    return prices.filter((p) => p.model.toLowerCase().includes(q));
  }, [prices, modelFilter]);

  const savePrice = async (payload: {
    provider: string;
    model: string;
    input_per_million: number;
    output_per_million: number;
    cache_read_per_million: number;
    active: boolean;
  }) => {
    if (!adminToken) return;
    try {
      setError(null);
      await upsertUsagePrice(adminToken, payload);
      const fresh = await fetchUsagePrices(adminToken);
      setPrices(fresh);
    } catch (err) {
      setError((err as Error).message || "Failed to save price");
    }
  };

  const loadPriceForEdit = (price: LLMModelPrice) => {
    setEditingId(price.id);
    setNewModel(price.model);
    setNewInputPrice(price.input_per_million);
    setNewOutputPrice(price.output_per_million);
    setNewCachePrice(price.cache_read_per_million);
    setNewActive(price.active);
  };

  const clearEdit = () => {
    setEditingId(null);
    setNewModel("gpt-4.1");
    setNewInputPrice(0);
    setNewOutputPrice(0);
    setNewCachePrice(0);
    setNewActive(true);
  };

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <div className={`${card} p-6`}>
        <div className="text-xs uppercase tracking-wide text-zinc-500">Usage</div>
        <h1 className="text-2xl font-semibold">LLM Token Usage & Cost</h1>
        <p className="text-sm text-zinc-400">
          Monitor requests in near real time. Filter by interval and model, and set per-model pricing to track spend.
        </p>
      </div>

      <div className={`${card} p-4 space-y-3`}>
        <div className="text-sm font-semibold">Admin Token</div>
        <div className="flex gap-2">
          <input
            value={adminToken}
            onChange={(e) => setAdminToken(e.target.value)}
            placeholder="Paste admin token"
            className="flex-1 h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
          />
          <button className={btn} onClick={handleSaveToken}>
            Save
          </button>
        </div>
        {error ? <div className="text-sm text-red-400">{error}</div> : null}
      </div>

      <div className={`${card} p-4 grid grid-cols-1 lg:grid-cols-6 gap-3 items-end`}>
        <label className="lg:col-span-1 text-sm">
          Interval
          <select
            value={granularity}
            onChange={(e) => handleGranularityChange(e.target.value as "hour" | "day" | "week" | "month" | "year")}
            className="mt-1 w-full h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
          >
            <option value="hour">Hourly</option>
            <option value="day">Daily</option>
            <option value="week">Weekly</option>
            <option value="month">Monthly</option>
            <option value="year">Yearly</option>
          </select>
        </label>
        <label className="lg:col-span-1 text-sm">
          Lookback
          <input
            type="number"
            value={lookback}
            onChange={(e) => setLookback(Number(e.target.value))}
            className="mt-1 w-full h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
          />
        </label>
        <label className="lg:col-span-2 text-sm">
          Model Filter
          <input
            value={modelFilter}
            onChange={(e) => setModelFilter(e.target.value)}
            placeholder="e.g. gpt-4.1, gpt-5"
            className="mt-1 w-full h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
          />
        </label>
        <label className="lg:col-span-1 text-sm flex items-center gap-2 h-9">
          <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
          Auto refresh (15s)
        </label>
        <button
          className={`${btnGhost} lg:col-span-1`}
          onClick={() => adminToken && loadAll(adminToken)}
          disabled={!adminToken || loading}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <div className={`${card} p-4`}>
          <div className="text-xs text-zinc-500 uppercase tracking-wide">Total Cost</div>
          <div className="text-2xl font-semibold mt-1">{fmtMoney(summary?.totals.cost || 0)}</div>
        </div>
        <div className={`${card} p-4`}>
          <div className="text-xs text-zinc-500 uppercase tracking-wide">Total Tokens</div>
          <div className="text-2xl font-semibold mt-1">{fmtInt(summary?.totals.total_tokens || 0)}</div>
          <div className="text-xs text-zinc-500 mt-1">
            In: {fmtInt(summary?.totals.input_tokens || 0)} · Out: {fmtInt(summary?.totals.output_tokens || 0)}
          </div>
        </div>
        <div className={`${card} p-4`}>
          <div className="text-xs text-zinc-500 uppercase tracking-wide">Requests</div>
          <div className="text-2xl font-semibold mt-1">{fmtInt(summary?.totals.requests || 0)}</div>
        </div>
        <div className={`${card} p-4`}>
          <div className="text-xs text-zinc-500 uppercase tracking-wide">Cache Read Tokens</div>
          <div className="text-2xl font-semibold mt-1">{fmtInt(summary?.totals.cached_input_tokens || 0)}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className={`${card} p-4`}>
          <div className="text-sm font-semibold">Trend by {granularity}</div>
          <div className="mt-3 overflow-auto max-h-[420px]">
            <table className="min-w-full text-sm">
              <thead className="text-left text-zinc-500">
                <tr>
                  <th className="py-2">Bucket</th>
                  <th className="py-2 text-right">Requests</th>
                  <th className="py-2 text-right">Tokens</th>
                  <th className="py-2 text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {(summary?.buckets ?? []).map((b) => (
                  <tr key={b.bucket} className="border-t border-zinc-200 dark:border-zinc-800">
                    <td className="py-2">{b.bucket.replace("T", " ").slice(0, 16)}</td>
                    <td className="py-2 text-right">{fmtInt(b.requests)}</td>
                    <td className="py-2 text-right">{fmtInt(b.total_tokens)}</td>
                    <td className="py-2 text-right">{fmtMoney(b.cost)}</td>
                  </tr>
                ))}
                {(summary?.buckets ?? []).length === 0 ? (
                  <tr>
                    <td className="py-2 text-zinc-500" colSpan={4}>
                      No usage events in this window.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>

        <div className={`${card} p-4`}>
          <div className="text-sm font-semibold">Model Breakdown</div>
          <div className="mt-3 overflow-auto max-h-[420px]">
            <table className="min-w-full text-sm">
              <thead className="text-left text-zinc-500">
                <tr>
                  <th className="py-2">Model</th>
                  <th className="py-2 text-right">Requests</th>
                  <th className="py-2 text-right">Tokens</th>
                  <th className="py-2 text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {(summary?.by_model ?? []).map((m) => (
                  <tr key={`${m.provider}:${m.model}`} className="border-t border-zinc-200 dark:border-zinc-800">
                    <td className="py-2">
                      <div className="font-medium">{m.model}</div>
                      <div className="text-xs text-zinc-500">{m.provider}</div>
                    </td>
                    <td className="py-2 text-right">{fmtInt(m.requests)}</td>
                    <td className="py-2 text-right">{fmtInt(m.total_tokens)}</td>
                    <td className="py-2 text-right">{fmtMoney(m.cost)}</td>
                  </tr>
                ))}
                {(summary?.by_model ?? []).length === 0 ? (
                  <tr>
                    <td className="py-2 text-zinc-500" colSpan={4}>
                      No model usage in this window.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className={`${card} p-4 space-y-3`}>
        <div className="text-sm font-semibold">Model Pricing (per 1M tokens)</div>
        {editingId ? (
          <div className="text-xs text-zinc-500">
            Editing existing model pricing. Save will update that model.
          </div>
        ) : null}
        <div className="grid grid-cols-1 md:grid-cols-6 gap-2 items-end">
          <label className="md:col-span-2 text-sm">
            Model
            <input
              value={newModel}
              onChange={(e) => setNewModel(e.target.value)}
              className="mt-1 w-full h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
            />
          </label>
          <label className="text-sm">
            Input $
            <input
              type="number"
              step="0.000001"
              value={newInputPrice}
              onChange={(e) => setNewInputPrice(Number(e.target.value))}
              className="mt-1 w-full h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
            />
          </label>
          <label className="text-sm">
            Output $
            <input
              type="number"
              step="0.000001"
              value={newOutputPrice}
              onChange={(e) => setNewOutputPrice(Number(e.target.value))}
              className="mt-1 w-full h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
            />
          </label>
          <label className="text-sm">
            Cache $
            <input
              type="number"
              step="0.000001"
              value={newCachePrice}
              onChange={(e) => setNewCachePrice(Number(e.target.value))}
              className="mt-1 w-full h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
            />
          </label>
          <div className="flex items-center gap-2">
            <label className="text-sm inline-flex items-center gap-2">
              <input type="checkbox" checked={newActive} onChange={(e) => setNewActive(e.target.checked)} />
              Active
            </label>
            <button
              className={btn}
              onClick={() =>
                savePrice({
                  provider: "openai",
                  model: newModel.trim(),
                  input_per_million: newInputPrice,
                  output_per_million: newOutputPrice,
                  cache_read_per_million: newCachePrice,
                  active: newActive,
                })
              }
              disabled={!adminToken || !newModel.trim()}
            >
              {editingId ? "Update" : "Save"}
            </button>
            {editingId ? (
              <button className={btnGhost} onClick={clearEdit}>
                Cancel
              </button>
            ) : null}
          </div>
        </div>

        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-zinc-500">
              <tr>
                <th className="py-2">Model</th>
                <th className="py-2 text-right">Input $/1M</th>
                <th className="py-2 text-right">Output $/1M</th>
                <th className="py-2 text-right">Cache $/1M</th>
                <th className="py-2 text-right">Active</th>
                <th className="py-2 text-right">Edit</th>
              </tr>
            </thead>
            <tbody>
              {filteredPrices.map((p) => (
                <tr key={p.id} className="border-t border-zinc-200 dark:border-zinc-800">
                  <td className="py-2">
                    <div className="font-medium">{p.model}</div>
                    <div className="text-xs text-zinc-500">{p.provider}</div>
                  </td>
                  <td className="py-2 text-right">{p.input_per_million.toFixed(6)}</td>
                  <td className="py-2 text-right">{p.output_per_million.toFixed(6)}</td>
                  <td className="py-2 text-right">{p.cache_read_per_million.toFixed(6)}</td>
                  <td className="py-2 text-right">{p.active ? "Yes" : "No"}</td>
                  <td className="py-2 text-right">
                    <button className={btnGhost} onClick={() => loadPriceForEdit(p)}>
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
              {filteredPrices.length === 0 ? (
                <tr>
                  <td className="py-2 text-zinc-500" colSpan={6}>
                    No model prices configured.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

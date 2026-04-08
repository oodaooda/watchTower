import { useCallback, useEffect, useMemo, useState } from "react";
import BackButton from "../components/BackButton";
import {
  createPortfolioPosition,
  deletePortfolioPosition,
  fetchPortfolio,
  PortfolioOverviewOut,
  PortfolioPosition,
  updatePortfolioPosition,
} from "../lib/api";

const card =
  "rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950";

const btn =
  "h-9 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900 " +
  "hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-sky-500/30 disabled:opacity-40";

const btnGhost =
  "h-9 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-200 " +
  "hover:bg-zinc-100/60 dark:hover:bg-zinc-800/60 focus:outline-none focus:ring-2 focus:ring-sky-500/30 disabled:opacity-40";

function fmtCurrency(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
}

function fmtPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 2, signDisplay: "auto" }).format(value);
}

function fmtNumber(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(value);
}

function priceStatusLabel(status?: string | null) {
  if (status === "live") return "Live";
  if (status === "cached") return "Cached";
  return "Unavailable";
}

export default function PortfolioPage() {
  const [portfolio, setPortfolio] = useState<PortfolioOverviewOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingTicker, setEditingTicker] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgCostBasis, setAvgCostBasis] = useState("");
  const [notes, setNotes] = useState("");

  const loadPortfolio = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const data = await fetchPortfolio();
      setPortfolio(data);
    } catch (err) {
      setError((err as Error).message || "Failed to load portfolio");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPortfolio();
  }, [loadPortfolio]);

  const resetForm = () => {
    setEditingTicker(null);
    setSymbol("");
    setQuantity("");
    setAvgCostBasis("");
    setNotes("");
  };

  const handleEdit = (position: PortfolioPosition) => {
    setEditingTicker(position.ticker);
    setSymbol(position.ticker);
    setQuantity(String(position.quantity));
    setAvgCostBasis(String(position.avg_cost_basis));
    setNotes(position.notes || "");
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const ticker = symbol.trim().toUpperCase();
    const parsedQuantity = Number(quantity);
    const parsedAvgCost = Number(avgCostBasis);
    if (!ticker || !Number.isFinite(parsedQuantity) || parsedQuantity <= 0 || !Number.isFinite(parsedAvgCost) || parsedAvgCost < 0) {
      setError("Enter a valid symbol, quantity, and average cost basis.");
      return;
    }

    setSaving(true);
    try {
      setError(null);
      const payload = {
        quantity: parsedQuantity,
        avg_cost_basis: parsedAvgCost,
        notes: notes.trim() || undefined,
      };
      const data = editingTicker
        ? await updatePortfolioPosition(editingTicker, payload)
        : await createPortfolioPosition({ ticker, ...payload });
      setPortfolio(data);
      resetForm();
    } catch (err) {
      setError((err as Error).message || "Failed to save portfolio position");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (ticker: string) => {
    setSaving(true);
    try {
      setError(null);
      const data = await deletePortfolioPosition(ticker);
      setPortfolio(data);
      if (editingTicker === ticker) {
        resetForm();
      }
    } catch (err) {
      setError((err as Error).message || "Failed to delete portfolio position");
    } finally {
      setSaving(false);
    }
  };

  const summary = portfolio?.summary;
  const positions = portfolio?.positions || [];

  const cards = useMemo(
    () => [
      { label: "Total Cost Basis", value: fmtCurrency(summary?.total_cost_basis) },
      { label: "Market Value", value: fmtCurrency(summary?.total_market_value) },
      { label: "Unrealized Gain/Loss", value: fmtCurrency(summary?.total_unrealized_gain_loss) },
      { label: "Gain/Loss %", value: fmtPercent(summary?.total_unrealized_gain_loss_pct) },
    ],
    [summary],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <BackButton />
          <div>
            <h1 className="text-2xl font-bold">Portfolio</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Track mixed stock and ETF holdings with quantity, cost basis, and unrealized gain/loss.
            </p>
          </div>
        </div>
        <button className={btnGhost} onClick={() => void loadPortfolio()} disabled={loading || saving}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((item) => (
          <div key={item.label} className={`${card} p-4`}>
            <div className="text-xs uppercase tracking-wide text-zinc-500">{item.label}</div>
            <div className="mt-2 text-2xl font-semibold">{item.value}</div>
          </div>
        ))}
      </div>

      {summary?.has_unpriced_positions ? (
        <div className="rounded-2xl border border-amber-300/40 bg-amber-50/60 px-4 py-3 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-200">
          {summary.unpriced_positions} position{summary.unpriced_positions === 1 ? "" : "s"} do not have a usable quote yet, so market value and gain totals are incomplete.
        </div>
      ) : null}

      <div className={`${card} p-4`}>
        <div className="mb-3 text-sm font-semibold">{editingTicker ? `Edit ${editingTicker}` : "Add Position"}</div>
        <form onSubmit={handleSubmit} className="grid gap-3 md:grid-cols-4 xl:grid-cols-6">
          <label className="text-sm">
            Symbol
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase().replace(/[^A-Z0-9.-]/g, ""))}
              placeholder="AAPL or VGT"
              disabled={Boolean(editingTicker)}
              className="mt-1 h-10 w-full rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm uppercase disabled:opacity-60"
            />
          </label>
          <label className="text-sm">
            Quantity
            <input
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="10"
              inputMode="decimal"
              className="mt-1 h-10 w-full rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
            />
          </label>
          <label className="text-sm">
            Avg Cost Basis
            <input
              value={avgCostBasis}
              onChange={(e) => setAvgCostBasis(e.target.value)}
              placeholder="150"
              inputMode="decimal"
              className="mt-1 h-10 w-full rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
            />
          </label>
          <label className="text-sm md:col-span-2 xl:col-span-2">
            Notes
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional note"
              className="mt-1 h-10 w-full rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
            />
          </label>
          <div className="flex items-end gap-2 md:col-span-4 xl:col-span-2">
            <button type="submit" className={btn} disabled={saving}>
              {saving ? "Saving..." : editingTicker ? "Update Position" : "Add Position"}
            </button>
            <button type="button" className={btnGhost} onClick={resetForm} disabled={saving}>
              Clear
            </button>
          </div>
        </form>
        {error ? <div className="mt-3 text-sm text-red-500">{error}</div> : null}
      </div>

      <div className="overflow-auto rounded-2xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900/60 text-left text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-3 py-3">Symbol</th>
              <th className="px-3 py-3">Asset</th>
              <th className="px-3 py-3">Type</th>
              <th className="px-3 py-3 text-right">Quantity</th>
              <th className="px-3 py-3 text-right">Avg Cost</th>
              <th className="px-3 py-3 text-right">Cost Basis</th>
              <th className="px-3 py-3 text-right">Price</th>
              <th className="px-3 py-3 text-right">Market Value</th>
              <th className="px-3 py-3 text-right">Gain/Loss</th>
              <th className="px-3 py-3 text-right">Gain/Loss %</th>
              <th className="px-3 py-3 text-right">Weight</th>
              <th className="px-3 py-3 text-right">Price State</th>
              <th className="px-3 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 ? (
              <tr>
                <td className="px-3 py-6 text-center text-zinc-500" colSpan={13}>
                  {loading ? "Loading portfolio..." : "No positions yet — add a stock or ETF above."}
                </td>
              </tr>
            ) : (
              positions.map((position) => (
                <tr
                  key={position.position_id}
                  className="border-t border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50/70 dark:hover:bg-zinc-900/40"
                >
                  <td className="px-3 py-3 font-semibold">{position.ticker}</td>
                  <td className="px-3 py-3">{position.name || "—"}</td>
                  <td className="px-3 py-3 uppercase">{position.asset_type}</td>
                  <td className="px-3 py-3 text-right">{fmtNumber(position.quantity)}</td>
                  <td className="px-3 py-3 text-right">{fmtCurrency(position.avg_cost_basis)}</td>
                  <td className="px-3 py-3 text-right">{fmtCurrency(position.total_cost_basis)}</td>
                  <td className="px-3 py-3 text-right">{fmtCurrency(position.current_price)}</td>
                  <td className="px-3 py-3 text-right">{fmtCurrency(position.market_value)}</td>
                  <td className={`px-3 py-3 text-right ${position.unrealized_gain_loss && position.unrealized_gain_loss > 0 ? "text-emerald-500" : position.unrealized_gain_loss && position.unrealized_gain_loss < 0 ? "text-red-500" : ""}`}>
                    {fmtCurrency(position.unrealized_gain_loss)}
                  </td>
                  <td className={`px-3 py-3 text-right ${position.unrealized_gain_loss_pct && position.unrealized_gain_loss_pct > 0 ? "text-emerald-500" : position.unrealized_gain_loss_pct && position.unrealized_gain_loss_pct < 0 ? "text-red-500" : ""}`}>
                    {fmtPercent(position.unrealized_gain_loss_pct)}
                  </td>
                  <td className="px-3 py-3 text-right">{fmtPercent(position.portfolio_weight)}</td>
                  <td className="px-3 py-3 text-right text-xs text-zinc-500">{priceStatusLabel(position.price_status)}</td>
                  <td className="px-3 py-3 text-right">
                    <div className="flex justify-end gap-3">
                      <button className="text-sm text-sky-600 hover:underline" onClick={() => handleEdit(position)}>
                        Edit
                      </button>
                      <button className="text-sm text-red-500 hover:underline" onClick={() => void handleDelete(position.ticker)}>
                        Remove
                      </button>
                    </div>
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

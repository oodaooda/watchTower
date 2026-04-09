import { useCallback, useEffect, useMemo, useState } from "react";
import BackButton from "../components/BackButton";
import {
  createPortfolioPosition,
  deletePortfolioPosition,
  fetchPortfolio,
  importPortfolioPositions,
  PortfolioOverviewOut,
  PortfolioPosition,
  PortfolioTickerGroup,
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

type ParsedImportRow = {
  ticker: string;
  quantity: number;
  avg_cost_basis: number;
  notes?: string;
};

type ParsedImportPreview = {
  rows: ParsedImportRow[];
  errors: string[];
};

const headerAliases: Record<string, string> = {
  ticker: "ticker",
  symbol: "ticker",
  shares: "quantity",
  quantity: "quantity",
  units: "quantity",
  "cost basis": "avg_cost_basis",
  cost_basis: "avg_cost_basis",
  avg_cost_basis: "avg_cost_basis",
  average_cost_basis: "avg_cost_basis",
  notes: "notes",
  note: "notes",
  description: "ignore",
  "trade date": "ignore",
  trade_date: "ignore",
};

function normalizeHeader(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function looksLikeHeader(cells: string[]) {
  return cells.some((cell) => {
    const normalized = normalizeHeader(cell);
    return normalized in headerAliases || normalized === "cost" || normalized === "basis";
  });
}

function parseDelimitedLine(line: string) {
  if (line.includes("\t")) return line.split("\t").map((cell) => cell.trim());
  return line.split(",").map((cell) => cell.trim());
}

function parsePortfolioImport(raw: string): ParsedImportPreview {
  const lines = raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return { rows: [], errors: [] };

  const firstCells = parseDelimitedLine(lines[0]);
  const hasHeader = looksLikeHeader(firstCells);
  const rows: ParsedImportRow[] = [];
  const errors: string[] = [];
  let headerMap: Record<string, number> = {};

  if (hasHeader) {
    firstCells.forEach((cell, idx) => {
      const normalized = normalizeHeader(cell);
      const canonical =
        headerAliases[normalized] ??
        (normalized === "cost" || normalized === "basis" ? "avg_cost_basis" : undefined);
      if (canonical) headerMap[canonical] = idx;
    });
  }

  const dataLines = hasHeader ? lines.slice(1) : lines;
  dataLines.forEach((line, lineIdx) => {
    const cells = parseDelimitedLine(line);
    const rowNumber = lineIdx + (hasHeader ? 2 : 1);

    const tickerCell =
      headerMap.ticker !== undefined
        ? cells[headerMap.ticker]
        : cells.length >= 2 && !/^[A-Z][A-Z0-9.-]*$/.test(cells[0] || "")
          ? cells[1]
          : cells[0];
    const quantityCell =
      headerMap.quantity !== undefined
        ? cells[headerMap.quantity]
        : cells.length >= 3
          ? cells[cells.length >= 4 ? 2 : 1]
          : undefined;
    const costBasisCell =
      headerMap.avg_cost_basis !== undefined
        ? cells[headerMap.avg_cost_basis]
        : cells.length >= 3
          ? cells[cells.length - 1]
          : undefined;
    const notesCell = headerMap.notes !== undefined ? cells[headerMap.notes] : undefined;

    const ticker = (tickerCell || "").toUpperCase().replace(/[^A-Z0-9.-]/g, "");
    const quantity = Number((quantityCell || "").replace(/,/g, ""));
    const avgCostBasis = Number((costBasisCell || "").replace(/[$,]/g, ""));

    if (!ticker || !Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(avgCostBasis) || avgCostBasis < 0) {
      errors.push(`Line ${rowNumber}: expected ticker, quantity, and cost basis`);
      return;
    }

    rows.push({
      ticker,
      quantity,
      avg_cost_basis: avgCostBasis,
      notes: notesCell || undefined,
    });
  });

  return { rows, errors };
}

export default function PortfolioPage() {
  const [portfolio, setPortfolio] = useState<PortfolioOverviewOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingPositionId, setEditingPositionId] = useState<number | null>(null);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [showEditPanel, setShowEditPanel] = useState(false);
  const [showImportPanel, setShowImportPanel] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgCostBasis, setAvgCostBasis] = useState("");
  const [notes, setNotes] = useState("");
  const [importText, setImportText] = useState("");

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
    setEditingPositionId(null);
    setSymbol("");
    setQuantity("");
    setAvgCostBasis("");
    setNotes("");
    setShowEditPanel(false);
  };

  const handleEdit = (position: PortfolioPosition) => {
    setEditingPositionId(position.position_id);
    setSymbol(position.ticker);
    setQuantity(String(position.quantity));
    setAvgCostBasis(String(position.avg_cost_basis));
    setNotes(position.notes || "");
    setSelectedTicker(position.ticker);
    setShowEditPanel(true);
  };

  const importPreview = useMemo(() => parsePortfolioImport(importText), [importText]);

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
        entry_source: "manual",
        notes: notes.trim() || undefined,
      };
      const data = editingPositionId
        ? await updatePortfolioPosition(editingPositionId, payload)
        : await createPortfolioPosition({ ticker, ...payload });
      setPortfolio(data);
      resetForm();
    } catch (err) {
      setError((err as Error).message || "Failed to save portfolio position");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (positionId: number) => {
    setSaving(true);
    try {
      setError(null);
      const data = await deletePortfolioPosition(positionId);
      setPortfolio(data);
      if (editingPositionId === positionId) {
        resetForm();
      }
    } catch (err) {
      setError((err as Error).message || "Failed to delete portfolio position");
    } finally {
      setSaving(false);
    }
  };

  const handleReplaceImport = async () => {
    if (!importPreview.rows.length || importPreview.errors.length) return;
    setSaving(true);
    try {
      setError(null);
      const data = await importPortfolioPositions(importPreview.rows, true);
      setPortfolio(data);
      setImportText("");
      setShowImportPanel(false);
      resetForm();
    } catch (err) {
      setError((err as Error).message || "Failed to import portfolio");
    } finally {
      setSaving(false);
    }
  };

  const summary = portfolio?.summary;
  const positions = portfolio?.positions || [];
  const groups = portfolio?.groups || [];
  const selectedLots = useMemo(
    () => positions.filter((position) => position.ticker === selectedTicker),
    [positions, selectedTicker],
  );

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
              Track mixed stock and ETF holdings with duplicate lots, grouped summaries, and unrealized gain/loss.
            </p>
          </div>
        </div>
        <button className={btnGhost} onClick={() => void loadPortfolio()} disabled={loading || saving}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          className={btn}
          onClick={() => {
            resetForm();
            setShowEditPanel(true);
          }}
          disabled={saving}
        >
          Add Position
        </button>
        <button className={btnGhost} onClick={() => setShowImportPanel((value) => !value)} disabled={saving}>
          {showImportPanel ? "Hide Import" : "Import Portfolio"}
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

      {showImportPanel ? (
        <div className={`${card} p-4 space-y-3`}>
          <div>
            <div className="text-sm font-semibold">Replace Portfolio From Paste</div>
            <div className="text-xs text-zinc-500 dark:text-zinc-400">
              Canonical format: <code>ticker,quantity,avg_cost_basis[,notes]</code>. Header rows are accepted, and pasted tables with
              columns like Symbol, Shares, and Cost Basis are also recognized. This import replaces the current saved portfolio.
            </div>
          </div>
          <textarea
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder={"ticker,quantity,avg_cost_basis\nAMD,26,219.18\nAMD,10,189.79\nVGT,509.913,619.22"}
            className="min-h-32 w-full rounded-2xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-3 text-sm"
          />
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <div className="text-zinc-500">Parsed rows: {importPreview.rows.length}</div>
            <div className={importPreview.errors.length ? "text-red-500" : "text-zinc-500"}>
              Errors: {importPreview.errors.length}
            </div>
            <button className={btn} onClick={() => void handleReplaceImport()} disabled={saving || !importPreview.rows.length || importPreview.errors.length > 0}>
              {saving ? "Importing..." : "Replace Portfolio"}
            </button>
          </div>
          {importPreview.errors.length ? (
            <div className="rounded-2xl border border-red-300/40 bg-red-50/60 px-4 py-3 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-950/30 dark:text-red-200">
              {importPreview.errors.map((message) => (
                <div key={message}>{message}</div>
              ))}
            </div>
          ) : null}
          {importPreview.rows.length ? (
            <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 p-3 text-sm">
              <div className="mb-2 font-medium">Import preview</div>
              <div className="space-y-1 text-zinc-600 dark:text-zinc-300">
                {importPreview.rows.slice(0, 8).map((row, idx) => (
                  <div key={`${row.ticker}-${idx}`}>
                    {row.ticker}: {fmtNumber(row.quantity)} units at {fmtCurrency(row.avg_cost_basis)}
                    {row.notes ? ` (${row.notes})` : ""}
                  </div>
                ))}
                {importPreview.rows.length > 8 ? <div>…and {importPreview.rows.length - 8} more row(s).</div> : null}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {summary?.has_unpriced_positions ? (
        <div className="rounded-2xl border border-amber-300/40 bg-amber-50/60 px-4 py-3 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-200">
          {summary.unpriced_positions} position{summary.unpriced_positions === 1 ? "" : "s"} do not have a usable quote yet, so market value and gain totals are incomplete.
        </div>
      ) : null}

      {showEditPanel ? (
        <div className={`${card} p-4`}>
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="text-sm font-semibold">{editingPositionId ? `Edit Position #${editingPositionId}` : "Add Position"}</div>
            <button type="button" className={btnGhost} onClick={resetForm} disabled={saving}>
              Close
            </button>
          </div>
          <form onSubmit={handleSubmit} className="grid gap-3 md:grid-cols-4 xl:grid-cols-6">
            <label className="text-sm">
              Symbol
              <input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase().replace(/[^A-Z0-9.-]/g, ""))}
                placeholder="AAPL or VGT"
                disabled={Boolean(editingPositionId)}
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
                {saving ? "Saving..." : editingPositionId ? "Update Position" : "Add Position"}
              </button>
              <button type="button" className={btnGhost} onClick={resetForm} disabled={saving}>
                Clear
              </button>
            </div>
          </form>
          {error ? <div className="mt-3 text-sm text-red-500">{error}</div> : null}
        </div>
      ) : error ? (
        <div className="text-sm text-red-500">{error}</div>
      ) : null}

      <div className="overflow-auto rounded-2xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900/60 text-left text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-3 py-3">Ticker</th>
              <th className="px-3 py-3">Asset</th>
              <th className="px-3 py-3 text-right">Lots</th>
              <th className="px-3 py-3 text-right">Total Qty</th>
              <th className="px-3 py-3 text-right">Weighted Avg Cost</th>
              <th className="px-3 py-3 text-right">Cost Basis</th>
              <th className="px-3 py-3 text-right">Price</th>
              <th className="px-3 py-3 text-right">Market Value</th>
              <th className="px-3 py-3 text-right">Gain/Loss</th>
              <th className="px-3 py-3 text-right">Weight</th>
              <th className="px-3 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {groups.length === 0 ? (
              <tr>
                <td className="px-3 py-6 text-center text-zinc-500" colSpan={11}>
                  {loading ? "Loading grouped summary..." : "No grouped holdings yet."}
                </td>
              </tr>
            ) : (
              groups.map((group: PortfolioTickerGroup) => (
                <tr key={group.ticker} className="border-t border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50/70 dark:hover:bg-zinc-900/40">
                  <td className="px-3 py-3 font-semibold">{group.ticker}</td>
                  <td className="px-3 py-3">{group.name || "—"}</td>
                  <td className="px-3 py-3 text-right">{group.lot_count}</td>
                  <td className="px-3 py-3 text-right">{fmtNumber(group.total_quantity)}</td>
                  <td className="px-3 py-3 text-right">{fmtCurrency(group.weighted_avg_cost_basis)}</td>
                  <td className="px-3 py-3 text-right">{fmtCurrency(group.total_cost_basis)}</td>
                  <td className="px-3 py-3 text-right">{fmtCurrency(group.current_price)}</td>
                  <td className="px-3 py-3 text-right">{fmtCurrency(group.market_value)}</td>
                  <td className={`px-3 py-3 text-right ${group.unrealized_gain_loss && group.unrealized_gain_loss > 0 ? "text-emerald-500" : group.unrealized_gain_loss && group.unrealized_gain_loss < 0 ? "text-red-500" : ""}`}>
                    {fmtCurrency(group.unrealized_gain_loss)}
                  </td>
                  <td className="px-3 py-3 text-right">{fmtPercent(group.portfolio_weight)}</td>
                  <td className="px-3 py-3 text-right">
                    <button className="text-sm text-sky-600 hover:underline" onClick={() => setSelectedTicker(group.ticker)}>
                      {selectedTicker === group.ticker ? "Viewing Lots" : group.lot_count > 1 ? "View Lots" : "Manage"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {selectedTicker ? (
        <div className={`${card} p-4`}>
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">{selectedTicker} Lots</div>
              <div className="text-xs text-zinc-500 dark:text-zinc-400">
                Manage the individual lots that roll up into the grouped holding.
              </div>
            </div>
            <button type="button" className={btnGhost} onClick={() => setSelectedTicker(null)}>
              Close
            </button>
          </div>
          <div className="overflow-auto rounded-2xl border border-zinc-200 dark:border-zinc-800">
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 dark:bg-zinc-900/60 text-left text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-3 py-3">ID</th>
                  <th className="px-3 py-3 text-right">Source</th>
                  <th className="px-3 py-3 text-right">Quantity</th>
                  <th className="px-3 py-3 text-right">Avg Cost</th>
                  <th className="px-3 py-3 text-right">Cost Basis</th>
                  <th className="px-3 py-3 text-right">Price</th>
                  <th className="px-3 py-3 text-right">Market Value</th>
                  <th className="px-3 py-3 text-right">Gain/Loss</th>
                  <th className="px-3 py-3 text-right">Gain/Loss %</th>
                  <th className="px-3 py-3 text-right">Price State</th>
                  <th className="px-3 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {selectedLots.map((position) => (
                  <tr
                    key={position.position_id}
                    className="border-t border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50/70 dark:hover:bg-zinc-900/40"
                  >
                    <td className="px-3 py-3 text-zinc-500">{position.position_id}</td>
                    <td className="px-3 py-3 text-right uppercase text-xs text-zinc-500">{position.entry_source}</td>
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
                    <td className="px-3 py-3 text-right text-xs text-zinc-500">{priceStatusLabel(position.price_status)}</td>
                    <td className="px-3 py-3 text-right">
                      <div className="flex justify-end gap-3">
                        <button className="text-sm text-sky-600 hover:underline" onClick={() => handleEdit(position)}>
                          Edit
                        </button>
                        <button className="text-sm text-red-500 hover:underline" onClick={() => void handleDelete(position.position_id)}>
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}

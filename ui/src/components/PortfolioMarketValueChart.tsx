import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PortfolioSnapshotHistory } from "../lib/api";

type Props = {
  history: PortfolioSnapshotHistory | null;
  loading: boolean;
  error: string | null;
  saving: boolean;
  onRunSnapshot: () => void;
};

function fmtCurrency(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
}

function fmtPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 2, signDisplay: "auto" }).format(value);
}

export default function PortfolioMarketValueChart({ history, loading, error, saving, onRunSnapshot }: Props) {
  const snapshots = history?.snapshots ?? [];
  const chartData = useMemo(
    () =>
      snapshots
        .filter((snapshot) => snapshot.total_market_value !== null && snapshot.total_market_value !== undefined)
        .map((snapshot) => ({
          ts: new Date(`${snapshot.snapshot_date}T00:00:00`).getTime(),
          marketValue: Number(snapshot.total_market_value),
          costBasis: Number(snapshot.total_cost_basis),
          complete: snapshot.is_complete,
          isInferred: snapshot.is_inferred,
          source: snapshot.source,
        })),
    [snapshots],
  );

  const latestSnapshot = snapshots.length ? snapshots[snapshots.length - 1] : undefined;
  const incompleteCount = snapshots.filter((snapshot) => !snapshot.is_complete).length;
  const inferredBaseline = snapshots.find((snapshot) => snapshot.is_inferred);
  const summaryCards = [
    { key: "1d", label: "1D Market Value Change" },
    { key: "1m", label: "1M Market Value Change" },
    { key: "ytd", label: "YTD Market Value Change" },
    { key: "1y", label: "1Y Market Value Change" },
  ].map((item) => ({
    ...item,
    change: history?.summary?.[item.key]?.change,
    changePct: history?.summary?.[item.key]?.change_pct,
  }));

  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Portfolio Market Value History</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Starts with an inferred cost-basis baseline, then uses stored EOD closes. This is market value change, not cash-flow adjusted performance.
          </p>
        </div>
        <button
          className="h-9 px-3 rounded-xl font-medium inline-flex items-center justify-center border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-100/60 dark:hover:bg-zinc-800/60 focus:outline-none focus:ring-2 focus:ring-sky-500/30 disabled:opacity-40"
          onClick={onRunSnapshot}
          disabled={loading || saving}
        >
          {saving ? "Recording..." : "Record Snapshot"}
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        {summaryCards.map((item) => (
          <div key={item.key} className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-3">
            <div className="text-xs uppercase tracking-wide text-zinc-500">{item.label}</div>
            <div className={`mt-1 text-lg font-semibold ${item.change && item.change > 0 ? "text-emerald-500" : item.change && item.change < 0 ? "text-red-500" : ""}`}>
              {fmtCurrency(item.change)}
            </div>
            <div className="text-sm text-zinc-500">{fmtPercent(item.changePct)}</div>
          </div>
        ))}
      </div>

      {latestSnapshot ? (
        <div className="flex flex-wrap gap-3 text-xs text-zinc-500 dark:text-zinc-400">
          <span>Latest snapshot: {latestSnapshot.snapshot_date}</span>
          <span>Priced positions: {latestSnapshot.priced_positions}</span>
          <span>Unpriced positions: {latestSnapshot.unpriced_positions}</span>
          {inferredBaseline ? <span>Baseline: inferred from current cost basis</span> : null}
        </div>
      ) : null}

      {incompleteCount ? (
        <div className="rounded-xl border border-amber-300/40 bg-amber-50/60 px-3 py-2 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-200">
          {incompleteCount} snapshot{incompleteCount === 1 ? "" : "s"} are incomplete because at least one position did not have an EOD close for that date. Incomplete snapshots are not charted as overall portfolio market value.
        </div>
      ) : null}

      {loading ? (
        <div className="text-sm text-zinc-500">Loading portfolio snapshots...</div>
      ) : error ? (
        <div className="text-sm text-red-500">{error}</div>
      ) : chartData.length === 0 ? (
        <div className="text-sm text-zinc-500">No portfolio snapshots yet. Use Record Snapshot after EOD prices are available.</div>
      ) : (
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="4 4" className="stroke-zinc-200 dark:stroke-zinc-800" />
              <XAxis
                dataKey="ts"
                type="number"
                scale="time"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(value) => new Date(value as number).toLocaleDateString()}
                minTickGap={16}
              />
              <YAxis tickFormatter={(value) => fmtCurrency(Number(value))} width={88} />
              <Tooltip
                labelFormatter={(value) => new Date(value as number).toLocaleDateString()}
                formatter={(value: number, name: string, item) => {
                  const payload = item.payload as { isInferred?: boolean };
                  const label =
                    name === "marketValue"
                      ? payload?.isInferred
                        ? "Inferred Baseline"
                        : "Market Value"
                      : "Cost Basis";
                  return [fmtCurrency(value), label];
                }}
              />
              <Line
                type="monotone"
                dataKey="marketValue"
                stroke="#0284c7"
                strokeWidth={2}
                dot={({ cx, cy, payload }) =>
                  payload?.isInferred ? <circle cx={cx} cy={cy} r={4} fill="#0284c7" stroke="#fff" strokeWidth={1.5} /> : <circle cx={cx} cy={cy} r={0} />
                }
                activeDot={{ r: 5 }}
              />
              <Line type="monotone" dataKey="costBasis" stroke="#71717a" strokeWidth={1.5} strokeDasharray="5 5" dot={false} />
              {chartData
                .filter((point) => point.isInferred)
                .map((point) => (
                  <ReferenceDot
                    key={`baseline-${point.ts}`}
                    x={point.ts}
                    y={point.marketValue}
                    r={5}
                    fill="#0284c7"
                    stroke="#ffffff"
                    label={{ value: "Baseline", position: "top", fill: "#0284c7", fontSize: 11 }}
                  />
                ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

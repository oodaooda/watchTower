import { useMemo, useState } from "react";
import {
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PortfolioSnapshotHistory } from "../lib/api";

const DEFAULT_VISIBLE_START = new Date("2026-01-01T00:00:00").getTime();

type ChartRangeKey = "1w" | "1m" | "3m" | "ytd" | "1y" | "max";
type ViewMode = "chart" | "table";
type SortDirection = "asc" | "desc";
type SnapshotTableSortKey = "date" | "marketValue" | "costBasis" | "dayChange" | "dayChangePct";
type TableAggregation = "daily" | "weekly" | "monthly";

const RANGE_OPTIONS: Array<{ key: ChartRangeKey; label: string }> = [
  { key: "1w", label: "1W" },
  { key: "1m", label: "1M" },
  { key: "3m", label: "3M" },
  { key: "ytd", label: "YTD" },
  { key: "1y", label: "1Y" },
  { key: "max", label: "MAX" },
];

type Props = {
  history: PortfolioSnapshotHistory | null;
  loading: boolean;
  error: string | null;
  saving: boolean;
  onRunSnapshot: () => void;
  summaryCards?: Array<{ label: string; value: string }>;
};

type ChartPoint = {
  ts: number;
  snapshotDate: string;
  marketValue: number;
  costBasis: number;
  dayChange: number | null;
  dayChangePct: number | null;
  complete: boolean;
  isInferred: boolean;
  source: string;
};

type SnapshotTablePoint = ChartPoint & {
  periodKey: string;
  periodLabel: string;
};

function fmtCurrency(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
}

function fmtPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 2, signDisplay: "auto" }).format(value);
}

function fmtCompactCurrency(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function fmtDate(value?: number | string | null) {
  if (value === null || value === undefined) return "-";
  const date = typeof value === "number" ? new Date(value) : new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function fmtMonth(value: number) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function getLocalDate(value: string) {
  return new Date(`${value}T00:00:00`);
}

function getWeekStart(date: Date) {
  const start = new Date(date);
  const day = start.getDay();
  const daysSinceMonday = (day + 6) % 7;
  start.setDate(start.getDate() - daysSinceMonday);
  return start;
}

function toIsoDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function tableAggregationForRange(range: ChartRangeKey): TableAggregation {
  if (range === "1w") return "weekly";
  if (range === "1m" || range === "3m" || range === "1y") return "monthly";
  return "daily";
}

function periodDetails(point: ChartPoint, aggregation: TableAggregation) {
  const date = getLocalDate(point.snapshotDate);
  if (aggregation === "weekly") {
    const weekStart = getWeekStart(date);
    return {
      key: `week-${toIsoDate(weekStart)}`,
      label: `Week of ${fmtDate(toIsoDate(weekStart))}`,
    };
  }
  if (aggregation === "monthly") {
    return {
      key: `month-${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`,
      label: fmtMonth(date.getTime()),
    };
  }
  return {
    key: point.snapshotDate,
    label: fmtDate(point.snapshotDate),
  };
}

function changeLabelsForAggregation(aggregation: TableAggregation) {
  if (aggregation === "weekly") {
    return { change: "Week Change", changePct: "Week Change %" };
  }
  if (aggregation === "monthly") {
    return { change: "Month Change", changePct: "Month Change %" };
  }
  return { change: "Day Change", changePct: "Day Change %" };
}

function PortfolioValueTooltip({ active, payload }: { active?: boolean; payload?: Array<{ dataKey?: string; value?: number; payload?: ChartPoint }> }) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;

  const rows = payload
    .filter((item) => item.dataKey === "marketValue" || item.dataKey === "costBasis")
    .map((item) => {
      const isMarketValue = item.dataKey === "marketValue";
      return {
        label: isMarketValue ? (point.isInferred ? "Inferred Baseline" : "Market Value") : "Cost Basis",
        value: fmtCurrency(item.value),
        color: isMarketValue ? "bg-sky-400" : "bg-zinc-400",
      };
    });

  return (
    <div className="min-w-[220px] rounded-xl border border-zinc-200/70 bg-white/90 px-3 py-2.5 text-sm shadow-xl shadow-zinc-950/10 backdrop-blur-md dark:border-zinc-700/70 dark:bg-zinc-950/85 dark:shadow-black/40">
      <div className="mb-2 border-b border-zinc-200/70 pb-2 dark:border-zinc-800">
        <div className="text-[11px] font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Snapshot Date</div>
        <div className="text-sm font-semibold text-zinc-950 dark:text-zinc-50">{fmtDate(point.snapshotDate)}</div>
      </div>
      <div className="space-y-1.5">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-5">
            <div className="flex items-center gap-2 text-zinc-600 dark:text-zinc-300">
              <span className={`h-2 w-2 rounded-full ${row.color}`} />
              <span>{row.label}</span>
            </div>
            <div className="font-semibold tabular-nums text-zinc-950 dark:text-zinc-50">{row.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function sortIndicator(active: boolean, direction: SortDirection) {
  if (!active) return "↕";
  return direction === "asc" ? "▲" : "▼";
}

export default function PortfolioMarketValueChart({ history, loading, error, saving, onRunSnapshot, summaryCards: portfolioSummaryCards = [] }: Props) {
  const snapshots = history?.snapshots ?? [];
  const [selectedRange, setSelectedRange] = useState<ChartRangeKey>("ytd");
  const [viewMode, setViewMode] = useState<ViewMode>("chart");
  const [tableSortKey, setTableSortKey] = useState<SnapshotTableSortKey>("date");
  const [tableSortDirection, setTableSortDirection] = useState<SortDirection>("desc");
  const tableAggregation = tableAggregationForRange(selectedRange);
  const tableChangeLabels = changeLabelsForAggregation(tableAggregation);
  const visibleSnapshots = useMemo(
    () =>
      snapshots.filter((snapshot) => {
        if (snapshot.total_market_value === null || snapshot.total_market_value === undefined) return false;
        return new Date(`${snapshot.snapshot_date}T00:00:00`).getTime() >= DEFAULT_VISIBLE_START;
      }),
    [snapshots],
  );
  const rangeStart = useMemo(() => {
    if (!visibleSnapshots.length) return DEFAULT_VISIBLE_START;
    const latestTs = new Date(`${visibleSnapshots[visibleSnapshots.length - 1].snapshot_date}T00:00:00`).getTime();
    const latestDate = new Date(latestTs);
    switch (selectedRange) {
      case "1w":
        return Math.max(DEFAULT_VISIBLE_START, latestTs - 7 * 24 * 60 * 60 * 1000);
      case "1m": {
        const start = new Date(latestDate);
        start.setMonth(start.getMonth() - 1);
        return Math.max(DEFAULT_VISIBLE_START, start.getTime());
      }
      case "3m": {
        const start = new Date(latestDate);
        start.setMonth(start.getMonth() - 3);
        return Math.max(DEFAULT_VISIBLE_START, start.getTime());
      }
      case "ytd":
        return DEFAULT_VISIBLE_START;
      case "1y": {
        const start = new Date(latestDate);
        start.setFullYear(start.getFullYear() - 1);
        return Math.max(DEFAULT_VISIBLE_START, start.getTime());
      }
      case "max":
      default:
        return DEFAULT_VISIBLE_START;
    }
  }, [selectedRange, visibleSnapshots]);
  const allCompleteTableRows = useMemo(() => {
    const rows = visibleSnapshots
      .filter((snapshot) => !snapshot.is_inferred)
      .map((snapshot, index, bucket) => {
        const previous = index > 0 ? bucket[index - 1] : undefined;
        const marketValue = Number(snapshot.total_market_value);
        const previousMarketValue = previous?.total_market_value != null ? Number(previous.total_market_value) : null;
        const dayChange = previousMarketValue === null ? null : marketValue - previousMarketValue;
        const dayChangePct = previousMarketValue === null || previousMarketValue === 0 ? null : (dayChange ?? 0) / previousMarketValue;
        return {
          ts: new Date(`${snapshot.snapshot_date}T00:00:00`).getTime(),
          snapshotDate: snapshot.snapshot_date,
          marketValue,
          costBasis: Number(snapshot.total_cost_basis),
          dayChange,
          dayChangePct,
          complete: snapshot.is_complete,
          isInferred: snapshot.is_inferred,
          source: snapshot.source,
        };
      });
    return rows;
  }, [visibleSnapshots]);
  const allTableRows = useMemo(() => {
    if (tableAggregation === "daily") {
      return allCompleteTableRows.map((point) => ({
        ...point,
        periodKey: point.snapshotDate,
        periodLabel: fmtDate(point.snapshotDate),
      }));
    }

    const latestPointByPeriod = new Map<string, SnapshotTablePoint>();
    allCompleteTableRows.forEach((point) => {
      const period = periodDetails(point, tableAggregation);
      const existing = latestPointByPeriod.get(period.key);
      if (!existing || point.ts > existing.ts) {
        latestPointByPeriod.set(period.key, {
          ...point,
          periodKey: period.key,
          periodLabel: period.label,
        });
      }
    });

    const periodRows = [...latestPointByPeriod.values()].sort((a, b) => a.ts - b.ts);
    return periodRows.map((point, index) => {
      const previous = index > 0 ? periodRows[index - 1] : undefined;
      const dayChange = previous ? point.marketValue - previous.marketValue : null;
      const dayChangePct = previous && previous.marketValue !== 0 ? (point.marketValue - previous.marketValue) / previous.marketValue : null;
      return {
        ...point,
        dayChange,
        dayChangePct,
      };
    });
  }, [allCompleteTableRows, tableAggregation]);
  const chartData = useMemo(
    () => allCompleteTableRows.filter((snapshot) => snapshot.ts >= rangeStart),
    [allCompleteTableRows, rangeStart],
  );
  const tableData = useMemo(
    () => allTableRows.filter((snapshot) => snapshot.ts >= rangeStart),
    [allTableRows, rangeStart],
  );
  const sortedTableData = useMemo(() => {
    const direction = tableSortDirection === "asc" ? 1 : -1;
    return [...tableData].sort((a, b) => {
      const aValue = tableSortKey === "date" ? a.ts : a[tableSortKey];
      const bValue = tableSortKey === "date" ? b.ts : b[tableSortKey];
      if (aValue === null || aValue === undefined) return 1;
      if (bValue === null || bValue === undefined) return -1;
      if (aValue < bValue) return -1 * direction;
      if (aValue > bValue) return 1 * direction;
      return b.ts - a.ts;
    });
  }, [tableData, tableSortDirection, tableSortKey]);

  const latestSnapshot = snapshots.length ? snapshots[snapshots.length - 1] : undefined;
  const incompleteCount = snapshots.filter((snapshot) => !snapshot.is_complete).length;
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

  const visibleRangeLabel = useMemo(() => {
    switch (selectedRange) {
      case "1w":
        return "Last 1 week";
      case "1m":
        return "Last 1 month";
      case "3m":
        return "Last 3 months";
      case "ytd":
        return "YTD";
      case "1y":
        return "Last 1 year";
      case "max":
        return "Max available";
      default:
        return "YTD";
    }
  }, [selectedRange]);
  const showPinnedPointLabels = selectedRange === "1w";
  const yDomain = useMemo(() => {
    if (!chartData.length) return ["auto", "auto"];
    const values = chartData.flatMap((point) => [point.marketValue, point.costBasis]);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max((max - min) * 0.12, 1000);
    return [Math.max(0, Math.floor(min - padding)), Math.ceil(max + padding)];
  }, [chartData]);
  const handleTableSort = (key: SnapshotTableSortKey) => {
    if (tableSortKey === key) {
      setTableSortDirection((direction) => (direction === "asc" ? "desc" : "asc"));
      return;
    }
    setTableSortKey(key);
    setTableSortDirection(key === "date" ? "desc" : "asc");
  };
  const tableHeader = (key: SnapshotTableSortKey, label: string, align: "left" | "right" = "right") => (
    <th className={`px-3 py-3 ${align === "right" ? "text-right" : "text-left"}`}>
      <button
        type="button"
        onClick={() => handleTableSort(key)}
        className={`inline-flex items-center gap-1 hover:underline ${align === "right" ? "justify-end" : ""}`}
      >
        <span>{label}</span>
        <span className={tableSortKey === key ? "opacity-100" : "opacity-50"}>
          {sortIndicator(tableSortKey === key, tableSortDirection)}
        </span>
      </button>
    </th>
  );

  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Portfolio Market Value History</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Showing snapshots from January 1, 2026 forward. Uses stored EOD closes and shows market value change, not cash-flow adjusted performance.
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

      {portfolioSummaryCards.length ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {portfolioSummaryCards.map((item) => (
            <div key={item.label} className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-3">
              <div className="text-xs uppercase tracking-wide text-zinc-500">{item.label}</div>
              <div className="mt-1 text-xl font-semibold">{item.value}</div>
            </div>
          ))}
        </div>
      ) : null}

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

      <div className="flex flex-wrap items-center gap-2">
        <div className="mr-2 inline-flex rounded-xl border border-zinc-300 dark:border-zinc-700 p-0.5">
          {(["chart", "table"] as ViewMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setViewMode(mode)}
              className={`h-7 rounded-lg px-3 text-xs font-medium capitalize transition-colors ${
                viewMode === mode
                  ? "bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900"
                  : "text-zinc-600 hover:bg-zinc-100/60 dark:text-zinc-300 dark:hover:bg-zinc-800/60"
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
        {RANGE_OPTIONS.map((option) => {
          const selected = option.key === selectedRange;
          return (
            <button
              key={option.key}
              type="button"
              onClick={() => setSelectedRange(option.key)}
              className={`h-8 rounded-xl border px-3 text-xs font-medium transition-colors ${
                selected
                  ? "border-sky-500/60 bg-sky-500/10 text-sky-600 dark:text-sky-300"
                  : "border-zinc-300 dark:border-zinc-700 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100/60 dark:hover:bg-zinc-800/60"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {latestSnapshot ? (
        <div className="flex flex-wrap gap-3 text-xs text-zinc-500 dark:text-zinc-400">
          <span>Latest snapshot: {latestSnapshot.snapshot_date}</span>
          <span>Priced positions: {latestSnapshot.priced_positions}</span>
          <span>Unpriced positions: {latestSnapshot.unpriced_positions}</span>
          <span>Visible range: {visibleRangeLabel}</span>
          {viewMode === "table" ? <span>Table rows: {tableAggregation}</span> : null}
        </div>
      ) : null}

      {incompleteCount ? (
        <div className="rounded-xl border border-amber-300/40 bg-amber-50/60 px-3 py-2 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-200">
          {incompleteCount} snapshot{incompleteCount === 1 ? " is" : "s are"} incomplete because at least one position did not have an EOD close for that date. Incomplete snapshots are not charted as overall portfolio market value.
        </div>
      ) : null}

      {loading ? (
        <div className="text-sm text-zinc-500">Loading portfolio snapshots...</div>
      ) : error ? (
        <div className="text-sm text-red-500">{error}</div>
      ) : chartData.length === 0 ? (
        <div className="text-sm text-zinc-500">No portfolio snapshots yet. Use Record Snapshot after EOD prices are available.</div>
      ) : viewMode === "table" ? (
        <div className="overflow-auto rounded-2xl border border-zinc-200 dark:border-zinc-800">
          <table className="min-w-full text-sm">
            <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900/60">
              <tr>
                {tableHeader("date", "Date", "left")}
                {tableHeader("marketValue", "Market Value")}
                {tableHeader("costBasis", "Cost Basis")}
                {tableHeader("dayChange", tableChangeLabels.change)}
                {tableHeader("dayChangePct", tableChangeLabels.changePct)}
              </tr>
            </thead>
            <tbody>
              {sortedTableData.map((point) => (
                <tr key={point.periodKey} className="border-t border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50/70 dark:hover:bg-zinc-900/40">
                  <td className="px-3 py-3 font-medium">{point.periodLabel}</td>
                  <td className="px-3 py-3 text-right">{fmtCurrency(point.marketValue)}</td>
                  <td className="px-3 py-3 text-right">{fmtCurrency(point.costBasis)}</td>
                  <td className={`px-3 py-3 text-right ${point.dayChange && point.dayChange > 0 ? "text-emerald-500" : point.dayChange && point.dayChange < 0 ? "text-red-500" : ""}`}>
                    {fmtCurrency(point.dayChange)}
                  </td>
                  <td className={`px-3 py-3 text-right ${point.dayChangePct && point.dayChangePct > 0 ? "text-emerald-500" : point.dayChangePct && point.dayChangePct < 0 ? "text-red-500" : ""}`}>
                    {fmtPercent(point.dayChangePct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
              <YAxis domain={yDomain} tickFormatter={(value) => fmtCompactCurrency(Number(value))} width={96} />
              <Tooltip content={<PortfolioValueTooltip />} cursor={{ stroke: "rgba(148, 163, 184, 0.65)", strokeWidth: 1 }} />
              <Line
                type="linear"
                dataKey="marketValue"
                stroke="#0284c7"
                strokeWidth={2}
                dot={showPinnedPointLabels ? { r: 3, strokeWidth: 1, fill: "#0284c7" } : false}
                activeDot={{ r: 5 }}
              >
                {showPinnedPointLabels ? (
                  <LabelList
                    dataKey="marketValue"
                    position="top"
                    offset={10}
                    formatter={(value: number) => fmtCompactCurrency(value)}
                    className="fill-zinc-500 text-[10px]"
                  />
                ) : null}
              </Line>
              <Line type="linear" dataKey="costBasis" stroke="#71717a" strokeWidth={1.5} strokeDasharray="5 5" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

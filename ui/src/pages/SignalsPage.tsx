type SignalStatus = "green" | "amber" | "red" | "grey";

type SignalTile = {
  id: string;
  group: "Portfolio Goal" | "Macro" | "Equity" | "Semi Cycle" | "Geopolitical" | "System";
  title: string;
  value: string;
  unit: string;
  zScore: number | null;
  status: SignalStatus;
  source: string;
  age: string;
  cadence: string;
  delta: string;
  sparkline: number[];
};

const tiles: SignalTile[] = [
  {
    id: "P1",
    group: "Portfolio Goal",
    title: "$1M Goal Tracker",
    value: "734.3",
    unit: "$K",
    zScore: null,
    status: "green",
    source: "Portfolio snapshots",
    age: "1d",
    cadence: "Daily",
    delta: "$265.7K left",
    sparkline: [548, 562, 589, 604, 617, 656, 695, 721, 734],
  },
  {
    id: "P2",
    group: "Portfolio Goal",
    title: "VGT Exposure",
    value: "594.0",
    unit: "$K",
    zScore: null,
    status: "amber",
    source: "Portfolio lots",
    age: "1d",
    cadence: "Daily",
    delta: "80.9% of portfolio",
    sparkline: [421, 438, 462, 485, 503, 541, 566, 587, 594],
  },
  {
    id: "P3",
    group: "Portfolio Goal",
    title: "90D Velocity",
    value: "+144.4",
    unit: "$K",
    zScore: 1.7,
    status: "amber",
    source: "Portfolio snapshots",
    age: "1d",
    cadence: "Daily",
    delta: "+25.4%",
    sparkline: [11, 28, 42, 55, 74, 91, 106, 128, 144],
  },
  {
    id: "M1",
    group: "Macro",
    title: "HY OAS",
    value: "312",
    unit: "bps",
    zScore: -0.4,
    status: "green",
    source: "FRED",
    age: "41m",
    cadence: "Daily",
    delta: "-7 bps",
    sparkline: [358, 349, 341, 338, 332, 329, 323, 319, 312],
  },
  {
    id: "M2",
    group: "Macro",
    title: "10Y Real Yield",
    value: "2.14",
    unit: "%",
    zScore: 1.1,
    status: "amber",
    source: "FRED",
    age: "43m",
    cadence: "Daily",
    delta: "+8 bp",
    sparkline: [1.84, 1.89, 1.93, 1.98, 2.03, 2.01, 2.08, 2.11, 2.14],
  },
  {
    id: "M3",
    group: "Macro",
    title: "VIX",
    value: "15.8",
    unit: "idx",
    zScore: -0.7,
    status: "green",
    source: "FRED",
    age: "42m",
    cadence: "Daily",
    delta: "-0.6",
    sparkline: [18.9, 18.2, 17.4, 17.8, 16.9, 16.4, 16.1, 15.9, 15.8],
  },
  {
    id: "M4",
    group: "Macro",
    title: "Dollar Broad Index",
    value: "123.4",
    unit: "idx",
    zScore: 0.3,
    status: "green",
    source: "FRED",
    age: "44m",
    cadence: "Daily",
    delta: "+0.2",
    sparkline: [121.9, 122.1, 122.4, 122.0, 122.6, 123.0, 122.8, 123.2, 123.4],
  },
  {
    id: "E1",
    group: "Equity",
    title: "News Sentiment Top 5",
    value: "+0.18",
    unit: "score",
    zScore: 1.8,
    status: "amber",
    source: "Alpha Vantage",
    age: "6m",
    cadence: "15m RTH",
    delta: "+0.07",
    sparkline: [-0.04, -0.01, 0.03, 0.05, 0.04, 0.09, 0.13, 0.16, 0.18],
  },
  {
    id: "E2",
    group: "Equity",
    title: "NVDA EPS Estimate Delta",
    value: "+2.6",
    unit: "%",
    zScore: 0.9,
    status: "green",
    source: "Alpha Vantage",
    age: "1h",
    cadence: "Daily",
    delta: "+0.4%",
    sparkline: [0.2, 0.5, 0.8, 1.3, 1.1, 1.8, 2.1, 2.4, 2.6],
  },
  {
    id: "E3",
    group: "Equity",
    title: "Insider Net Flow Top 5",
    value: "-18.4",
    unit: "$M",
    zScore: -1.5,
    status: "amber",
    source: "Alpha Vantage",
    age: "7h",
    cadence: "Daily",
    delta: "-$6.1M",
    sparkline: [4.1, 2.8, 1.2, -3.5, -6.0, -9.4, -13.2, -15.9, -18.4],
  },
  {
    id: "E4",
    group: "Equity",
    title: "Put/Call Skew VGT",
    value: "TBD",
    unit: "",
    zScore: null,
    status: "grey",
    source: "Unresolved",
    age: "--",
    cadence: "Skipped v1",
    delta: "needs source",
    sparkline: [0, 0, 0, 0, 0, 0, 0, 0, 0],
  },
  {
    id: "S1",
    group: "Semi Cycle",
    title: "TSMC Revenue YoY",
    value: "+31.6",
    unit: "%",
    zScore: 1.6,
    status: "amber",
    source: "TSMC IR",
    age: "1d",
    cadence: "Daily check",
    delta: "+2.3%",
    sparkline: [20.4, 24.5, 16.9, 31.4, 33.8, 25.8, 26.9, 39.6, 31.6],
  },
  {
    id: "S2",
    group: "Semi Cycle",
    title: "Hyperscaler Capex Delta",
    value: "+17.2",
    unit: "%",
    zScore: 2.2,
    status: "red",
    source: "SEC EDGAR",
    age: "3d",
    cadence: "Weekly",
    delta: "+4.8%",
    sparkline: [4.2, 6.4, 8.1, 9.7, 11.0, 12.8, 14.9, 16.1, 17.2],
  },
  {
    id: "G1",
    group: "Geopolitical",
    title: "Taiwan <2027 Market",
    value: "12.8",
    unit: "%",
    zScore: 2.7,
    status: "red",
    source: "Polymarket",
    age: "18s",
    cadence: "5m",
    delta: "+3.1%",
    sparkline: [4.1, 4.3, 4.7, 5.2, 6.4, 7.9, 9.8, 11.1, 12.8],
  },
  {
    id: "G2",
    group: "Geopolitical",
    title: "BIS Export Rules 90d",
    value: "7",
    unit: "rules",
    zScore: 1.9,
    status: "amber",
    source: "Federal Register",
    age: "9h",
    cadence: "Daily",
    delta: "+2",
    sparkline: [2, 2, 3, 3, 4, 5, 5, 6, 7],
  },
  {
    id: "I1",
    group: "System",
    title: "Ingest Health",
    value: "11/12",
    unit: "live",
    zScore: null,
    status: "amber",
    source: "Internal",
    age: "12s",
    cadence: "60s",
    delta: "E4 disabled",
    sparkline: [12, 12, 12, 12, 11, 11, 11, 11, 11],
  },
];

const alerts = [
  { time: "14:22:18", severity: "crit", text: "Taiwan probability crossed 10% hard-watch threshold" },
  { time: "13:05:44", severity: "warn", text: "Hyperscaler capex delta above +2 sigma" },
  { time: "09:31:09", severity: "info", text: "FRED macro bundle completed with 4 observations" },
  { time: "08:12:55", severity: "warn", text: "Insider net flow negative for top holdings basket" },
];

const statusStyles: Record<SignalStatus, { dot: string; text: string; border: string; fill: string }> = {
  green: {
    dot: "bg-emerald-400 shadow-emerald-400/50",
    text: "text-emerald-300",
    border: "border-emerald-400/25",
    fill: "#34d399",
  },
  amber: {
    dot: "bg-amber-300 shadow-amber-300/50",
    text: "text-amber-200",
    border: "border-amber-300/25",
    fill: "#fbbf24",
  },
  red: {
    dot: "bg-red-400 shadow-red-400/50",
    text: "text-red-300",
    border: "border-red-400/30",
    fill: "#f87171",
  },
  grey: {
    dot: "bg-zinc-500 shadow-zinc-500/30",
    text: "text-zinc-400",
    border: "border-zinc-700",
    fill: "#71717a",
  },
};

function sparklinePath(values: number[]) {
  const width = 210;
  const height = 46;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function formatZScore(value: number | null) {
  if (value === null) return "Z: --";
  return `Z: ${value > 0 ? "+" : ""}${value.toFixed(1)} (1Y)`;
}

function SignalTileCard({ tile }: { tile: SignalTile }) {
  const styles = statusStyles[tile.status];
  return (
    <button
      type="button"
      className={`group flex min-h-[184px] w-full flex-col justify-between rounded-lg border bg-zinc-950/80 p-3 text-left shadow-sm shadow-black/30 ${styles.border} hover:bg-zinc-900/90 focus:outline-none focus:ring-2 focus:ring-sky-500/40`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-zinc-500">{tile.group}</div>
          <div className="mt-1 text-sm font-semibold uppercase tracking-wide text-zinc-100">{tile.title}</div>
        </div>
        <span className="relative mt-1 flex h-3 w-3">
          <span className={`absolute inline-flex h-full w-full rounded-full opacity-40 ${tile.status !== "grey" ? "animate-ping" : ""} ${styles.dot}`} />
          <span className={`relative inline-flex h-3 w-3 rounded-full shadow-lg ${styles.dot}`} />
        </span>
      </div>

      <div className="mt-4 flex items-end justify-between gap-3">
        <div>
          <div className={`font-mono text-3xl font-semibold leading-none tabular-nums ${styles.text}`}>
            {tile.value}
            {tile.unit ? <span className="ml-1 text-sm text-zinc-500">{tile.unit}</span> : null}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-xs">
            <span className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-zinc-300">{formatZScore(tile.zScore)}</span>
            <span className={styles.text}>{tile.delta}</span>
          </div>
        </div>
        <div className="text-right font-mono text-[11px] uppercase text-zinc-500">
          <div>{tile.id}</div>
          <div>{tile.cadence}</div>
        </div>
      </div>

      <svg className="mt-4 h-[50px] w-full overflow-visible" viewBox="0 0 210 50" preserveAspectRatio="none" aria-hidden="true">
        <path d="M0 46H210" stroke="rgba(63,63,70,0.75)" strokeWidth="1" />
        <path d="M0 23H210" stroke="rgba(63,63,70,0.35)" strokeWidth="1" strokeDasharray="4 6" />
        <path d={sparklinePath(tile.sparkline)} fill="none" stroke={styles.fill} strokeWidth="2.2" vectorEffect="non-scaling-stroke" />
      </svg>

      <div className="mt-3 flex items-center justify-between gap-3 border-t border-zinc-800 pt-2 font-mono text-[11px] text-zinc-500">
        <span className="truncate">{tile.source} | {tile.age} ago</span>
        <span className="text-sky-300 opacity-80 group-hover:opacity-100">expand -&gt;</span>
      </div>
    </button>
  );
}

export default function SignalsPage() {
  const stressedCount = tiles.filter((tile) => tile.status === "red" || tile.status === "amber").length;
  return (
    <div className="min-h-[calc(100vh-96px)] rounded-xl border border-zinc-800 bg-[#05070a] p-3 text-zinc-100 shadow-2xl shadow-black/40 md:p-4">
      <div className="mb-3 grid gap-3 xl:grid-cols-[1fr_360px]">
        <section className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-mono text-xs uppercase tracking-[0.22em] text-zinc-500">WatchTower / Signals</div>
              <h1 className="mt-1 text-xl font-semibold tracking-tight text-zinc-50">VGT Goal And OSINT Monitor</h1>
            </div>
            <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
              <span className="rounded border border-red-400/30 bg-red-500/10 px-2.5 py-1.5 text-red-200">STRESSED</span>
              <span className="rounded border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-zinc-300">{stressedCount} thresholds active</span>
              <span className="rounded border border-emerald-400/25 bg-emerald-500/10 px-2.5 py-1.5 text-emerald-200">SSE live</span>
              <span className="rounded border border-sky-400/25 bg-sky-500/10 px-2.5 py-1.5 text-sky-200">assistant read-only</span>
            </div>
          </div>
          <div className="mt-3 grid gap-2 font-mono text-xs text-zinc-400 md:grid-cols-5">
            <div className="rounded border border-zinc-800 bg-black/25 p-2">
              <div className="text-zinc-600">Regime rules</div>
              <div className="mt-1 text-red-200">G1 hard-watch, S2 &gt;2 sigma</div>
            </div>
            <div className="rounded border border-zinc-800 bg-black/25 p-2">
              <div className="text-zinc-600">Stream</div>
              <div className="mt-1 text-zinc-200">Last event #12346</div>
            </div>
            <div className="rounded border border-zinc-800 bg-black/25 p-2">
              <div className="text-zinc-600">Coverage</div>
              <div className="mt-1 text-zinc-200">15 tiles | 7 sources</div>
            </div>
            <div className="rounded border border-zinc-800 bg-black/25 p-2">
              <div className="text-zinc-600">Goal tracker</div>
              <div className="mt-1 text-emerald-200">$734.3K / $1.0M</div>
            </div>
            <div className="rounded border border-zinc-800 bg-black/25 p-2">
              <div className="text-zinc-600">Assistant context</div>
              <div className="mt-1 text-sky-200">read-only, cited</div>
            </div>
          </div>
        </section>

        <aside className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3">
          <div className="flex items-center justify-between">
            <h2 className="font-mono text-xs uppercase tracking-[0.18em] text-zinc-400">Alert Rail</h2>
            <span className="font-mono text-[11px] text-zinc-600">last 50</span>
          </div>
          <div className="mt-3 space-y-2">
            {alerts.map((alert) => (
              <div key={`${alert.time}-${alert.text}`} className="rounded border border-zinc-800 bg-black/25 p-2">
                <div className="flex items-center justify-between gap-2 font-mono text-[11px] uppercase text-zinc-500">
                  <span>{alert.time}</span>
                  <span className={alert.severity === "crit" ? "text-red-300" : alert.severity === "warn" ? "text-amber-200" : "text-sky-300"}>
                    {alert.severity}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-5 text-zinc-300">{alert.text}</p>
              </div>
            ))}
          </div>
        </aside>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {tiles.map((tile) => (
          <SignalTileCard key={tile.id} tile={tile} />
        ))}
      </section>
    </div>
  );
}

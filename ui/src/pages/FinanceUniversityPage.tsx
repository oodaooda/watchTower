import { useMemo, useState } from "react";
import BackButton from "../components/BackButton";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const chapters = [
  { id: "foundations", title: "Foundation: Financial Statements" },
  { id: "income", title: "Income Statement Mechanics" },
  { id: "drivers", title: "Unit Economics & Drivers" },
  { id: "margins", title: "Margins & Operating Leverage" },
  { id: "dilution", title: "Capital Structure & Dilution" },
  { id: "forecasting", title: "Forecasting & Scenarios" },
  { id: "valuation", title: "Valuation Basics" },
  { id: "risk", title: "Risk & Sensitivity" },
];

const card =
  "rounded-2xl border border-zinc-200/40 dark:border-zinc-800/80 bg-white/80 dark:bg-zinc-950/90 shadow-[0_12px_40px_rgba(0,0,0,0.18)]";
const panel =
  "rounded-2xl border border-zinc-200/40 dark:border-zinc-800/80 bg-zinc-900/40 dark:bg-zinc-950/40 backdrop-blur";

function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
  suffix,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (next: number) => void;
  suffix?: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-zinc-500">
      <span className="flex items-center justify-between">
        {label}
        <span className="text-zinc-300">{value.toFixed(1)}{suffix}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

function SectionMeta({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        <p className="text-sm text-zinc-400">{description}</p>
      </div>
      <span className="text-xs uppercase tracking-wide text-zinc-500">Interactive</span>
    </div>
  );
}

function KeyTakeaways({ items }: { items: string[] }) {
  return (
    <div className={`${panel} p-4`}>
      <div className="text-xs uppercase tracking-wide text-zinc-500">Key Takeaways</div>
      <ul className="mt-2 space-y-1 text-sm text-zinc-300">
        {items.map((item) => (
          <li key={item}>• {item}</li>
        ))}
      </ul>
    </div>
  );
}

export default function FinanceUniversityPage() {
  const [active, setActive] = useState("foundations");
  const [revenue, setRevenue] = useState(1000);
  const [cogsPct, setCogsPct] = useState(40);
  const [opexPct, setOpexPct] = useState(35);
  const [taxPct, setTaxPct] = useState(18);

  const [dau, setDau] = useState(50);
  const [paidPct, setPaidPct] = useState(8);
  const [arpu, setArpu] = useState(12);
  const [growthRate, setGrowthRate] = useState(12);
  const [opexLeverage, setOpexLeverage] = useState(65);
  const [dilutionPct, setDilutionPct] = useState(2);
  const [discountRate, setDiscountRate] = useState(10);
  const [terminalGrowth, setTerminalGrowth] = useState(3);
  const [sensitivity, setSensitivity] = useState(15);

  const incomeData = useMemo(() => {
    const cogs = revenue * (cogsPct / 100);
    const gross = revenue - cogs;
    const opex = revenue * (opexPct / 100);
    const opIncome = gross - opex;
    const tax = Math.max(opIncome, 0) * (taxPct / 100);
    const net = opIncome - tax;
    return [
      { label: "Revenue", value: revenue },
      { label: "Gross Profit", value: gross },
      { label: "Operating Income", value: opIncome },
      { label: "Net Income", value: net },
    ];
  }, [revenue, cogsPct, opexPct, taxPct]);

  const driverData = useMemo(() => {
    const base = dau * (paidPct / 100) * arpu;
    const points = Array.from({ length: 8 }, (_, i) => {
      const factor = 1 + i * 0.04;
      return {
        quarter: `Q${(i % 4) + 1}`,
        revenue: base * factor,
      };
    });
    return points;
  }, [dau, paidPct, arpu]);

  const marginData = useMemo(() => {
    const points = Array.from({ length: 8 }, (_, i) => {
      const scale = 1 + i * (growthRate / 100);
      const margin = Math.max(5, 35 + i * (1 - opexLeverage / 100));
      return {
        year: `Y${i + 1}`,
        revenue: revenue * scale,
        margin,
      };
    });
    return points;
  }, [growthRate, opexLeverage, revenue]);

  const dilutionData = useMemo(() => {
    const netIncome = 120;
    const shares = 100;
    return Array.from({ length: 8 }, (_, i) => {
      const shareCount = shares * (1 + dilutionPct / 100) ** i;
      return {
        year: `Y${i + 1}`,
        eps: netIncome / shareCount,
      };
    });
  }, [dilutionPct]);

  const valuationData = useMemo(() => {
    const cashFlows = Array.from({ length: 6 }, (_, i) => 80 * (1 + growthRate / 100) ** i);
    const pv = cashFlows.map((cf, i) => cf / (1 + discountRate / 100) ** (i + 1));
    const terminal = cashFlows[cashFlows.length - 1] * (1 + terminalGrowth / 100);
    const terminalPv = terminal / ((discountRate - terminalGrowth) / 100) / (1 + discountRate / 100) ** cashFlows.length;
    return pv.map((value, i) => ({ year: `Y${i + 1}`, pv: value })).concat({
      year: "TV",
      pv: terminalPv,
    });
  }, [discountRate, terminalGrowth, growthRate]);

  const sensitivityData = useMemo(() => {
    const base = 100;
    return [
      { factor: "Revenue growth", impact: base + sensitivity },
      { factor: "Gross margin", impact: base + sensitivity / 2 },
      { factor: "Discount rate", impact: base - sensitivity },
      { factor: "Terminal growth", impact: base + sensitivity / 3 },
    ];
  }, [sensitivity]);

  return (
    <div className="mt-6 space-y-4">
      <div className="flex items-center gap-3">
        <BackButton />
        <h1 className="text-2xl font-semibold">Finance University</h1>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-4">
      <div className={`${card} p-4 space-y-2`}>
        <div className="text-xs uppercase tracking-wide text-zinc-500">Finance University</div>
        <div className="text-lg font-semibold text-white">Chapters</div>
        <div className="space-y-1">
          {chapters.map((chapter) => (
            <button
              key={chapter.id}
              className={`w-full text-left rounded-xl px-3 py-2 text-sm border ${
                active === chapter.id
                  ? "border-sky-500/60 bg-sky-500/10 text-sky-200"
                  : "border-zinc-800 text-zinc-300 hover:bg-zinc-900/40"
              }`}
              onClick={() => setActive(chapter.id)}
            >
              {chapter.title}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <div className={`${card} p-6 bg-gradient-to-br from-zinc-900 via-zinc-950 to-zinc-900`}>
          <div className="text-xs uppercase tracking-wide text-zinc-500">Chapter</div>
          <h1 className="text-2xl font-semibold text-white">
            {chapters.find((c) => c.id === active)?.title}
          </h1>
          <p className="mt-2 text-sm text-zinc-400 max-w-3xl">
            Learn the mechanics behind the model and how each lever shapes the forecast.
            Chapters mix concise explanations with interactive exercises.
          </p>
          <div className="mt-4 flex flex-wrap gap-3 text-xs text-zinc-300">
            <span className="rounded-full border border-zinc-700 px-3 py-1">Professional finance tone</span>
            <span className="rounded-full border border-zinc-700 px-3 py-1">Interactive models</span>
            <span className="rounded-full border border-zinc-700 px-3 py-1">Tied to watchTower projections</span>
          </div>
        </div>

        {active === "foundations" && (
          <div className={`${card} p-5 space-y-4`}>
            <SectionMeta
              title="Statement Links"
              description="Income statement drives net income, which feeds cash flow and equity."
            />
            <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-4">
              <div className="space-y-3">
                <Slider label="Revenue" value={revenue} min={500} max={2000} step={25} onChange={setRevenue} />
                <Slider label="COGS % of revenue" value={cogsPct} min={10} max={80} step={1} onChange={setCogsPct} suffix="%" />
                <Slider label="OpEx % of revenue" value={opexPct} min={10} max={60} step={1} onChange={setOpexPct} suffix="%" />
                <Slider label="Tax rate" value={taxPct} min={5} max={35} step={1} onChange={setTaxPct} suffix="%" />
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={incomeData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="label" stroke="#a1a1aa" />
                    <YAxis stroke="#a1a1aa" />
                    <Tooltip cursor={{ fill: "rgba(148, 163, 184, 0.1)" }} />
                    <Bar dataKey="value" fill="#38bdf8" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <KeyTakeaways
              items={[
                "Revenue and COGS define gross profit.",
                "Operating income is gross profit minus OpEx.",
                "Net income feeds retained earnings and cash flow.",
              ]}
            />
          </div>
        )}

        {active === "income" && (
          <div className={`${card} p-5 space-y-4`}>
            <SectionMeta
              title="Income Statement Mechanics"
              description="Adjust margins and see how revenue flows into operating and net income."
            />
            <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-4">
              <div className="space-y-3">
                <Slider label="Revenue" value={revenue} min={500} max={2000} step={25} onChange={setRevenue} />
                <Slider label="COGS % of revenue" value={cogsPct} min={10} max={80} step={1} onChange={setCogsPct} suffix="%" />
                <Slider label="OpEx % of revenue" value={opexPct} min={10} max={60} step={1} onChange={setOpexPct} suffix="%" />
                <Slider label="Tax rate" value={taxPct} min={5} max={35} step={1} onChange={setTaxPct} suffix="%" />
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={incomeData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="label" stroke="#a1a1aa" />
                    <YAxis stroke="#a1a1aa" />
                    <Tooltip cursor={{ fill: "rgba(148, 163, 184, 0.1)" }} />
                    <Bar dataKey="value" fill="#38bdf8" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <KeyTakeaways
              items={[
                "Gross margin reflects pricing power and unit costs.",
                "OpEx intensity drives operating leverage.",
                "Tax rate affects net income, not operating income.",
              ]}
            />
          </div>
        )}

        {active === "drivers" && (
          <div className={`${card} p-5 space-y-4`}>
            <SectionMeta
              title="Driver-Based Revenue"
              description="Model revenue using DAU, paid conversion, and ARPU. This powers the driver blend in forecasts."
            />
            <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-4">
              <div className="space-y-3">
                <Slider label="DAU (millions)" value={dau} min={5} max={150} step={1} onChange={setDau} />
                <Slider label="Paid conversion %" value={paidPct} min={1} max={30} step={0.5} onChange={setPaidPct} suffix="%" />
                <Slider label="ARPU ($/quarter)" value={arpu} min={5} max={30} step={0.5} onChange={setArpu} />
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={driverData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="quarter" stroke="#a1a1aa" />
                    <YAxis stroke="#a1a1aa" />
                    <Tooltip cursor={{ stroke: "#38bdf8" }} />
                    <Line type="monotone" dataKey="revenue" stroke="#22c55e" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            <KeyTakeaways
              items={[
                "DAU drives the activity base.",
                "Paid conversion translates usage into revenue.",
                "ARPU controls monetization per user.",
              ]}
            />
          </div>
        )}

        {active === "margins" && (
          <div className={`${card} p-5 space-y-4`}>
            <SectionMeta
              title="Margins & Operating Leverage"
              description="Higher growth with disciplined costs expands operating margin over time."
            />
            <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-4">
              <div className="space-y-3">
                <Slider label="Revenue growth %" value={growthRate} min={2} max={30} step={1} onChange={setGrowthRate} suffix="%" />
                <Slider label="OpEx leverage" value={opexLeverage} min={40} max={90} step={1} onChange={setOpexLeverage} suffix="%" />
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={marginData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="year" stroke="#a1a1aa" />
                    <YAxis stroke="#a1a1aa" />
                    <Tooltip />
                    <Line type="monotone" dataKey="margin" stroke="#f97316" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="revenue" stroke="#38bdf8" strokeWidth={2} dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
            <KeyTakeaways
              items={[
                "Operating leverage improves as revenue scales faster than costs.",
                "Margin gains are more durable with stable gross margin.",
                "Monitor OpEx discipline as growth slows.",
              ]}
            />
          </div>
        )}

        {active === "dilution" && (
          <div className={`${card} p-5 space-y-4`}>
            <SectionMeta
              title="Capital Structure & Dilution"
              description="Share count growth dilutes EPS even if net income is stable."
            />
            <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-4">
              <div className="space-y-3">
                <Slider label="Annual dilution %" value={dilutionPct} min={0} max={6} step={0.2} onChange={setDilutionPct} suffix="%" />
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={dilutionData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="year" stroke="#a1a1aa" />
                    <YAxis stroke="#a1a1aa" />
                    <Tooltip />
                    <Line type="monotone" dataKey="eps" stroke="#a78bfa" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            <KeyTakeaways
              items={[
                "Dilution reduces EPS even if profit holds steady.",
                "Equity comp and capital raises are common drivers.",
                "Track buybacks vs issuance to assess net dilution.",
              ]}
            />
          </div>
        )}

        {active === "forecasting" && (
          <div className={`${card} p-5 space-y-4`}>
            <SectionMeta
              title="Forecasting & Scenarios"
              description="Use growth and margin levers to build base, bull, and bear trajectories."
            />
            <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-4">
              <div className="space-y-3">
                <Slider label="Revenue growth %" value={growthRate} min={2} max={30} step={1} onChange={setGrowthRate} suffix="%" />
                <Slider label="OpEx leverage" value={opexLeverage} min={40} max={90} step={1} onChange={setOpexLeverage} suffix="%" />
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={marginData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="year" stroke="#a1a1aa" />
                    <YAxis stroke="#a1a1aa" />
                    <Tooltip />
                    <Line type="monotone" dataKey="revenue" stroke="#38bdf8" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            <KeyTakeaways
              items={[
                "Base case reflects expected operating trajectory.",
                "Bull/Bear adjust growth and margins asymmetrically.",
                "Use scenario deltas to frame valuation ranges.",
              ]}
            />
          </div>
        )}

        {active === "valuation" && (
          <div className={`${card} p-5 space-y-4`}>
            <SectionMeta
              title="Valuation Basics"
              description="Discount rate and terminal growth dominate DCF value. Adjust and observe."
            />
            <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-4">
              <div className="space-y-3">
                <Slider label="Discount rate" value={discountRate} min={6} max={14} step={0.5} onChange={setDiscountRate} suffix="%" />
                <Slider label="Terminal growth" value={terminalGrowth} min={1} max={5} step={0.2} onChange={setTerminalGrowth} suffix="%" />
                <Slider label="Growth (years 1-5)" value={growthRate} min={2} max={30} step={1} onChange={setGrowthRate} suffix="%" />
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={valuationData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="year" stroke="#a1a1aa" />
                    <YAxis stroke="#a1a1aa" />
                    <Tooltip />
                    <Bar dataKey="pv" fill="#22c55e" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <KeyTakeaways
              items={[
                "Discount rate is the primary valuation sensitivity.",
                "Terminal value often dominates total DCF.",
                "Keep terminal growth conservative and defensible.",
              ]}
            />
          </div>
        )}

        {active === "risk" && (
          <div className={`${card} p-5 space-y-4`}>
            <SectionMeta
              title="Risk & Sensitivity"
              description="Identify which assumptions drive value the most."
            />
            <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-4">
              <div className="space-y-3">
                <Slider label="Sensitivity range" value={sensitivity} min={5} max={30} step={1} onChange={setSensitivity} suffix="%" />
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={sensitivityData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis type="number" stroke="#a1a1aa" />
                    <YAxis dataKey="factor" type="category" stroke="#a1a1aa" width={120} />
                    <Tooltip />
                    <Bar dataKey="impact" fill="#facc15" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <KeyTakeaways
              items={[
                "Rank assumptions by valuation impact.",
                "High sensitivity = high monitoring priority.",
                "Stress test to bracket downside scenarios.",
              ]}
            />
          </div>
        )}
      </div>
    </div>
    </div>
  );
}

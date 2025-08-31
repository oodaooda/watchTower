import { useState } from "react";

type Props = {
  onRun: (params: {
    pe_max?: number;
    cash_debt_min?: number;
    growth_consistency_min?: number;
    rev_cagr_min?: number;
    ni_cagr_min?: number;
    fcf_cagr_min?: number;   // NEW
    industry?: string;
  }) => void;
};

const btnPrimary =
  "h-9 px-4 rounded-md bg-black text-white font-medium " +
  "inline-flex items-center justify-center " +
  "hover:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

export default function FilterBar({ onRun }: Props) {
  // Local UI state; all optional filters
  const [peMax, setPeMax] = useState<number | undefined>(undefined);
  const [cashDebtMin, setCashDebtMin] = useState<number | undefined>(0.8);
  const [growthMin, setGrowthMin] = useState<number | undefined>(7);
  const [revCagr, setRevCagr] = useState<number | undefined>(undefined);
  const [niCagr, setNiCagr] = useState<number | undefined>(undefined);
  const [fcfCagr, setFcfCagr] = useState<number | undefined>(undefined); // NEW
  const [industry, setIndustry] = useState<string>("");

  return (
    <div className="rounded-2xl p-4 mb-4 border border-zinc-200 bg-white shadow-sm
                dark:border-white/10 dark:bg-white/5">

      <div className="grid grid-cols-2 md:grid-cols-7 gap-3">
        <div>
          <label className="text-xs mb-1 block">P/E ≤</label>
          <input
            type="number"
            placeholder="e.g. 20"
            value={peMax ?? ""}
            onChange={(e) => setPeMax(e.target.value ? Number(e.target.value) : undefined)}
            className={inputCls}
          />
        </div>

        <div>
          <label className="text-xs mb-1 block">Cash/Debt ≥</label>
          <input
            type="number"
            step="0.01"
            value={cashDebtMin ?? ""}
            onChange={(e) => setCashDebtMin(e.target.value ? Number(e.target.value) : undefined)}
            className={inputCls}
          />
        </div>

        <div>
          <label className="text-xs mb-1 block">Growth Consistency ≥</label>
          <input
            type="number"
            value={growthMin ?? ""}
            onChange={(e) => setGrowthMin(e.target.value ? Number(e.target.value) : undefined)}
            className={inputCls}
          />
        </div>

        <div>
          <label className="text-xs mb-1 block">Rev CAGR 5y ≥</label>
          <input
            type="number"
            step="0.01"
            placeholder="0.05 = 5%"
            value={revCagr ?? ""}
            onChange={(e) => setRevCagr(e.target.value ? Number(e.target.value) : undefined)}
            className={inputCls}
          />
        </div>

        <div>
          <label className="text-xs mb-1 block">NI CAGR 5y ≥</label>
          <input
            type="number"
            step="0.01"
            placeholder="0.05 = 5%"
            value={niCagr ?? ""}
            onChange={(e) => setNiCagr(e.target.value ? Number(e.target.value) : undefined)}
            className={inputCls}
          />
        </div>

        {/* NEW: FCF CAGR filter */}
        <div>
          <label className="text-xs mb-1 block">FCF CAGR 5y ≥</label>
          <input
            type="number"
            step="0.01"
            placeholder="0.05 = 5%"
            value={fcfCagr ?? ""}
            onChange={(e) => setFcfCagr(e.target.value ? Number(e.target.value) : undefined)}
            className={inputCls}
          />
        </div>

        <div>
          <label className="text-xs mb-1 block">Industry</label>
          <input
            type="text"
            placeholder="e.g. Semiconductors"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            className={inputCls}
          />
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          className={btnPrimary}
          onClick={() =>
            onRun({
              pe_max: peMax,
              cash_debt_min: cashDebtMin,
              growth_consistency_min: growthMin,
              rev_cagr_min: revCagr,
              ni_cagr_min: niCagr,
              industry: industry || undefined,
            })
          }
        >
          Run screen
        </button>

        <button
          type="button"
          className={btnPrimary}  // <-- same style for Reset
          onClick={() => {
            setPeMax(undefined);
            setCashDebtMin(0.8);
            setGrowthMin(7);
            setRevCagr(undefined);
            setNiCagr(undefined);
            setIndustry("");
          }}
        >
          Reset
        </button>
      </div>
    </div>
  );
}



const inputCls =
  "w-full h-9 rounded-md px-3 border bg-white text-zinc-900 placeholder-zinc-500 " +
  "focus:outline-none focus:ring-2 focus:ring-sky-500/30 " +
  "dark:bg-zinc-800 dark:text-white dark:placeholder-white/60 dark:border-white/10 " +
  "dark:focus:ring-sky-400/30";

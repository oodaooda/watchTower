import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ModelingAssumption,
  ModelingChatResponse,
  ModelingKPI,
  ModelingRunResponse,
  fetchModelingData,
  runModeling,
  saveModelingAssumptions,
  saveModelingKpis,
  chatModeling,
} from "../lib/api";
import Tooltip from "../components/Tooltip";

type ScenarioName = "base" | "bull" | "bear";

const btn =
  "h-9 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900 " +
  "hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

const btnGhost =
  "h-9 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-200 " +
  "hover:bg-zinc-100/60 dark:hover:bg-zinc-800/60 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

const card =
  "rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950";

function ArrowLeftIcon() {
  return (
    <svg
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M10 19l-7-7 7-7" />
      <path d="M3 12h18" />
    </svg>
  );
}

function PaperAirplaneIcon() {
  return (
    <svg
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M5 12l14-7-7 14-2-5-5-2z" />
    </svg>
  );
}

const pctFields = new Set([
  "revenue_cagr_start",
  "revenue_cagr_floor",
  "gross_margin_target",
  "rnd_pct",
  "sm_pct",
  "ga_pct",
  "tax_rate",
  "interest_pct_revenue",
  "dilution_pct_annual",
  "driver_blend_start_weight",
  "driver_blend_end_weight",
]);

const assumptionFields: Array<{ key: keyof ModelingAssumption; label: string }> = [
  { key: "revenue_cagr_start", label: "Revenue CAGR start" },
  { key: "revenue_cagr_floor", label: "Revenue CAGR floor" },
  { key: "revenue_decay_quarters", label: "Revenue decay (quarters)" },
  { key: "gross_margin_target", label: "Gross margin target" },
  { key: "gross_margin_glide_quarters", label: "Gross margin glide (quarters)" },
  { key: "rnd_pct", label: "R&D % of revenue" },
  { key: "sm_pct", label: "S&M % of revenue" },
  { key: "ga_pct", label: "G&A % of revenue" },
  { key: "tax_rate", label: "Tax rate" },
  { key: "interest_pct_revenue", label: "Interest % of revenue" },
  { key: "dilution_pct_annual", label: "Dilution % annual" },
  { key: "driver_blend_start_weight", label: "Driver blend start weight" },
  { key: "driver_blend_end_weight", label: "Driver blend end weight" },
  { key: "driver_blend_ramp_quarters", label: "Driver blend ramp (quarters)" },
];

const assumptionTips: Partial<Record<keyof ModelingAssumption, string>> = {
  revenue_cagr_start:
    "Starting annualized revenue growth rate before decay begins.",
  revenue_cagr_floor:
    "Long-run revenue growth rate the model converges toward.",
  revenue_decay_quarters:
    "How quickly growth decays from the start rate to the floor.",
  gross_margin_target:
    "Target gross margin the model glides toward over time.",
  gross_margin_glide_quarters:
    "Number of quarters to reach the target gross margin.",
  rnd_pct:
    "R&D as a % of revenue. Higher R&D compresses margins near-term.",
  sm_pct:
    "Sales & Marketing as a % of revenue; impacts acquisition efficiency.",
  ga_pct:
    "General & Administrative as a % of revenue; corporate overhead.",
  tax_rate:
    "Effective tax rate applied to pretax income.",
  interest_pct_revenue:
    "Interest expense as a % of revenue; proxy for financing cost.",
  dilution_pct_annual:
    "Annual share count growth; impacts EPS.",
  driver_blend_start_weight:
    "Weight on KPI-derived revenue at the start of the forecast.",
  driver_blend_end_weight:
    "Weight on KPI-derived revenue by the end of the blend ramp.",
  driver_blend_ramp_quarters:
    "Quarters to ramp driver blend weight from start to end.",
};

const kpiTips: Partial<Record<keyof ModelingKPI, string>> = {
  mau: "Monthly Active Users; broad engagement measure.",
  dau: "Daily Active Users; core activity driver for usage-based models.",
  paid_subs: "Number of paying subscribers.",
  paid_conversion_pct: "Share of active users who are paid customers.",
  arpu: "Average Revenue Per User over the period.",
  churn_pct: "Percent of users or subscribers that cancel in a period.",
};

const kpiFields: Array<{ key: keyof ModelingKPI; label: string }> = [
  { key: "mau", label: "MAU" },
  { key: "dau", label: "DAU" },
  { key: "paid_subs", label: "Paid subs" },
  { key: "paid_conversion_pct", label: "Paid %" },
  { key: "arpu", label: "ARPU" },
  { key: "churn_pct", label: "Churn %" },
];

const resultRows = [
  { key: "revenue", label: "Revenue" },
  { key: "gross_profit", label: "Gross Profit" },
  { key: "operating_income", label: "Operating Income" },
  { key: "net_income", label: "Net Income" },
  { key: "eps", label: "EPS" },
  { key: "gross_margin_pct", label: "Gross Margin %" },
  { key: "operating_margin_pct", label: "Operating Margin %" },
  { key: "net_margin_pct", label: "Net Margin %" },
];

function formatNumber(value?: number | null, opts: Intl.NumberFormatOptions = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, ...opts }).format(value);
}

function formatPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(undefined, {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(value);
}

export default function ModelingPage() {
  const { companyId } = useParams<{ companyId: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [assumptions, setAssumptions] = useState<ModelingAssumption[]>([]);
  const [kpis, setKpis] = useState<ModelingKPI[]>([]);
  const [quarters, setQuarters] = useState<Array<{ fiscal_year: number; fiscal_period: string }>>([]);
  const [scenario, setScenario] = useState<ScenarioName>("base");
  const [result, setResult] = useState<ModelingRunResponse | null>(null);
  const [mode, setMode] = useState<"quarterly" | "annual">("quarterly");
  const [companyName, setCompanyName] = useState<string>("");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [chatPending, setChatPending] = useState(false);
  const [chatEdits, setChatEdits] = useState<ModelingChatResponse["proposed_edits"]>([]);

  useEffect(() => {
    if (!companyId) return;
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const data = await fetchModelingData(companyId);
        if (!alive) return;
        setAssumptions(data.assumptions);
        setKpis(data.kpis);
        const quarterRows = (data.financials_quarterly || []).map((row) => ({
          fiscal_year: row.fiscal_year,
          fiscal_period: row.fiscal_period,
        }));
        setQuarters(quarterRows);
        setCompanyName(`${data.company.name ?? "Company"} (${data.company.ticker})`);
      } catch (err) {
        if (!alive) return;
        setError((err as Error).message || "Failed to load modeling data");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [companyId]);

  const scenarioAssumption = useMemo(
    () => assumptions.find((item) => item.scenario === scenario),
    [assumptions, scenario]
  );

  const setScenarioField = (key: keyof ModelingAssumption, value: number | string) => {
    setAssumptions((prev) =>
      prev.map((item) => {
        if (item.scenario !== scenario) return item;
        return { ...item, [key]: value };
      })
    );
  };

  const kpiMap = useMemo(() => {
    const map = new Map<string, ModelingKPI>();
    kpis.forEach((row) => {
      map.set(`${row.fiscal_year}-${row.fiscal_period}`, row);
    });
    return map;
  }, [kpis]);

  const sortedKpis = useMemo(() => {
    const baseRows = quarters.length
      ? quarters
      : kpis.map((row) => ({ fiscal_year: row.fiscal_year, fiscal_period: row.fiscal_period }));
    const rows = baseRows
      .map((row) => kpiMap.get(`${row.fiscal_year}-${row.fiscal_period}`) || row)
      .map((row) => ({
        fiscal_year: row.fiscal_year,
        fiscal_period: row.fiscal_period,
        mau: row.mau ?? null,
        dau: row.dau ?? null,
        paid_subs: row.paid_subs ?? null,
        paid_conversion_pct: row.paid_conversion_pct ?? null,
        arpu: row.arpu ?? null,
        churn_pct: row.churn_pct ?? null,
        source: row.source ?? "manual",
      }));
    rows.sort(
      (a, b) => a.fiscal_year - b.fiscal_year || a.fiscal_period.localeCompare(b.fiscal_period)
    );
    return rows.slice(-8);
  }, [kpiMap, kpis, quarters]);

  const scenarioResult = useMemo(
    () => result?.scenarios.find((item) => item.name === scenario),
    [result, scenario]
  );

  const tableRows = useMemo(() => {
    if (!scenarioResult) return [];
    return mode === "quarterly" ? scenarioResult.quarterly : scenarioResult.annual;
  }, [scenarioResult, mode]);

  const handleRun = async () => {
    if (!companyId) return;
    const response = await runModeling(companyId, assumptions, kpis);
    setResult(response);
  };

  const handleSave = async () => {
    if (!companyId) return;
    await saveModelingAssumptions(companyId, assumptions);
    await saveModelingKpis(companyId, kpis);
  };

  const handleChat = async () => {
    if (!companyId || !chatInput.trim()) return;
    const message = chatInput.trim();
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: message }]);
    setChatPending(true);
    try {
      const history = [...chatMessages, { role: "user", content: message }];
      const res = await chatModeling(companyId, message, assumptions, kpis, history);
      setChatMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      setChatEdits(res.proposed_edits || []);
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Could not reach the AI service." },
      ]);
    } finally {
      setChatPending(false);
    }
  };

  const applyChatEdits = () => {
    if (!chatEdits.length) return;
    setAssumptions((prev) => {
      const next = [...prev];
      chatEdits.forEach((edit) => {
        const path = edit.path || "";
        const [scenarioKey, field] = path.split(".");
        const idx = next.findIndex((item) => item.scenario === scenarioKey);
        if (idx === -1 || !field) return;
        const parsed = Number(edit.new);
        next[idx] = { ...next[idx], [field]: Number.isNaN(parsed) ? edit.new : parsed };
      });
      return next;
    });
    setChatEdits([]);
  };

  if (loading) {
    return <div className="text-sm text-zinc-500">Loading modeling data…</div>;
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-400/40 bg-red-50/60 dark:bg-red-900/20 px-4 py-3 text-sm text-red-600 dark:text-red-300">
        {error}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)_320px] gap-4">
      <div className={`${card} p-4 space-y-4`}>
        <button className={btnGhost} onClick={() => navigate(-1)}>
          <span className="inline-flex items-center gap-2">
            <ArrowLeftIcon />
            Back
          </span>
        </button>
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">Modeling</div>
          <div className="text-lg font-semibold">{companyName}</div>
          <div className="mt-1 text-xs text-zinc-500">
            <Tooltip label="Assumptions drive the forecast engine and scenario outputs.">
              <span>Assumptions guide projections</span>
            </Tooltip>
          </div>
        </div>
        <div className="flex gap-2">
          {(["base", "bull", "bear"] as ScenarioName[]).map((s) => (
            <button
              key={s}
              className={`${btnGhost} ${scenario === s ? "bg-zinc-200/80 dark:bg-zinc-800" : ""}`}
              onClick={() => setScenario(s)}
            >
              {s.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="space-y-3">
          {assumptionFields.map((field) => {
            const value = scenarioAssumption?.[field.key] ?? "";
            const isPct = pctFields.has(field.key as string);
            const displayValue =
              typeof value === "number" && isPct ? (value * 100).toFixed(2) : value;
            return (
              <label key={field.key} className="flex flex-col text-xs text-zinc-500 gap-1">
                <span className="flex items-center gap-1">
                  {field.label}
                  {assumptionTips[field.key] ? (
                    <Tooltip label={assumptionTips[field.key] ?? ""} />
                  ) : null}
                </span>
                <input
                  className="h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm text-zinc-900 dark:text-zinc-100"
                  type="number"
                  step="any"
                  value={displayValue ?? ""}
                  onChange={(e) => {
                    const raw = e.target.value;
                    const parsed = raw === "" ? "" : Number(raw);
                    if (raw === "") {
                      setScenarioField(field.key, raw);
                    } else if (!Number.isNaN(parsed)) {
                      setScenarioField(field.key, isPct ? parsed / 100 : parsed);
                    }
                  }}
                />
              </label>
            );
          })}
        </div>
        <div className="flex flex-col gap-2">
          <button className={btn} onClick={handleRun}>
            Run Model
          </button>
          <button className={btnGhost} onClick={handleSave}>
            Save Inputs
          </button>
        </div>
      </div>

      <div className={`${card} p-4 space-y-4`}>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            Projections
            <Tooltip label="Forecast output by quarter or fiscal year." />
          </h2>
          <div className="flex gap-2">
            <button
              className={`${btnGhost} ${mode === "quarterly" ? "bg-zinc-200/80 dark:bg-zinc-800" : ""}`}
              onClick={() => setMode("quarterly")}
            >
              Quarterly
            </button>
            <button
              className={`${btnGhost} ${mode === "annual" ? "bg-zinc-200/80 dark:bg-zinc-800" : ""}`}
              onClick={() => setMode("annual")}
            >
              Annual
            </button>
          </div>
        </div>

        {!scenarioResult ? (
          <div className="text-sm text-zinc-500">Run the model to see results.</div>
        ) : (
          <div className="overflow-auto border border-zinc-200 dark:border-zinc-800 rounded-xl">
            <table className="min-w-full text-sm">
              <thead className="sticky top-0 bg-zinc-50 dark:bg-zinc-900">
                <tr>
                  <th className="text-left px-3 py-2">Line item</th>
                  {tableRows.map((row) => (
                    <th key={`${row.fiscal_year}-${row.fiscal_period ?? "FY"}`} className="text-right px-3 py-2">
                      {mode === "quarterly" ? `${row.fiscal_period} ${row.fiscal_year}` : `FY ${row.fiscal_year}`}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {resultRows.map((rowDef) => (
                  <tr key={rowDef.key} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="px-3 py-2 font-medium">{rowDef.label}</td>
                    {tableRows.map((row) => {
                      const value = row[rowDef.key as keyof typeof row];
                      const isPct = rowDef.key.includes("margin");
                      return (
                        <td key={`${row.fiscal_year}-${row.fiscal_period}-${rowDef.key}`} className="px-3 py-2 text-right">
                          {isPct ? formatPercent(value as number | null) : formatNumber(value as number | null)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-200 flex items-center gap-2">
            KPIs (last 8 quarters)
            <Tooltip label="KPIs power driver-based revenue when provided." />
          </h3>
          <div className="overflow-auto border border-zinc-200 dark:border-zinc-800 rounded-xl">
            <table className="min-w-full text-xs">
              <thead className="bg-zinc-50 dark:bg-zinc-900">
                <tr>
                  <th className="px-2 py-2 text-left">Period</th>
                  {kpiFields.map((field) => (
                    <th key={field.key} className="px-2 py-2 text-right">
                      <span className="inline-flex items-center gap-1 justify-end">
                        {field.label}
                        {kpiTips[field.key] ? (
                          <Tooltip label={kpiTips[field.key] ?? ""} />
                        ) : null}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedKpis.map((row) => (
                  <tr key={`${row.fiscal_year}-${row.fiscal_period}`} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="px-2 py-1 text-left">{row.fiscal_period} {row.fiscal_year}</td>
                    {kpiFields.map((field) => {
                      const value = row[field.key] ?? "";
                      const isPct = field.key.includes("pct");
                      const display =
                        typeof value === "number" && isPct ? (value * 100).toFixed(2) : value;
                      return (
                        <td key={field.key} className="px-2 py-1 text-right">
                          <input
                            className="w-20 text-right bg-transparent border-b border-zinc-200 dark:border-zinc-700 focus:outline-none"
                            type="number"
                            step="any"
                            value={display}
                            onChange={(e) => {
                              const parsed = e.target.value === "" ? null : Number(e.target.value);
                              setKpis((prev) => {
                                const idx = prev.findIndex(
                                  (item) =>
                                    item.fiscal_year === row.fiscal_year &&
                                    item.fiscal_period === row.fiscal_period
                                );
                                const nextValue =
                                  parsed === null ? null : isPct ? parsed / 100 : parsed;
                                if (idx === -1) {
                                  return [
                                    ...prev,
                                    {
                                      fiscal_year: row.fiscal_year,
                                      fiscal_period: row.fiscal_period,
                                      [field.key]: nextValue,
                                    } as ModelingKPI,
                                  ];
                                }
                                return prev.map((item, i) =>
                                  i === idx ? { ...item, [field.key]: nextValue } : item
                                );
                              });
                            }}
                          />
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className={`${card} p-4 flex flex-col gap-3`}>
        <div className="text-sm font-semibold">Modeling AI</div>
        <div className="flex-1 overflow-auto border border-zinc-200 dark:border-zinc-800 rounded-xl p-3 space-y-3 text-sm">
          {chatMessages.length === 0 ? (
            <div className="text-zinc-500">Ask about growth, margins, or scenario changes.</div>
          ) : (
            chatMessages.map((msg, idx) => (
              <div key={idx} className={msg.role === "user" ? "text-right" : "text-left"}>
                <div className="inline-block px-3 py-2 rounded-xl bg-zinc-100 dark:bg-zinc-800">
                  {msg.content}
                </div>
              </div>
            ))
          )}
          {chatPending ? <div className="text-zinc-500">Thinking…</div> : null}
        </div>
        {chatEdits.length ? (
          <div className="border border-amber-200 dark:border-amber-700 bg-amber-50/60 dark:bg-amber-900/20 rounded-xl p-3 text-xs">
            <div className="font-semibold text-amber-700 dark:text-amber-200 mb-2">Proposed changes</div>
            <ul className="space-y-1 text-amber-700 dark:text-amber-100">
              {chatEdits.map((edit, idx) => (
                <li key={idx}>
                  {edit.path}: {String(edit.old)} → {String(edit.new)}
                </li>
              ))}
            </ul>
            <button className={`${btn} mt-3`} onClick={applyChatEdits}>
              Apply changes
            </button>
          </div>
        ) : null}
        <div className="flex gap-2">
          <input
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="Ask the AI..."
            className="flex-1 h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
          />
          <button className={btn} onClick={handleChat} disabled={chatPending}>
            <span className="inline-flex items-center gap-2">
              Send
              <PaperAirplaneIcon />
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}

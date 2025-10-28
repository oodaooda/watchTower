import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  fetchPharmaCompany,
  refreshPharmaCompany,
  pharmaChat,
  PharmaCompanyDetail,
  PharmaDrug,
} from "../lib/api";
import PriceHistoryChart from "../components/PriceHistoryChart";

const btn =
  "h-8 px-3 rounded-xl font-medium inline-flex items-center justify-center bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900 hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

const phaseColors: Record<string, string> = {
  "phase 1": "bg-sky-500/20 text-sky-400 border border-sky-500/40",
  "phase 2": "bg-purple-500/20 text-purple-300 border border-purple-500/40",
  "phase 3": "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40",
  "phase 4": "bg-emerald-600/20 text-emerald-200 border border-emerald-600/40",
  "fda review": "bg-amber-500/20 text-amber-300 border border-amber-500/40",
  approved: "bg-emerald-600/30 text-emerald-200 border border-emerald-600/50",
};

const statusColors: Record<string, string> = {
  active: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40",
  recruiting: "bg-sky-500/20 text-sky-300 border border-sky-500/40",
  completed: "bg-emerald-600/20 text-emerald-200 border border-emerald-600/40",
  suspended: "bg-amber-500/20 text-amber-300 border border-amber-500/40",
  withdrawn: "bg-rose-500/20 text-rose-300 border border-rose-500/40",
  terminated: "bg-rose-500/20 text-rose-300 border border-rose-500/40",
  inactive: "bg-zinc-600/20 text-zinc-300 border border-zinc-600/40",
};

function normalize(str: string | null | undefined): string {
  return (str || "").trim();
}

function badgeClass(base: Record<string, string>, value: string | null | undefined): string {
  if (!value) return "bg-zinc-600/20 text-zinc-300 border border-zinc-600/40";
  const key = value.toLowerCase();
  return base[key] ?? "bg-zinc-600/20 text-zinc-300 border border-zinc-600/40";
}

function progressFromPhase(phase: string | null | undefined): number {
  if (!phase) return 20;
  const key = phase.toLowerCase();
  if (key.includes("approved")) return 100;
  if (key.includes("phase 4")) return 90;
  if (key.includes("fda")) return 85;
  if (key.includes("phase 3")) return 75;
  if (key.includes("phase 2")) return 50;
  if (key.includes("phase 1")) return 25;
  if (key.includes("early")) return 15;
  return 20;
}

function successColor(prob: number | null | undefined): string {
  if (prob == null) return "bg-zinc-700 text-zinc-200";
  if (prob >= 70) return "bg-emerald-500/30 text-emerald-100";
  if (prob >= 40) return "bg-amber-500/30 text-amber-100";
  return "bg-rose-500/30 text-rose-100";
}

type TrialRow = {
  drugName: string;
  indication?: string | null;
  phase?: string | null;
  status?: string | null;
  successProbability?: number | null;
  estimatedCompletion?: string | null;
  enrollment?: number | null;
  nctId?: string | null;
  source?: string | null;
};

export default function PharmaCompanyPage() {
  const { identifier } = useParams<{ identifier: string }>();
  const [detail, setDetail] = useState<PharmaCompanyDetail | null>(null);
  const [liveActive, setLiveActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [chatMessage, setChatMessage] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatResponse, setChatResponse] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);

  useEffect(() => {
    if (!identifier) return;
    let cancelled = false;
    async function load(forceLive: boolean) {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchPharmaCompany(identifier, { force_live: forceLive });
        if (!cancelled) {
          setDetail(data);
          setLiveActive(forceLive);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load(false);
    return () => {
      cancelled = true;
    };
  }, [identifier]);

  const drugs = useMemo<PharmaDrug[]>(() => {
    if (!detail) return [];
    if (liveActive && detail.live_drugs && detail.live_drugs.length) return detail.live_drugs;
    return detail.drugs ?? [];
  }, [detail, liveActive]);

  const pipelineRows = useMemo<TrialRow[]>(() => {
    const rows: TrialRow[] = [];
  drugs.forEach((drug) => {
    drug.trials.forEach((trial) => {
      const status = normalize(trial.status);
      const statusLower = status.toLowerCase();
      if (
        statusLower &&
        !(
          statusLower.includes("activ") ||
          statusLower.includes("recruit") ||
          statusLower.includes("enrolling") ||
          statusLower.includes("complet") ||
          statusLower.includes("approved") ||
          statusLower.includes("marketing")
        )
      ) {
        return;
      }

      const friendlyName = prettifyDrugName(drug.name);
      rows.push({
        drugName: friendlyName,
        indication: drug.indication ?? trial.condition ?? null,
        phase: trial.phase,
        status: trial.status,
        successProbability: trial.success_probability ?? null,
        estimatedCompletion: trial.estimated_completion ?? null,
        enrollment: trial.enrollment ?? null,
        nctId: trial.nct_id ?? undefined,
        source: trial.source_url ?? undefined,
        });
      });
    });
    return rows.sort((a, b) => a.drugName.localeCompare(b.drugName));
  }, [drugs]);

  async function handleRefresh() {
    if (!identifier) return;
    setRefreshing(true);
    try {
      await refreshPharmaCompany(identifier);
      const data = await fetchPharmaCompany(identifier, { force_live: false });
      setDetail(data);
      setLiveActive(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefreshing(false);
    }
  }

  async function handleForceLive() {
    if (!identifier) return;
    setRefreshing(true);
    try {
      const data = await fetchPharmaCompany(identifier, { force_live: true });
      setDetail(data);
      setLiveActive(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefreshing(false);
    }
  }

  async function handleChatSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!chatMessage.trim()) return;
    setChatLoading(true);
    setChatError(null);
    try {
      const response = await pharmaChat(chatMessage);
      setChatResponse(response);
    } catch (err) {
      setChatError(err instanceof Error ? err.message : String(err));
      setChatResponse(null);
    } finally {
      setChatLoading(false);
    }
  }

  return (
    <div className="w-full max-w-[1400px] mx-auto px-4 md:px-6 lg:px-8 py-4 space-y-4">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{detail?.company.name ?? identifier}</h1>
          <p className="text-sm text-zinc-500">{detail?.company.lead_sponsor ?? "Lead sponsor unavailable"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link className={btn} to="/pharma">
            ← Pharma Dashboard
          </Link>
          <Link className={btn} to={`/financials/${detail?.company.id ?? ""}`}>
            Financials →
          </Link>
        </div>
      </div>

      {loading ? (
        <div className="text-sm text-zinc-500">Loading…</div>
      ) : error ? (
        <div className="text-sm text-red-500">{error}</div>
      ) : detail ? (
        <>
          <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 space-y-4">
            <div className="flex flex-col lg:flex-row lg:justify-between lg:items-start gap-4">
              <div>
                <div className="text-sm text-zinc-500">Ticker</div>
                <div className="text-xl font-semibold">{detail.company.ticker}</div>
              </div>
              <div className="space-x-2">
                <button
                  className={`${btn} ${refreshing ? "opacity-60" : ""}`}
                  onClick={handleRefresh}
                  disabled={refreshing}
                >
                  Refresh Stored Data
                </button>
                <button
                  className={`${btn} ${liveActive ? "opacity-60" : ""}`}
                  onClick={handleForceLive}
                  disabled={refreshing}
                >
                  Fetch Live Snapshot
                </button>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <MetricCard label="Lead Sponsor" value={detail.company.lead_sponsor ?? "—"} />
              <MetricCard label="Last Stored Refresh" value={detail.company.last_refreshed ? new Date(detail.company.last_refreshed).toLocaleString() : "Not yet"} />
            </div>
          </div>

          <PriceHistoryChart ticker={detail.company.ticker} />

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Drug Pipeline</h2>
              {liveActive && <span className="text-xs px-2 py-1 rounded-full bg-sky-100 text-sky-700">Live snapshot</span>}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <PhaseBadge label="Phase 1" colorClass={phaseColors["phase 1"]} />
              <PhaseBadge label="Phase 2" colorClass={phaseColors["phase 2"]} />
              <PhaseBadge label="Phase 3" colorClass={phaseColors["phase 3"]} />
              <PhaseBadge label="FDA Review" colorClass={phaseColors["fda review"]} />
              <PhaseBadge label="Approved" colorClass={phaseColors["approved"]} />
              <span className="ml-auto text-zinc-500">Status indicators:</span>
              <span className={`px-2 py-0.5 rounded-full text-xs ${statusColors["active"]}`}>Active</span>
              <span className={`px-2 py-0.5 rounded-full text-xs ${statusColors["inactive"]}`}>Inactive</span>
            </div>
            {pipelineRows.length === 0 ? (
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 text-sm text-zinc-500">
                No clinical trials tracked yet.
              </div>
            ) : (
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-50 dark:bg-zinc-900/70 text-xs uppercase tracking-wide text-zinc-500">
                      <tr>
                        <th className="px-4 py-3 text-left">Drug</th>
                        <th className="px-4 py-3 text-left">Indication</th>
                        <th className="px-4 py-3 text-left">Phase</th>
                        <th className="px-4 py-3 text-left">Status</th>
                        <th className="px-4 py-3 text-left">Progress</th>
                        <th className="px-4 py-3 text-left">Success Prob.</th>
                        <th className="px-4 py-3 text-left">Est. Completion</th>
                        <th className="px-4 py-3 text-left">Enrollment</th>
                        <th className="px-4 py-3 text-left">NCT ID</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                      {pipelineRows.map((row) => {
                        const phaseClass = badgeClass(phaseColors, row.phase);
                        const statusClass = badgeClass(statusColors, row.status);
                        const progress = progressFromPhase(row.phase);
                        const successClass = successColor(row.successProbability ?? null);

                        return (
                          <tr key={`${row.drugName}-${row.nctId ?? row.phase}`}>
                            <td className="px-4 py-3 font-semibold text-zinc-900 dark:text-zinc-100 whitespace-nowrap">
                              {row.drugName}
                            </td>
                            <td className="px-4 py-3 text-zinc-500 whitespace-nowrap">{row.indication ?? "—"}</td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-1 rounded-full text-xs font-semibold ${phaseClass}`}>
                                {row.phase ?? "Unknown"}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-1 rounded-full text-xs font-semibold ${statusClass}`}>
                                {row.status ?? "Unknown"}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <div className="w-36 h-3 rounded-full bg-zinc-800 overflow-hidden">
                                <div
                                  className="h-full bg-sky-500/70"
                                  style={{ width: `${Math.min(100, Math.max(5, progress))}%` }}
                                />
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-1 rounded-md text-xs font-semibold ${successClass}`}>
                                {row.successProbability != null ? `${row.successProbability.toFixed(1)}%` : "—"}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-zinc-500 whitespace-nowrap">
                              {row.estimatedCompletion
                                ? new Date(row.estimatedCompletion).toLocaleDateString(undefined, {
                                    month: "short",
                                    year: "numeric",
                                  })
                                : "—"}
                            </td>
                            <td className="px-4 py-3 text-zinc-500">{row.enrollment != null ? row.enrollment.toLocaleString() : "—"}</td>
                            <td className="px-4 py-3 text-sky-500">
                              {row.nctId ? (
                                row.source ? (
                                  <a href={row.source} target="_blank" rel="noreferrer">
                                    {row.nctId}
                                  </a>
                                ) : (
                                  row.nctId
                                )
                              ) : (
                                "—"
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 space-y-3">
              <h3 className="text-lg font-semibold">Pharma Advisor</h3>
              <form className="space-y-2" onSubmit={handleChatSubmit}>
                <textarea
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  placeholder="Ask about the pipeline, competitive landscape, or risks…"
                  className="w-full min-h-[120px] rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/40"
                />
                <div className="flex justify-end">
                  <button type="submit" className={`${btn} ${chatLoading ? "opacity-60" : ""}`} disabled={chatLoading}>
                    Ask
                  </button>
                </div>
              </form>
              {chatLoading ? (
                <div className="text-sm text-zinc-500">Analyzing…</div>
              ) : chatError ? (
                <div className="text-sm text-red-500">{chatError}</div>
              ) : chatResponse ? (
                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 p-3 text-sm whitespace-pre-wrap">
                  {chatResponse}
                </div>
              ) : null}
            </div>

            <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 space-y-3">
              <h3 className="text-lg font-semibold">Analysis</h3>
              {detail.analysis ? (
                <div className="text-sm text-zinc-600 dark:text-zinc-300 whitespace-pre-wrap leading-relaxed">
                  {detail.analysis}
                </div>
              ) : (
                <div className="text-sm text-zinc-500">No stored analysis yet. Use the advisor to generate commentary.</div>
              )}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4">
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mt-1">{value ?? "—"}</div>
    </div>
  );
}

function PhaseBadge({ label, colorClass }: { label: string; colorClass: string }) {
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-semibold ${colorClass}`}>{label}</span>
  );
}

function prettifyDrugName(raw: string): string {
  const match = raw.match(/\(([^)]+)\)/);
  if (match) {
    const candidate = match[1].trim();
    if (candidate.length > 3) return candidate;
  }
  const cleaned = raw.replace(/^[Aa]ctive drug\s*/g, "").replace(/\s+/g, " ").trim();
  return cleaned.length > 3 ? cleaned : raw;
}

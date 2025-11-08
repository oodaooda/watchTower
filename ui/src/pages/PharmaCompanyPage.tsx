import { Fragment, useEffect, useMemo, useState } from "react";
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
  "phase 1/phase 2": "bg-purple-500/20 text-purple-300 border border-purple-500/40",
  "phase 2/phase 3": "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40",
  commercial: "bg-emerald-600/30 text-emerald-200 border border-emerald-600/50",
};

const statusColors: Record<string, string> = {
  active: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40",
  recruiting: "bg-sky-500/20 text-sky-300 border border-sky-500/40",
  completed: "bg-emerald-600/20 text-emerald-200 border border-emerald-600/40",
  suspended: "bg-amber-500/20 text-amber-300 border border-amber-500/40",
  withdrawn: "bg-rose-500/20 text-rose-300 border border-rose-500/40",
  terminated: "bg-rose-500/20 text-rose-300 border border-rose-500/40",
  inactive: "bg-zinc-600/20 text-zinc-300 border border-zinc-600/40",
  "approved for marketing": "bg-emerald-600/20 text-emerald-200 border border-emerald-600/40",
  "not yet recruiting": "bg-sky-500/20 text-sky-300 border border-sky-500/40",
  "active, not recruiting": "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40",
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
  if (key.includes("commercial")) return 100;
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

type ActivePipelineRow = {
  drugName: string;
  rawDrugName?: string | null;
  label?: string | null;
  indication?: string | null;
  stage?: string | null;
  status?: string | null;
  statusLower?: string | null;
  probability?: number | null;
  probabilitySource?: string | null;
  peakSales?: number | null;
  peakSalesCurrency?: string | null;
  expectedValue?: number | null;
  expectedValueCurrency?: string | null;
  startDate?: string | null;
  completionDate?: string | null;
  statusVerified?: string | null;
  nctId?: string | null;
  source?: string | null;
  outcome?: string | null;
  hasResults?: boolean | null;
  trialsCount?: number;
  notes?: string | null;
  latestAnnual?: { year: number; revenue: number | null; currency?: string | null };
  latestQuarter?: { year: number; quarter?: number | null; revenue: number | null; currency?: string | null };
  isCommercial: boolean;
  isTerminated: boolean;
};

type HistoricalRow = {
  drugName: string;
  rawDrugName?: string | null;
  label?: string | null;
  indication?: string | null;
  phase?: string | null;
  status?: string | null;
  category?: string | null;
  successProbability?: number | null;
  estimatedCompletion?: string | null;
  startDate?: string | null;
  enrollment?: number | null;
  nctId?: string | null;
  source?: string | null;
  statusVerified?: string | null;
  outcome?: string | null;
  notes?: string | null;
  latestAnnual?: { year: number; revenue: number | null; currency?: string | null };
  latestQuarter?: { year: number; quarter?: number | null; revenue: number | null; currency?: string | null };
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
    const currentId = identifier;
    let cancelled = false;
    async function load(forceLive: boolean) {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchPharmaCompany(currentId, { force_live: forceLive });
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

  const activeDrugPayloads = useMemo<PharmaDrug[]>(() => {
    if (!detail) return [];
    if (liveActive && detail.live_drugs && detail.live_drugs.length) return detail.live_drugs;
    return detail.drugs ?? [];
  }, [detail, liveActive]);

  const legacyDrugPayloads = useMemo<PharmaDrug[]>(() => {
    if (!detail || liveActive) return [];
    return detail.legacy_drugs ?? [];
  }, [detail, liveActive]);

  const activeRows = useMemo<ActivePipelineRow[]>(() => {
    const rows: ActivePipelineRow[] = [];
    activeDrugPayloads.forEach((drug) => {
      const summary = drug.summary;
      const activeTrials = drug.active_trials ?? [];
      const fallbackTrials = activeTrials.length ? activeTrials : (drug.historical_trials ?? []);
      const primary = fallbackTrials[0] ?? null;
      if (!primary && !summary.is_commercial && !(summary.metadata_source === "manual")) return;

      const sales = summary.sales ?? drug.sales ?? { annual: [], quarterly: [] };
      const latestAnnual = sales.annual && sales.annual.length ? sales.annual[0] : undefined;
      const latestQuarter = sales.quarterly && sales.quarterly.length ? sales.quarterly[0] : undefined;

      const display = primary ?? {
        phase: summary.stage ?? null,
        status: summary.status ?? (summary.is_commercial ? "Approved For Marketing" : null),
        success_probability: summary.probability ?? null,
        condition: drug.indication ?? null,
        estimated_completion: summary.primary_estimated_completion ?? null,
        start_date: summary.primary_start_date ?? null,
        nct_id: summary.primary_nct_id ?? null,
        source_url: undefined,
        outcome: summary.is_commercial ? "Approved for marketing" : null,
        has_results: null,
        status_last_verified: null,
      };

      const statusText = (summary.status ?? (display as any).status ?? "").toString();
      const statusLower = statusText.toLowerCase();
      const stageText = (summary.stage ?? (display as any).phase ?? "").toString();
      const isCommercial =
        Boolean(summary.is_commercial) ||
        stageText.toLowerCase().includes("commercial") ||
        statusLower.includes("approved");
      const isTerminated =
        !isCommercial &&
        (statusLower.includes("termin") || statusLower.includes("withdrawn") || statusLower.includes("suspend"));

      rows.push({
        drugName: prettifyDrugName((drug.display_name ?? drug.name) || "Unknown Drug"),
        rawDrugName: drug.name,
        label: summary.label ?? drug.label ?? null,
        indication: drug.indication ?? (display as any).condition ?? null,
        stage: summary.stage ?? (display as any).phase ?? null,
        status: statusText || null,
        statusLower: statusLower || null,
        probability: summary.probability ?? (display as any).success_probability ?? null,
        probabilitySource: summary.probability_source ?? null,
        peakSales: summary.peak_sales ?? null,
        peakSalesCurrency: summary.peak_sales_currency ?? null,
        expectedValue: summary.expected_value ?? null,
        expectedValueCurrency: summary.expected_value_currency ?? null,
        latestAnnual,
        latestQuarter,
        startDate: summary.primary_start_date ?? (display as any).start_date ?? null,
        completionDate: summary.primary_estimated_completion ?? (display as any).estimated_completion ?? null,
        statusVerified: (display as any).status_last_verified ?? null,
        nctId: summary.primary_nct_id ?? (display as any).nct_id ?? null,
        source: (display as any).source_url ?? null,
        outcome: (display as any).outcome ?? null,
        hasResults: (display as any).has_results ?? null,
        trialsCount: summary.active_trial_count ?? activeTrials.length,
        notes: summary.notes ?? null,
        isCommercial,
        isTerminated,
      });
    });
    return rows.sort((a, b) => a.drugName.localeCompare(b.drugName));
  }, [activeDrugPayloads]);

  const legacyRows = useMemo<HistoricalRow[]>(() => {
    const rows: HistoricalRow[] = [];
    const source = liveActive ? [] : legacyDrugPayloads.length ? legacyDrugPayloads : detail?.drugs ?? [];
    source.forEach((drug) => {
      const summary = drug.summary;
      const label = summary.label ?? drug.label ?? null;
      const baseName = prettifyDrugName((drug.display_name ?? drug.name) || "Unknown Drug");
      const sales = summary.sales ?? drug.sales ?? { annual: [], quarterly: [] };
      const latestAnnual = sales.annual && sales.annual.length ? sales.annual[0] : undefined;
      const latestQuarter = sales.quarterly && sales.quarterly.length ? sales.quarterly[0] : undefined;

      (drug.historical_trials ?? []).forEach((trial) => {
        rows.push({
          drugName: baseName,
          rawDrugName: drug.name,
          label,
          indication: drug.indication ?? trial.condition ?? null,
          phase: trial.phase ?? null,
          status: trial.status ?? null,
          category: trial.category ?? (trial.is_active ? "active" : "historical"),
          successProbability: trial.success_probability ?? null,
          estimatedCompletion: trial.estimated_completion ?? null,
          startDate: trial.start_date ?? null,
          enrollment: trial.enrollment ?? null,
          nctId: trial.nct_id ?? null,
          source: trial.source_url ?? null,
          statusVerified: trial.status_last_verified ?? null,
          outcome: trial.outcome ?? null,
          notes: summary.notes ?? null,
          latestAnnual,
          latestQuarter,
        });
      });

      if (summary.is_commercial && (drug.historical_trials?.length ?? 0) === 0) {
        rows.push({
          drugName: baseName,
          rawDrugName: drug.name,
          label,
          indication: drug.indication ?? null,
          phase: summary.stage ?? "Commercial",
          status: summary.status ?? "Approved For Marketing",
          category: "commercial",
          successProbability: summary.probability ?? null,
          estimatedCompletion: summary.primary_estimated_completion ?? null,
          startDate: summary.primary_start_date ?? null,
          enrollment: null,
          nctId: summary.primary_nct_id ?? null,
          source: null,
          statusVerified: null,
          outcome: "Approved for marketing",
          notes: summary.notes ?? null,
          latestAnnual,
          latestQuarter,
        });
      }
    });
    return rows.sort((a, b) => a.drugName.localeCompare(b.drugName));
  }, [legacyDrugPayloads, detail, liveActive]);

  const commercialRows = useMemo(() => activeRows.filter((row) => row.isCommercial), [activeRows]);
  const terminatedRows = useMemo(() => activeRows.filter((row) => !row.isCommercial && row.isTerminated), [activeRows]);
  const pipelineRows = useMemo(
    () => activeRows.filter((row) => !row.isCommercial && !row.isTerminated),
    [activeRows]
  );

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

  const summary = detail?.summary;
  const evCurrencyOptions = summary ? Object.keys(summary.expected_value_by_currency ?? {}) : [];
  const peakCurrencyOptions = summary ? Object.keys(summary.peak_sales_by_currency ?? {}) : [];
  const evCurrency = evCurrencyOptions.includes("USD") ? "USD" : evCurrencyOptions[0];
  const peakCurrency = peakCurrencyOptions.includes("USD") ? "USD" : peakCurrencyOptions[0];
  const evTotal = summary && evCurrency ? summary.expected_value_by_currency[evCurrency] : undefined;
  const peakTotal = summary && peakCurrency ? summary.peak_sales_by_currency[peakCurrency] : undefined;
  const salesCurrencyOptions = summary ? Object.keys(summary.latest_annual_sales_by_currency ?? {}) : [];
  const salesCurrency = salesCurrencyOptions.includes("USD") ? "USD" : salesCurrencyOptions[0];
  const salesTotal = summary && salesCurrency ? summary.latest_annual_sales_by_currency[salesCurrency] : undefined;

  return (
    <div className="w-full max-w-[1800px] mx-auto px-4 md:px-6 lg:px-8 py-4 space-y-4">
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

            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
              <MetricCard label="Lead Sponsor" value={detail.company.lead_sponsor ?? "—"} />
              <MetricCard label="Last Stored Refresh" value={detail.company.last_refreshed ? new Date(detail.company.last_refreshed).toLocaleString() : "Not yet"} />
              <MetricCard label="Active Assets" value={summary ? String(summary.active_drug_count ?? 0) : "—"} />
              <MetricCard label="Active Trials" value={summary ? String(summary.active_trials ?? 0) : "—"} />
              <MetricCard label="Commercial Assets" value={summary ? String(summary.commercial_assets ?? 0) : "—"} />
              <MetricCard label="Legacy Programs" value={summary ? String(summary.legacy_drug_count ?? 0) : "—"} />
              <MetricCard label="Legacy Trials" value={summary ? String(summary.legacy_trial_count ?? 0) : "—"} />
              <MetricCard
                label={`Total Expected Value${evCurrency ? ` (${evCurrency})` : ""}`}
                value={evTotal != null ? formatCurrency(evTotal, evCurrency) : "—"}
              />
              <MetricCard
                label={`Total Peak Sales${peakCurrency ? ` (${peakCurrency})` : ""}`}
                value={peakTotal != null ? formatCurrency(peakTotal, peakCurrency) : "—"}
              />
              <MetricCard
                label={`Latest Annual Sales${salesCurrency ? ` (${salesCurrency})` : ""}`}
                value={salesTotal != null ? formatCurrency(salesTotal, salesCurrency) : "—"}
              />
            </div>
          </div>

          <PriceHistoryChart ticker={detail.company.ticker} />

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Commercial Portfolio</h2>
            </div>
            {commercialRows.length === 0 ? (
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 text-sm text-zinc-500">
                No commercial assets tracked yet.
              </div>
            ) : (
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-50 dark:bg-zinc-900/70 text-xs uppercase tracking-wide text-zinc-500">
                      <tr>
                        <th className="px-4 py-3 text-left">Drug</th>
                        <th className="px-4 py-3 text-left">Indication</th>
                        <th className="px-4 py-3 text-left">Stage</th>
                        <th className="px-4 py-3 text-left">Status</th>
                        <th className="px-4 py-3 text-left">Probability</th>
                        <th className="px-4 py-3 text-left">Peak Sales</th>
                        <th className="px-4 py-3 text-left">Expected Value</th>
                        <th className="px-4 py-3 text-left">Latest Sales</th>
                        <th className="px-4 py-3 text-left">Outcome</th>
                        <th className="px-4 py-3 text-left">NCT ID</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                      {commercialRows.map((row) => {
                        const probabilityClass = successColor(row.probability ?? null);
                        return (
                          <Fragment key={`${row.drugName}-commercial`}>
                            <tr>
                              <td className="px-4 py-3 font-semibold text-zinc-900 dark:text-zinc-100">
                                <div>{row.drugName}</div>
                                {row.rawDrugName && row.rawDrugName !== row.drugName ? (
                                  <div className="text-xs text-zinc-500">{row.rawDrugName}</div>
                                ) : null}
                                <div className="mt-1 flex flex-wrap items-center gap-1 text-[10px] text-zinc-500">
                                  {row.label ? (
                                    <span className="inline-flex items-center rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-semibold px-2 py-0.5">
                                      {row.label}
                                    </span>
                                  ) : null}
                                  {row.trialsCount ? <span>{row.trialsCount} active trials</span> : null}
                                </div>
                                {row.latestAnnual && row.latestAnnual.revenue != null ? (
                                  <div className="text-xs text-emerald-400">
                                    FY {row.latestAnnual.year}: {formatCurrency(row.latestAnnual.revenue, row.latestAnnual.currency)}
                                  </div>
                                ) : null}
                                {row.latestQuarter && row.latestQuarter.revenue != null ? (
                                  <div className="text-xs text-emerald-300">
                                    {formatQuarter(row.latestQuarter.year, row.latestQuarter.quarter ?? null)}: {formatCurrency(row.latestQuarter.revenue, row.latestQuarter.currency)}
                                  </div>
                                ) : null}
                              </td>
                              <td className="px-4 py-3 text-zinc-500 whitespace-normal break-words max-w-xs">{row.indication ?? "—"}</td>
                              <td className="px-4 py-3">
                                <span className={`px-2 py-1 rounded-full text-xs font-semibold ${badgeClass(phaseColors, row.stage)}`}>
                                  {row.stage ?? "Commercial"}
                                </span>
                              </td>
                              <td className="px-4 py-3">
                                <span className={`px-2 py-1 rounded-full text-xs font-semibold ${badgeClass(statusColors, row.status)}`}>
                                  {row.status ?? "Approved"}
                                </span>
                              </td>
                              <td className="px-4 py-3">
                                <span className={`px-2 py-1 rounded-full text-xs font-semibold ${probabilityClass}`}>
                                  {row.probability != null ? `${row.probability.toFixed(1)}%` : "—"}
                                </span>
                                {row.probabilitySource === "override" ? (
                                  <span className="ml-2 text-[10px] text-zinc-500">override</span>
                                ) : null}
                              </td>
                              <td className="px-4 py-3 text-zinc-500 whitespace-nowrap">
                                {row.peakSales != null ? formatCurrency(row.peakSales, row.peakSalesCurrency) : "—"}
                              </td>
                              <td className="px-4 py-3 text-zinc-500 whitespace-nowrap">
                                {row.expectedValue != null
                                  ? formatCurrency(row.expectedValue, row.expectedValueCurrency ?? row.peakSalesCurrency)
                                  : "—"}
                              </td>
                              <td className="px-4 py-3 text-zinc-500 whitespace-nowrap">
                                {row.latestAnnual && row.latestAnnual.revenue != null
                                  ? formatCurrency(row.latestAnnual.revenue, row.latestAnnual.currency)
                                  : row.latestQuarter && row.latestQuarter.revenue != null
                                  ? `${formatQuarter(row.latestQuarter.year, row.latestQuarter.quarter ?? null)} ${formatCurrency(row.latestQuarter.revenue, row.latestQuarter.currency)}`
                                  : "—"}
                              </td>
                              <td className="px-4 py-3 text-zinc-500">{row.outcome ?? "—"}</td>
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
                            {row.notes ? (
                              <tr className="bg-zinc-950/60">
                                <td colSpan={10} className="px-6 py-2 text-xs text-zinc-500 dark:text-zinc-400">
                                  {row.notes}
                                </td>
                              </tr>
                            ) : null}
                          </Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Pipeline Programs</h2>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <PhaseBadge label="Phase 1" colorClass={phaseColors["phase 1"]} />
              <PhaseBadge label="Phase 2" colorClass={phaseColors["phase 2"]} />
              <PhaseBadge label="Phase 3" colorClass={phaseColors["phase 3"]} />
              <PhaseBadge label="FDA Review" colorClass={phaseColors["fda review"]} />
            </div>
            {pipelineRows.length === 0 ? (
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 text-sm text-zinc-500">
                No pipeline programs tracked yet.
              </div>
            ) : (
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-50 dark:bg-zinc-900/70 text-xs uppercase tracking-wide text-zinc-500">
                      <tr>
                        <th className="px-4 py-3 text-left">Drug</th>
                        <th className="px-4 py-3 text-left">Indication</th>
                        <th className="px-4 py-3 text-left">Stage</th>
                        <th className="px-4 py-3 text-left">Progress</th>
                        <th className="px-4 py-3 text-left">Status</th>
                        <th className="px-4 py-3 text-left">Probability</th>
                        <th className="px-4 py-3 text-left">Peak Sales</th>
                        <th className="px-4 py-3 text-left">Expected Value</th>
                        <th className="px-4 py-3 text-left">Start</th>
                        <th className="px-4 py-3 text-left">Completion</th>
                        <th className="px-4 py-3 text-left">Status Verified</th>
                        <th className="px-4 py-3 text-left">Outcome</th>
                        <th className="px-4 py-3 text-left">NCT ID</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                      {pipelineRows.map((row) => {
                        const stageClass = badgeClass(phaseColors, row.stage);
                        const statusClass = badgeClass(statusColors, row.status);
                        const progress = progressFromPhase(row.stage);
                        const probabilityClass = successColor(row.probability ?? null);

                        return (
                          <Fragment key={`${row.drugName}-pipeline`}>
                            <tr>
                              <td className="px-4 py-3 font-semibold text-zinc-900 dark:text-zinc-100">
                                <div>{row.drugName}</div>
                                {row.rawDrugName && row.rawDrugName !== row.drugName ? (
                                  <div className="text-xs text-zinc-500">{row.rawDrugName}</div>
                                ) : null}
                                <div className="mt-1 flex flex-wrap items-center gap-1 text-[10px] text-zinc-500">
                                  {row.label ? (
                                    <span className="inline-flex items-center rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-semibold px-2 py-0.5">
                                      {row.label}
                                    </span>
                                  ) : null}
                                  {row.trialsCount ? <span>{row.trialsCount} active trials</span> : null}
                                </div>
                              </td>
                              <td className="px-4 py-3 text-zinc-500 whitespace-normal break-words max-w-xs">{row.indication ?? "—"}</td>
                              <td className="px-4 py-3">
                                <span className={`px-2 py-1 rounded-full text-xs font-semibold ${stageClass}`}>
                                  {row.stage ?? "Unknown"}
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
                                <span className={`px-2 py-1 rounded-full text-xs font-semibold ${statusClass}`}>
                                  {row.status ?? "Unknown"}
                                </span>
                              </td>
                              <td className="px-4 py-3">
                                <span className={`px-2 py-1 rounded-full text-xs font-semibold ${probabilityClass}`}>
                                  {row.probability != null ? `${row.probability.toFixed(1)}%` : "—"}
                                </span>
                                {row.probabilitySource === "override" ? (
                                  <span className="ml-2 text-[10px] text-zinc-500">override</span>
                                ) : null}
                              </td>
                              <td className="px-4 py-3 text-zinc-500 whitespace-nowrap">
                                {row.peakSales != null ? formatCurrency(row.peakSales, row.peakSalesCurrency) : "—"}
                              </td>
                              <td className="px-4 py-3 text-zinc-500 whitespace-nowrap">
                                {row.expectedValue != null
                                  ? formatCurrency(row.expectedValue, row.expectedValueCurrency ?? row.peakSalesCurrency)
                                  : "—"}
                              </td>
                              <td className="px-4 py-3 text-zinc-500">{formatDate(row.startDate)}</td>
                              <td className="px-4 py-3 text-zinc-500">{formatDate(row.completionDate)}</td>
                              <td className="px-4 py-3 text-zinc-500">{formatDate(row.statusVerified)}</td>
                              <td className="px-4 py-3 text-zinc-500">{row.outcome ?? "—"}</td>
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
                            {row.notes ? (
                              <tr className="bg-zinc-950/60">
                                <td colSpan={13} className="px-6 py-2 text-xs text-zinc-500 dark:text-zinc-400">
                                  {row.notes}
                                </td>
                              </tr>
                            ) : null}
                          </Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Terminated Programs</h2>
            </div>
            {terminatedRows.length === 0 ? (
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 text-sm text-zinc-500">
                No terminated trials tracked yet.
              </div>
            ) : (
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-50 dark:bg-zinc-900/70 text-xs uppercase tracking-wide text-zinc-500">
                      <tr>
                        <th className="px-4 py-3 text-left">Drug</th>
                        <th className="px-4 py-3 text-left">Indication</th>
                        <th className="px-4 py-3 text-left">Status</th>
                        <th className="px-4 py-3 text-left">Completion</th>
                        <th className="px-4 py-3 text-left">Outcome</th>
                        <th className="px-4 py-3 text-left">NCT ID</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                      {terminatedRows.map((row) => (
                        <Fragment key={`${row.drugName}-terminated`}>
                          <tr>
                            <td className="px-4 py-3 font-semibold text-zinc-900 dark:text-zinc-100">
                              <div>{row.drugName}</div>
                              {row.rawDrugName && row.rawDrugName !== row.drugName ? (
                                <div className="text-xs text-zinc-500">{row.rawDrugName}</div>
                              ) : null}
                            </td>
                            <td className="px-4 py-3 text-zinc-500 whitespace-normal break-words max-w-xs">{row.indication ?? "—"}</td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-1 rounded-full text-xs font-semibold ${badgeClass(statusColors, row.status)}`}>
                                {row.status ?? "Terminated"}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-zinc-500">{formatDate(row.completionDate)}</td>
                            <td className="px-4 py-3 text-zinc-500">{row.outcome ?? "—"}</td>
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
                          {row.notes ? (
                            <tr className="bg-zinc-950/60">
                              <td colSpan={6} className="px-6 py-2 text-xs text-zinc-500 dark:text-zinc-400">
                                {row.notes}
                              </td>
                            </tr>
                          ) : null}
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Legacy Programs</h2>
            </div>
            {legacyRows.length === 0 ? (
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 text-sm text-zinc-500">
                No legacy records available.
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
                        <th className="px-4 py-3 text-left">Category</th>
                        <th className="px-4 py-3 text-left">Success Prob.</th>
                        <th className="px-4 py-3 text-left">Start</th>
                        <th className="px-4 py-3 text-left">Completion</th>
                        <th className="px-4 py-3 text-left">Enrollment</th>
                        <th className="px-4 py-3 text-left">NCT ID</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                      {legacyRows.map((row) => {
                        const phaseClass = badgeClass(phaseColors, row.phase);
                        const statusClass = badgeClass(statusColors, row.status);
                        const probabilityClass = successColor(row.successProbability ?? null);

                        return (
                          <tr key={`${row.drugName}-${row.nctId ?? row.phase}`}>
                            <td className="px-4 py-3 font-semibold text-zinc-900 dark:text-zinc-100">
                              <div>{row.drugName}</div>
                              {row.rawDrugName && row.rawDrugName !== row.drugName ? (
                                <div className="text-xs text-zinc-500">{row.rawDrugName}</div>
                              ) : null}
                              {row.label ? (
                                <span className="mt-1 inline-flex items-center rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 text-[10px] font-semibold px-2 py-0.5">
                                  {row.label}
                                </span>
                              ) : null}
                              {row.notes ? (
                                <div className="mt-1 text-xs text-zinc-500/80 dark:text-zinc-400">{row.notes}</div>
                              ) : null}
                              {row.latestAnnual && row.latestAnnual.revenue != null ? (
                                <div className="text-xs text-emerald-400">
                                  FY {row.latestAnnual.year}: {formatCurrency(row.latestAnnual.revenue, row.latestAnnual.currency)}
                                </div>
                              ) : null}
                              {row.latestQuarter && row.latestQuarter.revenue != null ? (
                                <div className="text-xs text-emerald-300">
                                  {formatQuarter(row.latestQuarter.year, row.latestQuarter.quarter ?? null)}: {formatCurrency(row.latestQuarter.revenue, row.latestQuarter.currency)}
                                </div>
                              ) : null}
                            </td>
                            <td className="px-4 py-3 text-zinc-500 whitespace-normal break-words max-w-xs">{row.indication ?? "—"}</td>
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
                            <td className="px-4 py-3 text-zinc-500 capitalize">{row.category ?? "—"}</td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-1 rounded-md text-xs font-semibold ${probabilityClass}`}>
                                {row.successProbability != null ? `${row.successProbability.toFixed(1)}%` : "—"}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-zinc-500">{formatDate(row.startDate)}</td>
                            <td className="px-4 py-3 text-zinc-500">{formatDate(row.estimatedCompletion)}</td>
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

function formatCurrency(value: number | null | undefined, currency?: string | null): string {
  if (value == null) return "—";
  const code = currency && currency.length === 3 ? currency : "USD";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: code,
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return `${code} ${value.toLocaleString()}`;
  }
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

function formatQuarter(year?: number | null, quarter?: number | null): string {
  if (year == null || quarter == null) return "—";
  return `Q${quarter} ${year}`;
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

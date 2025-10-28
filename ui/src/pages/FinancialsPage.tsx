import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";

type Row = {
  fiscal_year: number;
  fiscal_period?: string | null; // Q1–Q4 when quarterly
  revenue?: number | null;
  cost_of_revenue?: number | null;
  gross_profit?: number | null;
  research_and_development?: number | null;
  selling_general_admin?: number | null;
  operating_income?: number | null;
  interest_expense?: number | null;
  income_tax_expense?: number | null;
  net_income?: number | null;
  eps_diluted?: number | null;
  assets_total?: number | null;
  equity_total?: number | null;
  cash_and_sti?: number | null;
  total_debt?: number | null;
  shares_outstanding?: number | null;
  cfo?: number | null;
  capex?: number | null;
  fcf?: number | null;
  depreciation_amortization?: number | null;
  share_based_comp?: number | null;
  dividends_paid?: number | null;
  share_repurchases?: number | null;
  liabilities_current?: number | null;
  liabilities_longterm?: number | null;
  inventories?: number | null;
  accounts_receivable?: number | null;
  accounts_payable?: number | null;
};

// 🔹 Company info type
type Company = {
  id: number;
  ticker: string;
  name: string;
  description?: string | null;
};

const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const btn =
  "h-8 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900 " +
  "hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

function formatNum(v?: number | null, opts: Intl.NumberFormatOptions = {}) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const fmt = new Intl.NumberFormat(undefined, {
    notation: "compact",
    maximumFractionDigits: 2,
    ...opts,
  });
  return fmt.format(v);
}

function useContainerWidth<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((e) => setW(e[0]?.contentRect?.width ?? 0));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return { ref, w };
}

export default function FinancialsPage() {
  const { companyId } = useParams<{ companyId: string }>();
  const navigate = useNavigate();

  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"annual" | "quarterly">("annual");

  // 🔹 Company state
  const [company, setCompany] = useState<Company | null>(null);

  // fetch company details
  useEffect(() => {
    if (!companyId) return;
    fetch(`${API}/companies/${companyId}`)
      .then((r) => r.json())
      .then(setCompany)
      .catch(() => setCompany(null));
  }, [companyId]);

  // fetch financials (annual vs quarterly)
  useEffect(() => {
    if (!companyId) return;
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const endpoint =
          mode === "annual"
            ? `${API}/financials/${companyId}`
            : `${API}/financials/quarterly/${companyId}`;
        const r = await fetch(endpoint);
        let data: Row[] = await r.json();

        // 🔹 sort
        data = (data || []).sort(
          (a, b) =>
            a.fiscal_year - b.fiscal_year ||
            (a.fiscal_period || "").localeCompare(b.fiscal_period || "")
        );

        // 🔹 keep only last 16 quarters (~4 years)
        if (mode === "quarterly") {
          data = data.slice(-16);
        }

        if (alive) setRows(data);
      } catch {
        if (alive) setRows([]);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [companyId, mode]);

  const fiscalYears = useMemo(() => rows.map((r) => r.fiscal_year), [rows]);
  const byYear = useMemo(
    () => new Map(rows.map((r) => [r.fiscal_year + (r.fiscal_period ?? ""), r])),
    [rows]
  );
  const val = (row: Row, k: keyof Row) =>
    (row as any)?.[k] as number | null | undefined;

  const sections = [
    {
      title: "Income Statement",
      lines: [
        { key: "revenue", label: "Revenue" },
        { key: "cost_of_revenue", label: "Cost of Revenue" },
        { key: "gross_profit", label: "Gross Profit" },
        { key: "research_and_development", label: "R&D Expense" },
        { key: "selling_general_admin", label: "SG&A Expense" },
        { key: "operating_income", label: "Operating Income" },
        { key: "net_income", label: "Net Income" },
        { key: "interest_expense", label: "Interest Expense" },
        { key: "income_tax_expense", label: "Tax Expense" },
        {
          key: "eps_diluted",
          label: "EPS (Diluted, proxy)",
          fmt: (v?: number | null) =>
            formatNum(v, { notation: "standard", maximumFractionDigits: 2 }),
        },
      ],
    },
    {
      title: "Cash Flow",
      lines: [
        { key: "cfo", label: "Cash From Operations (CFO)" },
        { key: "capex", label: "Capital Expenditures (CapEx)" },
        { key: "depreciation_amortization", label: "Depreciation & Amortization" },
        { key: "share_based_comp", label: "Share-based Compensation" },
        { key: "dividends_paid", label: "Dividends Paid" },
        { key: "share_repurchases", label: "Share Repurchases" },
        { key: "fcf", label: "Free Cash Flow (FCF)" },
      ],
    },
    {
      title: "Balance Sheet",
      lines: [
        { key: "assets_total", label: "Total Assets" },
        { key: "liabilities_current", label: "Current Liabilities" },
        { key: "liabilities_longterm", label: "Long-Term Liabilities" },
        { key: "equity_total", label: "Total Equity" },
        { key: "cash_and_sti", label: "Cash & Short-Term Investments" },
        { key: "total_debt", label: "Total Debt" },
        { key: "inventories", label: "Inventories" },
        { key: "accounts_receivable", label: "Accounts Receivable" },
        { key: "accounts_payable", label: "Accounts Payable" },
        {
          key: "shares_outstanding",
          label: "Shares Outstanding",
          fmt: (v?: number | null) =>
            formatNum(v, { notation: "compact", maximumFractionDigits: 0 }),
        },
      ],
    },
  ] as const;

  const { ref: outerRef, w: wrapW } = useContainerWidth<HTMLDivElement>();
  const leftW = Math.round(Math.min(360, Math.max(220, wrapW * 0.22)));
  const yearsCount = rows.length || 1;
  const yearW = Math.round(
    Math.min(160, Math.max(60, (wrapW - leftW) / yearsCount))
  );

  return (
    <div
      ref={outerRef}
      className="w-full max-w-none px-4 md:px-8 lg:px-12 xl:px-16 py-4 space-y-3"
    >
      {/* Back to Screener */}
      <div className="flex items-center justify-between">
        <button className={btn} onClick={() => navigate("/")} aria-label="Back to Screener">
          ← Back to Screener
        </button>
        <div className="flex gap-2">
          {company ? (
            <button
              className={btn}
              onClick={() => navigate(`/companies/${company.ticker}/profile`)}
            >
              Company Profile →
            </button>
          ) : null}
          {company ? (
            <button
              className={btn}
              onClick={() => navigate(`/pharma/${company.ticker}`)}
            >
              Pharma Insights →
            </button>
          ) : null}
        </div>
      </div>

      {/* Toggle Annual / Quarterly */}
      <div className="flex space-x-2 mb-4">
        <button
          className={`${btn} ${mode === "annual" ? "opacity-100" : "opacity-60"}`}
          onClick={() => setMode("annual")}
        >
          Annual
        </button>
        <button
          className={`${btn} ${mode === "quarterly" ? "opacity-100" : "opacity-60"}`}
          onClick={() => setMode("quarterly")}
        >
          Quarterly
        </button>
      </div>

      {/* Company header */}
      {company && (
        <div className="flex flex-col md:flex-row md:items-start md:space-x-6 mb-6">
          <div className="shrink-0">
            <h1 className="text-2xl font-bold">
              {company.name}{" "}
              <span className="text-zinc-500">({company.ticker})</span>
            </h1>
          </div>
          {company.description && (
            <div className="flex-1">
              <p className="text-sm text-zinc-500 leading-relaxed">
                {company.description}
              </p>
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-zinc-500">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="text-sm text-zinc-500">No financials yet.</div>
      ) : (
        <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
          <table className="w-full table-fixed text-[12px]">
            <colgroup>
              <col style={{ width: leftW }} />
              {rows.map((_, idx) => (
                <col key={`col-${idx}`} style={{ width: yearW }} />
              ))}
            </colgroup>

            <thead className="bg-zinc-50 dark:bg-zinc-900/60">
              <tr>
                <th className="text-left font-semibold px-3 py-3 sticky left-0 bg-zinc-50 dark:bg-zinc-900/60 z-10">
                  Line Item
                </th>
                {rows.map((row, idx) => {
                  const label =
                    mode === "quarterly"
                      ? `${row.fiscal_year} ${row.fiscal_period}` // Q1–Q4
                      : `FY ${row.fiscal_year}`; // Annual totals
                  return (
                    <th key={idx} className="text-right font-semibold px-3 py-3">
                      <span className="tabular-nums">{label}</span>
                    </th>
                  );
                })}
              </tr>
            </thead>

            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {sections.map((sec) => (
                <FragmentSection
                  key={sec.title}
                  title={sec.title}
                  lines={sec.lines as any}
                  rows={rows}
                  val={val}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FragmentSection({
  title,
  lines,
  rows,
  val,
}: {
  title: string;
  lines: Array<{
    key: string;
    label: string;
    fmt?: (v?: number | null) => string;
  }>;
  rows: Row[];
  val: (row: Row, k: keyof Row) => number | null | undefined;
}) {
  return (
    <>
      <tr>
        <td
          colSpan={9999}
          className="px-3 py-3 text-[12px] leading-5 uppercase tracking-wide text-zinc-500 bg-zinc-100 dark:bg-zinc-900/70"
        >
          {title}
        </td>
      </tr>
      {lines.map((ln) => (
        <tr key={title + ln.key}>
          <td className="sticky left-0 bg-white dark:bg-zinc-950 px-3 py-2 text-[12px] leading-5 align-middle">
            {ln.label}
          </td>
          {rows.map((row, idx) => {
            const raw = val(row, ln.key as keyof Row);
            const formatted = (ln.fmt ?? formatNum)(raw);
            const isNegative = typeof raw === "number" && raw < 0;
            const extraClass =
              ln.key === "net_income" ? "font-bold border-t border-zinc-400" : "";
            return (
              <td
                key={`${ln.key}-${idx}`}
                className={`px-3 py-2 text-[12px] leading-5 align-middle text-right font-mono tabular-nums whitespace-nowrap ${
                  isNegative ? "text-red-500" : ""
                } ${extraClass}`}
              >
                {formatted}
              </td>
            );
          })}
        </tr>
      ))}
    </>
  );
}

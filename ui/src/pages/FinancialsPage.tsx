// ui/src/pages/FinancialsPage.tsx
import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";

type Row = {
  fiscal_year: number;
  revenue?: number | null;
  gross_profit?: number | null;
  operating_income?: number | null;
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
};

const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const btn =
  "h-8 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900 " +
  "hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

function formatNum(v?: number | null, opts: Intl.NumberFormatOptions = {}) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const fmt = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 2, ...opts });
  return fmt.format(v);
}

export default function FinancialsPage() {
  const { companyId } = useParams<{ companyId: string }>();
  const navigate = useNavigate();

  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!companyId) return;
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API}/financials/${companyId}`);
        const data: Row[] = await r.json();
        if (alive) setRows((data || []).sort((a, b) => a.fiscal_year - b.fiscal_year));
      } catch {
        if (alive) setRows([]);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [companyId]);

  const fiscalYears = useMemo(() => rows.map(r => r.fiscal_year), [rows]);

  // quick access map
  const byYear = useMemo(() => {
    const m = new Map<number, Row>();
    rows.forEach(r => m.set(r.fiscal_year, r));
    return m;
  }, [rows]);

  const val = (y: number, k: keyof Row) => (byYear.get(y) as any)?.[k] as number | null | undefined;

  // derived expenses
  const cogs  = (y: number) => (val(y,"revenue")!=null && val(y,"gross_profit")!=null) ? (val(y,"revenue") as number)-(val(y,"gross_profit") as number) : null;
  const opex  = (y: number) => (val(y,"gross_profit")!=null && val(y,"operating_income")!=null) ? (val(y,"gross_profit") as number)-(val(y,"operating_income") as number) : null;

  const sections = [
    {
      title: "Income Statement",
      lines: [
        { key: "revenue", label: "Revenue", fmt: (v: any)=>formatNum(v) },
        { key: "gross_profit", label: "Gross Profit", fmt: formatNum },
        { key: "cogs", label: "Cost of Revenue (derived)", source: cogs, fmt: formatNum },
        { key: "operating_income", label: "Operating Income", fmt: formatNum },
        { key: "opex", label: "Operating Expenses (derived)", source: opex, fmt: formatNum },
        { key: "net_income", label: "Net Income", fmt: formatNum },
        { key: "eps_diluted", label: "EPS (Diluted, proxy)", fmt: (v:any)=>formatNum(v,{notation:"standard",maximumFractionDigits:2}) },
      ],
    },
    {
      title: "Cash Flow",
      lines: [
        { key: "cfo", label: "Cash From Operations (CFO)", fmt: formatNum },
        { key: "capex", label: "Capital Expenditures (CapEx)", fmt: formatNum },
        { key: "fcf", label: "Free Cash Flow (FCF)", fmt: formatNum },
      ],
    },
    {
      title: "Balance Sheet",
      lines: [
        { key: "assets_total", label: "Total Assets", fmt: formatNum },
        { key: "equity_total", label: "Total Equity", fmt: formatNum },
        { key: "cash_and_sti", label: "Cash & Short-Term Investments", fmt: formatNum },
        { key: "total_debt", label: "Total Debt", fmt: formatNum },
        { key: "shares_outstanding", label: "Shares Outstanding", fmt: (v:any)=>formatNum(v,{notation:"standard",maximumFractionDigits:0}) },
      ],
    },
  ] as const;

  // compact fixed widths to keep all years visible
  const sizeCell = "px-2 py-1 text-[11px] leading-4";
  const sizeHead = "px-2 py-2 text-[11px] leading-4";
  const leftColW = "w-[200px]";
  const yearColW = "w-[64px]";

  return (
    <div className="max-w-6xl mx-auto p-4 space-y-3">
      <div className="flex items-center justify-between">
        <button className={btn} onClick={() => navigate("/")} aria-label="Back to Screener">
          ← Back to Screener
        </button>
      </div>

      {loading ? (
        <div className="text-sm text-zinc-500">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="text-sm text-zinc-500">No financials yet.</div>
      ) : (
        <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
          <table className={`w-full table-fixed text-[11px]`}>
            <thead className="bg-zinc-50 dark:bg-zinc-900/60">
              <tr>
                <th className={`text-left font-semibold sticky left-0 bg-zinc-50 dark:bg-zinc-900/60 z-10 ${sizeHead} ${leftColW}`}>
                  Line Item
                </th>
                {fiscalYears.map((y) => (
                  <th key={y} className={`text-right font-semibold ${sizeHead} ${yearColW}`}>
                    <span className="tabular-nums">{y}</span>
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {sections.map((sec) => (
                <FragmentSection
                  key={sec.title}
                  title={sec.title}
                  lines={sec.lines}
                  fiscalYears={fiscalYears}
                  sizeCell={sizeCell}
                  leftColW={leftColW}
                  yearColW={yearColW}
                  val={val}
                  cogs={cogs}
                  opex={opex}
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
  title, lines, fiscalYears, sizeCell, leftColW, yearColW, val, cogs, opex,
}: {
  title: string;
  lines: Array<any>;
  fiscalYears: number[];
  sizeCell: string;
  leftColW: string;
  yearColW: string;
  val: (y:number,k:any)=>any;
  cogs: (y:number)=>number|null;
  opex: (y:number)=>number|null;
}) {
  return (
    <>
      <tr>
        <td colSpan={9999} className={`px-3 py-2 text-[10px] tracking-wide uppercase text-zinc-500 bg-zinc-100 dark:bg-zinc-900/70 ${leftColW} ${sizeCell}`}>
          {title}
        </td>
      </tr>
      {lines.map((ln:any) => (
        <tr key={String(title + ln.key)}>
          <td className={`sticky left-0 bg-white dark:bg-zinc-950 ${sizeCell}`}>
            {ln.label}
          </td>
          {fiscalYears.map((y) => {
            const raw =
              ln.key === "cogs" ? cogs(y)
              : ln.key === "opex" ? opex(y)
              : val(y, ln.key);
            return (
              <td key={`${ln.key}-${y}`} className={`${sizeCell} ${yearColW} text-right font-mono tabular-nums whitespace-nowrap`}>
                {(ln.fmt ?? formatNum)(raw as number | null | undefined)}
              </td>
            );
          })}
        </tr>
      ))}
    </>
  );
}

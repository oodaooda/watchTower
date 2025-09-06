// ui/src/pages/FinancialsPage.tsx
import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";

type Row = {
  fiscal_year: number;

  // Income Statement
  revenue?: number | null;
  gross_profit?: number | null;
  operating_income?: number | null;
  net_income?: number | null;
  eps_diluted?: number | null;

  // Balance Sheet
  assets_total?: number | null;
  equity_total?: number | null;
  cash_and_sti?: number | null;
  total_debt?: number | null;
  shares_outstanding?: number | null;

  // Cash Flow
  cfo?: number | null;
  capex?: number | null;
  fcf?: number | null;
};

const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const btn =
  "h-9 px-4 rounded-xl font-medium inline-flex items-center justify-center " +
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
        if (alive) setRows(data || []);
      } catch {
        if (alive) setRows([]);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [companyId]);

  const fiscalYears = useMemo(
    () => [...new Set(rows.map((r) => r.fiscal_year))].sort((a, b) => a - b),
    [rows]
  );

  // One combined config: Income Statement + Cash Flow + Balance Sheet
  const sections: Array<{
    title: string;
    lines: Array<{
      key: keyof Row | "eps_diluted_fmt" | "shares_outstanding_fmt";
      label: string;
      fmt?: (v?: number | null) => string;
    }>;
  }> = [
    {
      title: "Income Statement",
      lines: [
        { key: "revenue", label: "Revenue", fmt: (v) => formatNum(v) },
        { key: "gross_profit", label: "Gross Profit", fmt: (v) => formatNum(v) },
        { key: "operating_income", label: "Operating Income", fmt: (v) => formatNum(v) },
        { key: "net_income", label: "Net Income", fmt: (v) => formatNum(v) },
        {
          key: "eps_diluted_fmt",
          label: "EPS (Diluted, proxy)",
          fmt: (v) => formatNum(v, { notation: "standard", maximumFractionDigits: 2 }),
        },
      ],
    },
    {
      title: "Cash Flow",
      lines: [
        { key: "cfo", label: "Cash From Operations (CFO)", fmt: (v) => formatNum(v) },
        { key: "capex", label: "Capital Expenditures (CapEx)", fmt: (v) => formatNum(v) },
        { key: "fcf", label: "Free Cash Flow (FCF)", fmt: (v) => formatNum(v) },
      ],
    },
    {
      title: "Balance Sheet",
      lines: [
        { key: "assets_total", label: "Total Assets", fmt: (v) => formatNum(v) },
        { key: "equity_total", label: "Total Equity", fmt: (v) => formatNum(v) },
        { key: "cash_and_sti", label: "Cash & Short-Term Investments", fmt: (v) => formatNum(v) },
        { key: "total_debt", label: "Total Debt", fmt: (v) => formatNum(v) },
        {
          key: "shares_outstanding_fmt",
          label: "Shares Outstanding",
          fmt: (v) => formatNum(v, { notation: "standard", maximumFractionDigits: 0 }),
        },
      ],
    },
  ];

  return (
    <div className="max-w-6xl mx-auto p-4 space-y-4">
      {/* Back to Screener */}
      <div className="flex items-center justify-between">
        <button
          className={btn}
          onClick={() => navigate("/")}
          aria-label="Back to Screener"
          title="Back to Screener"
        >
          ← Back to Screener
        </button>
      </div>

      {loading ? (
        <div className="text-sm text-zinc-500">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="text-sm text-zinc-500">No financials yet.</div>
      ) : (
        <div className="overflow-auto rounded-2xl border border-zinc-200 dark:border-zinc-800">
          <table className="min-w-full text-sm">
            <thead className="bg-zinc-50 dark:bg-zinc-900/60">
              <tr>
                <th className="text-left px-4 py-3 font-semibold sticky left-0 bg-zinc-50 dark:bg-zinc-900/60 z-10">
                  Line Item
                </th>
                {fiscalYears.map((y) => (
                  <th key={y} className="text-right px-4 py-3 font-semibold">
                    {y}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {sections.map((sec) => (
                <SectionBlock key={sec.title} title={sec.title}>
                  {sec.lines.map((ln) => (
                    <tr key={String(ln.key)}>
                      <td className="px-4 py-2 sticky left-0 bg-white dark:bg-zinc-950">
                        {ln.label}
                      </td>
                      {fiscalYears.map((y) => {
                        const r = rows.find((rr) => rr.fiscal_year === y);
                        const raw =
                          ln.key === "eps_diluted_fmt"
                            ? r?.eps_diluted
                            : ln.key === "shares_outstanding_fmt"
                            ? r?.shares_outstanding
                            : (r as any)?.[ln.key];

                        return (
                          <td key={`${ln.key}-${y}`} className="px-4 py-2 text-right">
                            {(ln.fmt ?? formatNum)(raw as number | null | undefined)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </SectionBlock>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SectionBlock({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <tr>
        <td colSpan={9999} className="px-4 py-2 text-xs tracking-wide uppercase text-zinc-500 bg-zinc-100 dark:bg-zinc-900/70">
          {title}
        </td>
      </tr>
      {children}
    </>
  );
}

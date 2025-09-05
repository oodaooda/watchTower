import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

type ScreenRow = {
  company_id: number;
  ticker: string;
  name: string;
  industry?: string | null;
  fiscal_year: number;
  cash_debt_ratio?: number | null;
  growth_consistency?: number | null;
  rev_cagr_5y?: number | null;
  ni_cagr_5y?: number | null;
  fcf?: number | null;
  fcf_cagr_5y?: number | null;
  pe_ttm?: number | null;
  price?: number | null;
};

const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

function fmtPct(v?: number | null) {
  if (v == null || Number.isNaN(v)) return "—";
  return (v * 100).toFixed(1) + "%";
}
function fmtNum(v?: number | null) {
  if (v == null || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 2 }).format(v);
}

export default function ScreenerPage() {
  const [rows, setRows] = useState<ScreenRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        // simple default screen; tweak params as you like
        const r = await fetch(`${API}/screen?limit=100`);
        const data = await r.json();
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
  }, []);

  const hasData = rows.length > 0;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Screener</h1>

      <div className="overflow-auto rounded-2xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900/60">
            <tr>
              <th className="text-left px-4 py-3 font-semibold">Ticker</th>
              <th className="text-left px-4 py-3 font-semibold">Company</th>
              <th className="text-left px-4 py-3 font-semibold">Industry</th>
              <th className="text-right px-4 py-3 font-semibold">FY</th>
              <th className="text-right px-4 py-3 font-semibold">Price</th>
              <th className="text-right px-4 py-3 font-semibold">P/E (TTM)</th>
              <th className="text-right px-4 py-3 font-semibold">Cash/Debt</th>
              <th className="text-right px-4 py-3 font-semibold">Growth Cons.</th>
              <th className="text-right px-4 py-3 font-semibold">Rev CAGR (5y)</th>
              <th className="text-right px-4 py-3 font-semibold">NI CAGR (5y)</th>
              <th className="text-right px-4 py-3 font-semibold">FCF CAGR (5y)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {loading && (
              <tr><td colSpan={11} className="px-4 py-4 text-zinc-500">Loading…</td></tr>
            )}
            {!loading && !hasData && (
              <tr><td colSpan={11} className="px-4 py-4 text-zinc-500">No results.</td></tr>
            )}
            {!loading && hasData && rows.map((r) => (
              <tr key={`${r.company_id}-${r.fiscal_year}`} className="hover:bg-zinc-50 dark:hover:bg-zinc-900/40">
                <td className="px-4 py-2 font-mono">{r.ticker}</td>
                <td className="px-4 py-2">
                  {/* Company name links to Financials page */}
                  <Link
                    to={`/financials/${r.company_id}`}
                    className="text-sky-700 dark:text-sky-400 hover:underline"
                    title="View Financials"
                  >
                    {r.name}
                  </Link>
                </td>
                <td className="px-4 py-2">{r.industry ?? "—"}</td>
                <td className="px-4 py-2 text-right">{r.fiscal_year}</td>
                <td className="px-4 py-2 text-right">{fmtNum(r.price)}</td>
                <td className="px-4 py-2 text-right">{r.pe_ttm ?? "—"}</td>
                <td className="px-4 py-2 text-right">{r.cash_debt_ratio?.toFixed(2) ?? "—"}</td>
                <td className="px-4 py-2 text-right">{r.growth_consistency ?? "—"}</td>
                <td className="px-4 py-2 text-right">{fmtPct(r.rev_cagr_5y)}</td>
                <td className="px-4 py-2 text-right">{fmtPct(r.ni_cagr_5y)}</td>
                <td className="px-4 py-2 text-right">{fmtPct(r.fcf_cagr_5y)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

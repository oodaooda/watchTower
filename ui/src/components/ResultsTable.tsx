// ui/src/components/ResultsTable.tsx
import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { ScreenRow } from "../lib/api";
import ValuationModal from "./ValuationModal";

// /valuation/summary merge adds these
type RowWithVal = ScreenRow & {
  fair_value_per_share?: number | null;
  upside_vs_price?: number | null;
};

const ND = "—";
const ndash = () => ND;

function fmtPct(x: number | null | undefined) {
  if (x == null) return ND;
  return new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 1 }).format(x);
}
function fmtNum(x: number | null | undefined, d = 3) {
  if (x == null) return ND;
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: d }).format(x);
}
function fmtUSD(x: number | null | undefined) {
  if (x == null) return ND;
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(x);
}
function secUrlForTicker(t: string) {
  return `https://www.sec.gov/edgar/search/#/category=custom&entityName=${encodeURIComponent(t)}`;
}

export default function ResultsTable({
  rows,
  loading,
  filterText,
}: {
  rows: RowWithVal[];
  loading: boolean;
  filterText?: string;
}) {
  const [valTicker, setValTicker] = useState<string | null>(null);

  // client-side filter (ticker or name)
  const q = (filterText ?? "").trim().toUpperCase();
  const filteredRows = useMemo(() => {
    if (!q) return rows;
    return rows.filter(
      (r) =>
        r.ticker.toUpperCase().includes(q) ||
        (r.name ?? "").toUpperCase().includes(q)
    );
  }, [rows, q]);

  const hasData = filteredRows.length > 0;

  return (
    <>
      {/* NOTE: ensure the page/container above uses: w-full max-w-none */}

      <div className="w-full max-w-none px-4 md:px-8 lg:px-12 xl:px-16 py-4">
        <table className="w-full table-auto text-[12px] leading-5">
          <thead className="bg-zinc-50 dark:bg-zinc-900/60">
            <tr className="text-left">
              <th className="py-2.5 px-3 font-semibold">Ticker</th>
              <th className="py-2.5 px-3 font-semibold">Company</th>
              <th className="py-2.5 px-3 font-semibold">Industry</th>
              <th className="py-2.5 px-3 font-semibold text-right">FY</th>

              <th className="py-2.5 px-3 font-semibold text-right">P/E (TTM)</th>
              <th className="py-2.5 px-3 font-semibold text-right">Cash/Debt</th>
              <th className="py-2.5 px-3 font-semibold text-right">Growth Cons.</th>
              <th className="py-2.5 px-3 font-semibold text-right">Rev CAGR (5y)</th>
              <th className="py-2.5 px-3 font-semibold text-right">NI CAGR (5y)</th>
              <th className="py-2.5 px-3 font-semibold text-right">FCF CAGR (5y)</th>

              <th className="py-2.5 px-3 font-semibold text-right">Price</th>
              <th className="py-2.5 px-3 font-semibold text-right">Fair Value</th>
              <th className="py-2.5 px-3 font-semibold text-right">Upside</th>
              <th className="py-2.5 px-3 font-semibold text-right">Valuation</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {loading && (
              <tr>
                <td colSpan={14} className="px-4 py-4 text-zinc-500">
                  Loading…
                </td>
              </tr>
            )}

            {!loading && !hasData && (
              <tr>
                <td colSpan={14} className="px-4 py-4 text-zinc-500">
                  No results.
                </td>
              </tr>
            )}

            {!loading &&
              hasData &&
              filteredRows.map((r) => {
                const industry = (r as any).industry ?? (r as any).industry_name ?? ndash();
                const upClass =
                  r.upside_vs_price == null
                    ? ""
                    : r.upside_vs_price >= 0
                    ? "text-emerald-600"
                    : "text-rose-600";

                return (
                  <tr
                    key={`${r.company_id}-${r.fiscal_year ?? ""}`}
                    className="hover:bg-zinc-900/5 dark:hover:bg-zinc-50/5"
                  >
                    {/* Ticker → SEC */}
                    <td className="py-2 px-3 font-semibold">
                      <a
                        href={secUrlForTicker(r.ticker)}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sky-500 hover:underline"
                        title="Open SEC filings"
                      >
                        {r.ticker}
                      </a>
                    </td>

                    {/* Company → Financials */}
                    <td className="py-2 px-3">
                      <Link
                        to={`/financials/${r.company_id}`}
                        className="text-sky-500 hover:underline"
                        title="View Financials"
                      >
                        {/* truncate keeps long names from forcing scroll */}
                        <span className="truncate inline-block max-w-full" title={r.name}>
                          {r.name}
                        </span>
                      </Link>
                    </td>

                    {/* Industry */}
                    <td className="py-2 px-3">
                      <span className="truncate inline-block max-w-full" title={industry}>
                        {industry}
                      </span>
                    </td>

                    <td className="py-2 px-3 text-right tabular-nums">{r.fiscal_year ?? ND}</td>

                    <td className="py-2 px-3 text-right tabular-nums">{fmtNum(r.pe_ttm, 3)}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{fmtNum(r.cash_debt_ratio, 4)}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{r.growth_consistency ?? ND}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{fmtPct(r.rev_cagr_5y)}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{fmtPct(r.ni_cagr_5y)}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{fmtPct(r.fcf_cagr_5y)}</td>

                    <td className="py-2 px-3 text-right tabular-nums">{fmtUSD(r.price)}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{fmtUSD(r.fair_value_per_share)}</td>
                    <td className={`py-2 px-3 text-right tabular-nums font-medium ${upClass}`}>
                      {fmtPct(r.upside_vs_price)}
                    </td>

                    {/* Valuation action → modal */}
                    <td className="py-2 px-3 text-right">
                      <button
                        type="button"
                        className="text-sky-500 hover:underline"
                        onClick={() => setValTicker(r.ticker)}
                      >
                        Valuation
                      </button>
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>

      {/* DCF modal */}
      {valTicker && (
        <ValuationModal ticker={valTicker} onClose={() => setValTicker(null)} />
      )}
    </>
  );
}

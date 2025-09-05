// ui/src/components/ResultsTable.tsx
import React, { useState } from "react";
import { Link } from "react-router-dom";
import type { ScreenRow } from "../lib/api"; // keep your original import
import ValuationModal from "./ValuationModal";

// ---- Extended row: your /valuation/summary merge adds these ----
type RowWithVal = ScreenRow & {
  fair_value_per_share?: number | null;
  upside_vs_price?: number | null;
};

// ---- Formatters ------------------------------------------------------------
const ND = "—";
const ndash = () => ND;

function fmtPct(x: number | null | undefined) {
  if (x == null) return ND;
  return `${(x * 100).toFixed(1)}%`;
}
function fmtNum(x: number | null | undefined, d = 4) {
  if (x == null) return ND;
  return x.toFixed(d);
}
function fmtUSD(x: number | null | undefined, d = 2) {
  if (x == null) return ND;
  return `$${x.toFixed(d)}`;
}
function secUrlForTicker(t: string) {
  return `https://www.sec.gov/edgar/search/#/category=custom&entityName=${encodeURIComponent(
    t
  )}`;
}

// ---- Component -------------------------------------------------------------
export default function ResultsTable({
  rows,
  loading,
  filterText, // NEW: client-side filter text
}: {
  rows: RowWithVal[];
  loading: boolean;
  filterText?: string;
}) {
  const [valTicker, setValTicker] = useState<string | null>(null);

  // Client-side search filter (by ticker or company name)
  const q = (filterText ?? "").trim().toUpperCase();
  const filteredRows =
    q.length > 0
      ? rows.filter(
          (r) =>
            r.ticker.toUpperCase().includes(q) ||
            (r.name ?? "").toUpperCase().includes(q)
        )
      : rows;

  const hasData = filteredRows.length > 0;

  return (
    <>
      <div className="mt-6 overflow-x-auto rounded-2xl border border-zinc-800">
        <table className="min-w-full text-[13px] md:text-sm whitespace-nowrap">
          <thead>
            <tr className="text-left border-b border-zinc-800 bg-zinc-900/40 text-[12.5px] md:text-sm">
              <th className="py-2 px-4">Ticker</th>
              <th className="py-2 px-4">Company</th>
              <th className="py-2 px-4">Industry</th>
              <th className="py-2 px-4">FY</th>

              <th className="py-2 px-4 text-right">P/E (TTM)</th>
              <th className="py-2 px-4 text-right">Cash/Debt</th>
              <th className="py-2 px-4 text-right">Growth Cons.</th>
              <th className="py-2 px-4 text-right">Rev CAGR (5y)</th>
              <th className="py-2 px-4 text-right">NI CAGR (5y)</th>
              <th className="py-2 px-4 text-right">FCF CAGR (5y)</th>

              <th className="py-2 px-4 text-right">Price</th>
              <th className="py-2 px-4 text-right">Fair Value</th>
              <th className="py-2 px-4 text-right">Upside</th>
              <th className="py-2 px-4 text-right">Valuation</th>
            </tr>
          </thead>

          <tbody>
            {loading && (
              <tr>
                <td colSpan={14} className="px-4 py-4 text-zinc-400">
                  Loading…
                </td>
              </tr>
            )}

            {!loading && !hasData && (
              <tr>
                <td colSpan={14} className="px-4 py-4 text-zinc-400">
                  No results.
                </td>
              </tr>
            )}

            {!loading &&
              hasData &&
              filteredRows.map((r) => {
                const upsideClass =
                  r.upside_vs_price == null
                    ? ""
                    : r.upside_vs_price >= 0
                    ? "text-emerald-500"
                    : "text-rose-500";

                return (
                  <tr
                    key={`${r.company_id}-${r.fiscal_year}`}
                    className="border-b border-zinc-800 hover:bg-zinc-800/40"
                  >
                    {/* Ticker → SEC */}
                    <td className="py-2 px-4 font-semibold">
                      <a
                        href={secUrlForTicker(r.ticker)}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sky-400 hover:underline"
                        title="Open SEC filings"
                      >
                        {r.ticker}
                      </a>
                    </td>

                    {/* Company → Financials */}
                    <td className="py-2 px-4">
                      <Link
                        to={`/financials/${r.company_id}`}
                        className="text-sky-400 hover:underline"
                        title="View Financials"
                      >
                        {r.name}
                      </Link>
                    </td>

                    <td className="py-2 px-4">{r.industry ?? ndash()}</td>
                    <td className="py-2 px-4">{r.fiscal_year}</td>

                    <td className="py-2 px-4 text-right">
                      {fmtNum(r.pe_ttm, 4)}
                    </td>
                    <td className="py-2 px-4 text-right">
                      {fmtNum(r.cash_debt_ratio, 4)}
                    </td>
                    <td className="py-2 px-4 text-right">
                      {r.growth_consistency ?? ndash()}
                    </td>
                    <td className="py-2 px-4 text-right">
                      {fmtPct(r.rev_cagr_5y)}
                    </td>
                    <td className="py-2 px-4 text-right">
                      {fmtPct(r.ni_cagr_5y)}
                    </td>
                    <td className="py-2 px-4 text-right">
                      {fmtPct(r.fcf_cagr_5y)}
                    </td>

                    {/* Price / FV / Upside (from /valuation/summary merge) */}
                    <td className="py-2 px-4 text-right">{fmtUSD(r.price)}</td>
                    <td className="py-2 px-4 text-right">
                      {fmtUSD(r.fair_value_per_share)}
                    </td>
                    <td className={`py-2 px-4 text-right font-medium ${upsideClass}`}>
                      {fmtPct(r.upside_vs_price)}
                    </td>

                    {/* Valuation action → modal */}
                    <td className="py-2 px-4 text-right">
                      <button
                        type="button"
                        className="text-sky-400 hover:underline"
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

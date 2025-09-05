// ui/src/components/ResultsTable.tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import type { ScreenRow } from "../types";
import ValuationModal from "./ValuationModal";

type RowWithVal = ScreenRow & {
  fair_value_per_share?: number | null;
  upside_vs_price?: number | null;
};

function fmtPct(v?: number | null) {
  if (v == null || Number.isNaN(v)) return "—";
  return (v * 100).toFixed(1) + "%";
}
function fmtNum(v?: number | null) {
  if (v == null || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat(undefined, {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(v);
}

export default function ResultsTable({
  rows,
  loading,
}: {
  rows: RowWithVal[];
  loading: boolean;
}) {
  const [openTicker, setOpenTicker] = useState<string | null>(null);
  const hasData = rows.length > 0;

  return (
    <>
      <div className="overflow-auto rounded-2xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900/60">
            <tr>
              <th className="text-left px-4 py-3 font-semibold">Ticker</th>
              <th className="text-left px-4 py-3 font-semibold">Company</th>
              <th className="text-left px-4 py-3 font-semibold">Industry</th>
              <th className="text-right px-4 py-3 font-semibold">FY</th>
              <th className="text-right px-4 py-3 font-semibold">Price</th>
              {/* Restored valuation summary columns */}
              <th className="text-right px-4 py-3 font-semibold">Fair Value</th>
              <th className="text-right px-4 py-3 font-semibold">Upside</th>
              <th className="text-right px-4 py-3 font-semibold">P/E (TTM)</th>
              <th className="text-right px-4 py-3 font-semibold">Cash/Debt</th>
              <th className="text-right px-4 py-3 font-semibold">Growth Cons.</th>
              <th className="text-right px-4 py-3 font-semibold">Rev CAGR (5y)</th>
              <th className="text-right px-4 py-3 font-semibold">NI CAGR (5y)</th>
              <th className="text-right px-4 py-3 font-semibold">FCF CAGR (5y)</th>
              <th className="text-right px-4 py-3 font-semibold">Valuation</th>
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
              rows.map((r) => {
                const secUrl = `https://www.sec.gov/edgar/search/#/q=${encodeURIComponent(
                  r.ticker
                )}`;
                return (
                  <tr
                    key={`${r.company_id}-${r.fiscal_year}`}
                    className="hover:bg-zinc-50 dark:hover:bg-zinc-900/40"
                  >
                    {/* Ticker → SEC */}
                    <td className="px-4 py-2 font-mono">
                      <a
                        href={secUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sky-700 dark:text-sky-400 hover:underline"
                        title="Open SEC filings"
                      >
                        {r.ticker}
                      </a>
                    </td>

                    {/* Company → Financials */}
                    <td className="px-4 py-2">
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

                    {/* Restored Fair Value / Upside (from /valuation/summary merge in App.tsx) */}
                    <td className="px-4 py-2 text-right">
                      {fmtNum(r.fair_value_per_share)}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {fmtPct(r.upside_vs_price ?? null)}
                    </td>

                    <td className="px-4 py-2 text-right">{r.pe_ttm ?? "—"}</td>
                    <td className="px-4 py-2 text-right">
                      {r.cash_debt_ratio?.toFixed(2) ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {r.growth_consistency ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {fmtPct(r.rev_cagr_5y)}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {fmtPct(r.ni_cagr_5y)}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {fmtPct(r.fcf_cagr_5y)}
                    </td>

                    {/* Valuation modal trigger (uses your existing ValuationModal) */}
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => setOpenTicker(r.ticker)}
                        className="text-sky-700 dark:text-sky-400 hover:underline"
                        title="Open DCF"
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

      {/* Your existing DCF modal */}
      {openTicker && (
        <ValuationModal
          ticker={openTicker}
          onClose={() => setOpenTicker(null)}
        />
      )}
    </>
  );
}

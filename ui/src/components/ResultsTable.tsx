// ui/src/components/ResultsTable.tsx
import React, { useState } from "react";
import type { ScreenRow } from "../lib/api"; // or from "../types" if that's where ScreenRow lives
import ValuationModal from "./ValuationModal";

// ---- Formatters ------------------------------------------------------------
function fmtPct(x: number | null | undefined) {
  if (x == null) return "—";
  return `${(x * 100).toFixed(1)}%`;
}
function fmtBn(x: number | null | undefined) {
  if (x == null) return "—";
  return (x / 1e9).toFixed(2);
}
function fmtNum(x: number | null | undefined, d = 4) {
  if (x == null) return "—";
  return x.toFixed(d);
}
function fmtUSD(x: number | null | undefined, d = 2) {
  if (x == null) return "—";
  return `$${x.toFixed(d)}`;
}
function secUrlForTicker(t: string) {
  return `https://www.sec.gov/edgar/search/#/category=custom&entityName=${encodeURIComponent(
    t
  )}`;
}

// ---- Component -------------------------------------------------------------
export default function ResultsTable({ rows }: { rows: ScreenRow[] }) {
  const [valTicker, setValTicker] = useState<string | null>(null);

  return (
    <>
      <div className="mt-6 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left border-b border-zinc-800">
              <th className="py-2 pr-4">Ticker</th>
              <th className="py-2 pr-4">Name</th>
              <th className="py-2 pr-4">Industry</th>
              <th className="py-2 pr-4">Year</th>
              <th className="py-2 pr-4">Cash/Debt</th>
              <th className="py-2 pr-4">Growth Consistency</th>
              <th className="py-2 pr-4">Rev CAGR 5y</th>
              <th className="py-2 pr-4">NI CAGR 5y</th>
              <th className="py-2 pr-4">FCF (bn)</th>
              <th className="py-2 pr-4">FCF CAGR 5y</th>
              {/* NEW valuation columns (now taken directly from each row) */}
              <th className="py-2 pr-4">Price</th>
              <th className="py-2 pr-4">Fair Value / Share</th>
              <th className="py-2 pr-2">Upside</th>
              <th className="py-2 pl-2">P/E</th>
              <th className="py-2 pl-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
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
                  <td className="py-2 pr-4 font-semibold">
                    <a
                      href={secUrlForTicker(r.ticker)}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blue-400 hover:underline"
                    >
                      {r.ticker}
                    </a>
                  </td>
                  <td className="py-2 pr-4">{r.name}</td>
                  <td className="py-2 pr-4">{r.industry ?? "—"}</td>
                  <td className="py-2 pr-4">{r.fiscal_year}</td>
                  <td className="py-2 pr-4">{fmtNum(r.cash_debt_ratio, 4)}</td>
                  <td className="py-2 pr-4">{r.growth_consistency ?? "—"}</td>
                  <td className="py-2 pr-4">{fmtPct(r.rev_cagr_5y)}</td>
                  <td className="py-2 pr-4">{fmtPct(r.ni_cagr_5y)}</td>
                  <td className="py-2 pr-4">{fmtBn(r.fcf)}</td>
                  <td className="py-2 pr-4">{fmtPct(r.fcf_cagr_5y)}</td>

                  {/* Price / FV / Upside now come straight from the row */}
                  <td className="py-2 pr-4">{fmtUSD(r.price)}</td>
                  <td className="py-2 pr-4">{fmtUSD(r.fair_value_per_share)}</td>
                  <td className={`py-2 pr-2 font-medium ${upsideClass}`}>
                    {fmtPct(r.upside_vs_price)}
                  </td>

                  <td className="py-2 pl-2">
                    {r.pe_ttm != null ? r.pe_ttm.toFixed(4) : "—"}
                  </td>
                  <td className="py-2 pl-4">
                    <button
                      type="button"
                      className="text-blue-400 hover:underline"
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

      {/* Modal (runs the full DCF on demand for the clicked ticker) */}
      {valTicker && (
        <ValuationModal ticker={valTicker} onClose={() => setValTicker(null)} />
      )}
    </>
  );
}

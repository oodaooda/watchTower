// ui/src/components/ResultsTable.tsx
import React, { useEffect, useState } from "react";
import type { ScreenRow, DCFResponse } from "../lib/api";
import { fetchDCF } from "../lib/api";
import ValuationModal from "./ValuationModal";

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
function secUrlForTicker(t: string) {
  return `https://www.sec.gov/edgar/search/#/category=custom&entityName=${encodeURIComponent(t)}`;
}

type ValMap = Record<
  string,
  { loading: boolean; data?: DCFResponse; error?: string }
>;

export default function ResultsTable({ rows }: { rows: ScreenRow[] }) {
  const [vals, setVals] = useState<ValMap>({});
  const [valTicker, setValTicker] = useState<string | null>(null);

  // Hydrate valuation data per visible row
  useEffect(() => {
    let cancelled = false;
    const tickers = rows.map((r) => r.ticker);

    // prune old cache entries
    setVals((prev) => {
      const next: ValMap = {};
      for (const t of tickers) if (prev[t]) next[t] = prev[t];
      return next;
    });

    (async () => {
      for (const t of tickers) {
        if (cancelled) break;
        if (vals[t]?.data || vals[t]?.loading) continue;

        setVals((prev) => ({ ...prev, [t]: { loading: true } }));
        try {
          const d = await fetchDCF({ ticker: t }); // server defaults
          if (!cancelled)
            setVals((prev) => ({ ...prev, [t]: { loading: false, data: d } }));
        } catch (e: any) {
          if (!cancelled)
            setVals((prev) => ({
              ...prev,
              [t]: { loading: false, error: e?.message ?? "error" },
            }));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows]);

  const getVal = (t: string) => vals[t]?.data;

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
              {/* NEW valuation columns */}
              <th className="py-2 pr-4">Price</th>
              <th className="py-2 pr-4">Fair Value / Share</th>
              <th className="py-2 pr-2">Upside</th>
              <th className="py-2 pl-2">P/E</th>
              <th className="py-2 pl-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const v = getVal(r.ticker);
              const upsideClass =
                v?.upside_vs_price == null
                  ? ""
                  : v.upside_vs_price >= 0
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

                  {/* Price / FV / Upside from valuation */}
                  <td className="py-2 pr-4">
                    {v?.price != null ? `$${v.price.toFixed(2)}` : "—"}
                  </td>
                  <td className="py-2 pr-4">
                    {v?.fair_value_per_share != null
                      ? `$${v.fair_value_per_share.toFixed(2)}`
                      : "—"}
                  </td>
                  <td className={`py-2 pr-2 font-medium ${upsideClass}`}>
                    {v?.upside_vs_price != null
                      ? `${(v.upside_vs_price * 100).toFixed(1)}%`
                      : "—"}
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

      {/* Modal */}
      {valTicker && (
        <ValuationModal
          ticker={valTicker}
          onClose={() => setValTicker(null)}
        />
      )}
    </>
  );
}

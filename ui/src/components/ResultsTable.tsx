// ui/src/components/ResultsTable.tsx
import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { ScreenRow } from "../lib/api";
import ValuationModal from "./ValuationModal";

export type SortKey =
  | "ticker" | "name" | "industry" | "fiscal_year"
  | "pe_ttm" | "cash_debt_ratio" | "growth_consistency"
  | "rev_cagr_5y" | "ni_cagr_5y" | "fcf_cagr_5y" | "price";

export type SortDir = "asc" | "desc";

type RowWithVal = ScreenRow & {
  fair_value_per_share?: number | null;
  upside_vs_price?: number | null;
};

const ND = "—";

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

function Header({
  label, k, activeKey, dir, onSort, numeric,
}: {
  label: string; k: SortKey; activeKey: SortKey; dir: SortDir;
  onSort: (k: SortKey) => void; numeric?: boolean;
}) {
  const isActive = activeKey === k;
  const arrow = !isActive ? "↕" : dir === "asc" ? "▲" : "▼";
  return (
    <th className={`py-2.5 px-3 font-semibold ${numeric ? "text-right" : "text-left"}`}>
      <button
        type="button"
        onClick={() => onSort(k)}
        className="inline-flex items-center gap-1 hover:underline select-none"
        aria-sort={isActive ? (dir === "asc" ? "ascending" : "descending") : "none"}
        title={`Sort by ${label}`}
      >
        <span>{label}</span>
        <span className={`text-xs ${isActive ? "opacity-100" : "opacity-50"}`}>{arrow}</span>
      </button>
    </th>
  );
}

export default function ResultsTable({
  rows,
  loading,
  filterText,
  sortKey,
  sortDir,
  onRequestSort,
}: {
  rows: RowWithVal[];
  loading: boolean;
  filterText?: string;
  sortKey: SortKey;
  sortDir: SortDir;
  onRequestSort: (k: SortKey) => void;
}) {
  const [valTicker, setValTicker] = useState<string | null>(null);

  // client-side text filter only (no sort here!)
  const q = (filterText ?? "").trim().toUpperCase();
  const filtered = useMemo(() => {
    if (!q) return rows;
    return rows.filter((r) =>
      r.ticker.toUpperCase().includes(q) || (r.name ?? "").toUpperCase().includes(q)
    );
  }, [rows, q]);

  const hasData = filtered.length > 0;

  return (
    <>
      <div className="mt-6 w-full rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <table className="w-full table-auto text-[12px] leading-5">
          <thead className="bg-zinc-50 dark:bg-zinc-900/60">
            <tr>
              <Header label="Ticker" k="ticker" activeKey={sortKey} dir={sortDir} onSort={onRequestSort} />
              <Header label="Company" k="name" activeKey={sortKey} dir={sortDir} onSort={onRequestSort} />
              
              <Header label="FY" k="fiscal_year" activeKey={sortKey} dir={sortDir} onSort={onRequestSort} numeric />
              <Header label="P/E (TTM)" k="pe_ttm" activeKey={sortKey} dir={sortDir} onSort={onRequestSort} numeric />
              <Header label="Cash/Debt" k="cash_debt_ratio" activeKey={sortKey} dir={sortDir} onSort={onRequestSort} numeric />
              <Header label="Growth Cons." k="growth_consistency" activeKey={sortKey} dir={sortDir} onSort={onRequestSort} numeric />
              <Header label="Rev CAGR (5y)" k="rev_cagr_5y" activeKey={sortKey} dir={sortDir} onSort={onRequestSort} numeric />
              <Header label="NI CAGR (5y)" k="ni_cagr_5y" activeKey={sortKey} dir={sortDir} onSort={onRequestSort} numeric />
              <Header label="FCF CAGR (5y)" k="fcf_cagr_5y" activeKey={sortKey} dir={sortDir} onSort={onRequestSort} numeric />
              <Header label="Price" k="price" activeKey={sortKey} dir={sortDir} onSort={onRequestSort} numeric />
              <th className="py-2.5 px-3 font-semibold text-right">Fair Value</th>
              <th className="py-2.5 px-3 font-semibold text-right">Upside</th>
              <th className="py-2.5 px-3 font-semibold text-right">Valuation</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {loading && (
              <tr><td colSpan={14} className="px-4 py-4 text-zinc-500">Loading…</td></tr>
            )}
            {!loading && !hasData && (
              <tr><td colSpan={14} className="px-4 py-4 text-zinc-500">No results.</td></tr>
            )}
            {!loading && hasData && filtered.map((r) => {
              const industry = (r as any).industry ?? (r as any).industry_name ?? ND;
              const upClass =
                r.upside_vs_price == null ? "" : r.upside_vs_price >= 0 ? "text-emerald-600" : "text-rose-600";
              return (
                <tr key={`${r.company_id}-${r.fiscal_year ?? ""}`} className="hover:bg-zinc-900/5 dark:hover:bg-zinc-50/5">
                  <td className="py-2 px-3 font-semibold">
                    <a href={secUrlForTicker(r.ticker)} target="_blank" rel="noreferrer"
                       className="text-sky-500 hover:underline" title="Open SEC filings">
                      {r.ticker}
                    </a>
                  </td>
                  <td className="py-2 px-3">
                    <Link to={`/financials/${r.company_id}`} className="text-sky-500 hover:underline" title="View Financials">
                      <span className="truncate inline-block max-w-full" title={r.name}>{r.name}</span>
                    </Link>
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
                  <td className={`py-2 px-3 text-right tabular-nums font-medium ${upClass}`}>{fmtPct(r.upside_vs_price)}</td>
                  <td className="py-2 px-3 text-right">
                    <button type="button" className="text-sky-500 hover:underline" onClick={() => setValTicker(r.ticker)}>
                      Valuation
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {valTicker && <ValuationModal ticker={valTicker} onClose={() => setValTicker(null)} />}
    </>
  );
}

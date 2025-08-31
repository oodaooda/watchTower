// ui/src/components/ValuationModal.tsx
import React, { useEffect, useState } from "react";
import { fetchDCF, type DCFResponse } from "../lib/api";

export default function ValuationModal({
  ticker,
  onClose,
}: {
  ticker: string;
  onClose: () => void;
}) {
  // inputs
  const [years, setYears] = useState(10);
  const [dr, setDr] = useState(0.1);
  const [g0, setG0] = useState<number | undefined>(undefined);
  const [gt, setGt] = useState(0.025);

  const [data, setData] = useState<DCFResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run() {
    try {
      setLoading(true);
      setErr(null);
      const out = await fetchDCF({
        ticker,
        years,
        discount_rate: dr,
        start_growth: g0,
        terminal_growth: gt,
      });
      if (g0 == null) setG0(out.inputs?.start_growth ?? g0);
      // Keep using your original top-level fields for rendering:
      setData(out);
    } catch (e: any) {
      setErr(e?.message ?? "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 sm:p-6 md:p-10"
      role="dialog"
      aria-modal="true"
    >
      {/* overlay */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* sheet */}
      <div className="relative w-full max-w-3xl rounded-2xl bg-white text-gray-900 shadow-xl dark:bg-gray-900 dark:text-gray-100 dark:shadow-black/30">
        {/* header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-gray-700">
          <h2 className="text-lg font-semibold">DCF — {ticker}</h2>
          <button
            className="rounded px-2 py-1 text-sm text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-gray-800 dark:hover:text-white"
            onClick={onClose}
          >
            Close
          </button>
        </div>

        {/* content */}
        <div className="px-5 py-4">
          {/* controls */}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 mb-4">
            <LabeledInput
              label="Years"
              value={years}
              onChange={(v) => setYears(v)}
              min={3}
              max={20}
            />
            <LabeledInput
              label="Discount rate"
              value={dr}
              onChange={(v) => setDr(v)}
              step={0.005}
            />
            <LabeledInput
              label="Start growth"
              value={g0 ?? NaN}
              onChange={(v) => setG0(Number.isNaN(v) ? undefined : v)}
              step={0.005}
              placeholder="auto"
              allowEmpty
            />
            <LabeledInput
              label="Terminal growth"
              value={gt}
              onChange={(v) => setGt(v)}
              step={0.001}
            />
          </div>

          <div className="mb-4">
            <button
              className="rounded-md bg-gray-900 px-3 py-1.5 text-white hover:bg-black disabled:opacity-60 dark:bg-blue-600 dark:hover:bg-blue-500"
              onClick={run}
              disabled={loading}
            >
              {loading ? "Computing…" : "Recalculate"}
            </button>
          </div>

          {err && (
            <div className="mb-3 text-sm text-red-600 dark:text-red-400">
              {err}
            </div>
          )}

          {data && (
            <div className="space-y-4">
              {/* headline stats */}
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat
                  label="Base FCF"
                  value={`$${(data.base_fcf / 1e9).toFixed(2)} bn`}
                />
                <Stat
                  label="Enterprise Value"
                  value={`$${(data.enterprise_value / 1e9).toFixed(2)} bn`}
                />
                <Stat
                  label="Equity Value"
                  value={`$${(data.equity_value / 1e9).toFixed(2)} bn`}
                />
                <Stat
                  label="Fair Value / Share"
                  value={
                    data.fair_value_per_share != null
                      ? `$${data.fair_value_per_share.toFixed(2)}`
                      : "—"
                  }
                />
              </div>

              {/* price / fair value / upside */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Card label="Price" value={data.price != null ? `$${data.price.toFixed(2)}` : "—"} />
                <Card
                  label="Fair Value / Share"
                  value={
                    data.fair_value_per_share != null
                      ? `$${data.fair_value_per_share.toFixed(2)}`
                      : "—"
                  }
                />
                <Card
                  label="Upside vs Price"
                  value={
                    data.upside_vs_price != null
                      ? `${(data.upside_vs_price * 100).toFixed(1)}%`
                      : "—"
                  }
                  valueClass={
                    data.upside_vs_price != null && data.upside_vs_price >= 0
                      ? "text-emerald-600"
                      : "text-rose-600"
                  }
                />
              </div>

              {/* table */}
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left border-b border-gray-200 dark:border-gray-700">
                      <th className="py-2 pr-3">Year</th>
                      <th className="py-2 pr-3">FCF</th>
                      <th className="py-2 pr-3">Growth</th>
                      <th className="py-2 pr-3">PV of FCF</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.projections.map((row) => (
                      <tr
                        key={row.year}
                        className="border-b border-gray-200 dark:border-gray-700 odd:bg-gray-50 dark:odd:bg-gray-800/40"
                      >
                        <td className="py-2 pr-3">{row.year}</td>
                        <td className="py-2 pr-3">${(row.fcf / 1e9).toFixed(2)} bn</td>
                        <td className="py-2 pr-3">{(row.growth * 100).toFixed(1)}%</td>
                        <td className="py-2 pr-3">${(row.pv_fcf / 1e9).toFixed(2)} bn</td>
                      </tr>
                    ))}
                    <tr className="font-semibold">
                      <td className="py-2 pr-3">Terminal (PV)</td>
                      <td className="py-2 pr-3">—</td>
                      <td className="py-2 pr-3">—</td>
                      <td className="py-2 pr-3">
                        ${ (data.terminal_value_pv / 1e9).toFixed(2) } bn
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function LabeledInput({
  label,
  value,
  onChange,
  step,
  min,
  max,
  placeholder,
  allowEmpty = false,
}: {
  label: string;
  value: number; // can be NaN if allowEmpty
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
  placeholder?: string;
  allowEmpty?: boolean;
}) {
  const str = Number.isNaN(value) && allowEmpty ? "" : String(value);
  return (
    <label className="text-sm">
      <span className="mb-1 block text-gray-600 dark:text-gray-300">{label}</span>
      <input
        type="number"
        value={str}
        step={step}
        min={min}
        max={max}
        placeholder={placeholder}
        onChange={(e) =>
          onChange(e.target.value === "" && allowEmpty ? NaN : Number(e.target.value))
        }
        className="w-full rounded-md border border-gray-200 bg-white px-2 py-1 text-gray-900 placeholder-gray-400 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500/40 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 dark:placeholder-gray-500 dark:focus:ring-blue-400/40"
      />
    </label>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800">
      <div className="text-xs text-gray-600 dark:text-gray-300">{label}</div>
      <div className="text-base font-semibold">{value}</div>
    </div>
  );
}

function Card({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-2xl border border-gray-200 p-3 dark:border-gray-700">
      <div className="text-xs text-gray-600 dark:text-gray-300">{label}</div>
      <div className={`text-xl font-semibold ${valueClass ?? ""}`}>{value}</div>
    </div>
  );
}

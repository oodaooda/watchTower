import { useEffect, useState } from "react";
import FilterBar from "./components/FilterBar";
import ResultsTable from "./components/ResultsTable";
import { fetchScreen } from "./lib/api";
import { ScreenRow } from "./types";
import ThemeToggle from "./components/ThemeToggle";

/** Minimal screener page: filter bar + results grid. */
export default function App() {
  const [rows, setRows] = useState<ScreenRow[]>([]);
  const [loading, setLoading] = useState(false);

  async function run(params: any) {
    setLoading(true);
    try {
      const data = await fetchScreen({ limit: 100, ...params });
      setRows(data as ScreenRow[]);
    } finally {
      setLoading(false);
    }
  }

  // initial run (same defaults you’ve been curling)
  useEffect(() => {
    run({ cash_debt_min: 0.8, growth_consistency_min: 7 });
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-100">
      <div className="max-w-6xl mx-auto p-4">
        <div className="flex items-center gap-3 mb-4">
          <h1 className="text-2xl font-bold">watchTower — Screener</h1>
          <ThemeToggle />
        </div>
      <FilterBar onRun={run} />
      <ResultsTable rows={rows} loading={loading} />
    </div>
  </div>
  );
}

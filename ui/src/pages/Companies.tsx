// ui/src/pages/Companies.tsx
import { useEffect, useMemo, useState } from "react";

type CompanyItem = {
  id: number;
  ticker: string;
  name: string;
  industry?: string | null;
  sic?: string | null;
};
type CompaniesResponse = {
  page: number;
  page_size: number;
  total: number;
  items: CompanyItem[];
};
type Industry = { industry: string; count: number };

const API_BASE =
  (import.meta as any).env.VITE_API_BASE ??
  (import.meta as any).env.VITE_API_BASE_URL ??
  "http://localhost:8000";

function useDebounced<T>(value: T, delay = 400) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return v;
}

export default function CompaniesPage() {
  const [q, setQ] = useState("");
  const [industry, setIndustry] = useState("");
  const [sic, setSic] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);

  const [data, setData] = useState<CompaniesResponse | null>(null);
  const [industries, setIndustries] = useState<Industry[]>([]);
  const [loading, setLoading] = useState(false);

  const dq = useDebounced(q, 400);

  useEffect(() => {
    fetch(`${API_BASE}/industries`)
      .then((r) => r.json())
      .then((rows: Industry[]) => setIndustries(rows))
      .catch(() => setIndustries([]));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    if (dq) params.set("q", dq);
    if (industry) params.set("industry", industry);
    if (sic) params.set("sic", sic);

    setLoading(true);
    fetch(`${API_BASE}/companies?${params.toString()}`)
      .then((r) => r.json())
      .then((json: CompaniesResponse) => setData(json))
      .catch(() => setData({ page: 1, page_size: pageSize, total: 0, items: [] }))
      .finally(() => setLoading(false));
  }, [dq, industry, sic, page, pageSize]);

  useEffect(() => setPage(1), [dq, industry, sic]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil((data?.total ?? 0) / (data?.page_size ?? pageSize))),
    [data, pageSize]
  );

  const secLink = (t: string) =>
    `https://www.sec.gov/edgar/search/#/category=company&entityName=${encodeURIComponent(t)}`;

  return (
    <div className="w-full max-w-none px-4 md:px-8 lg:px-12 xl:px-16 py-4">
      <h1 className="text-2xl font-semibold">Companies</h1>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search ticker or name…"
          className="w-full rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2 focus:outline-none focus:ring"
        />
        <select
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          className="w-full rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2"
        >
          <option value="">All industries</option>
          {industries.map((i) => (
            <option key={i.industry} value={i.industry}>
              {i.industry} ({i.count})
            </option>
          ))}
        </select>
        <input
          value={sic}
          onChange={(e) => setSic(e.target.value)}
          placeholder="SIC (exact)"
          className="w-full rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2"
        />
        <div className="flex items-center justify-end gap-2 text-sm text-zinc-400">
          <span>Total: {data?.total ?? 0}</span>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-zinc-800">
        <table className="w-full table-auto text-[12px] leading-5">
          <thead className="bg-zinc-900/60">
            <tr>
              <th className="px-3 py-2 text-left">Ticker</th>
              <th className="px-3 py-2 text-left">Name</th>
              <th className="px-3 py-2 text-left">Industry</th>
              <th className="px-3 py-2 text-left">SIC</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {loading ? (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-zinc-400">
                  Loading…
                </td>
              </tr>
            ) : (data?.items ?? []).length === 0 ? (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-zinc-400">
                  No results.
                </td>
              </tr>
            ) : (
              data!.items.map((c) => (
                <tr key={c.id} className="hover:bg-zinc-900/40">
                  <td className="px-3 py-2">
                    <a
                      href={secLink(c.ticker)}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blue-400 hover:underline"
                      title="Open on SEC EDGAR"
                    >
                      {c.ticker}
                    </a>
                  </td>
                  <td className="px-3 py-2">{c.name}</td>
                  <td className="px-3 py-2">{c.industry ?? "—"}</td>
                  <td className="px-3 py-2">{c.sic ?? "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <button
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          className="rounded-xl border border-zinc-700 px-4 py-2 disabled:opacity-50"
        >
          Prev
        </button>
        <div className="text-sm text-zinc-400">
          Page {data?.page ?? 1} / {totalPages}
        </div>
        <button
          disabled={page >= totalPages}
          onClick={() => setPage((p) => p + 1)}
          className="rounded-xl border border-zinc-700 px-4 py-2 disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}

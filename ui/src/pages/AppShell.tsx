import { Link, Outlet } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";

export default function AppShell() {
  return (
    <div className="min-h-screen bg-white text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <div className="mx-auto w-full max-w-[1800px] px-4 md:px-6 lg:px-8 py-4">
        <div className="flex items-center gap-3 mb-4">
          <Link to="/" className="text-2xl font-bold hover:opacity-80">
            watchTower — Screener
          </Link>
          <Link
            to="/companies"
            className="rounded-xl border border-zinc-700 px-3 py-1.5 hover:bg-zinc-900/40"
          >
            Companies
          </Link>
          <Link
            to="/universe"
            className="rounded-xl border border-zinc-700 px-3 py-1.5 hover:bg-zinc-900/40"
          >
            Universe
          </Link>
          <Link
            to="/favorites"
            className="rounded-xl border border-zinc-700 px-3 py-1.5 hover:bg-zinc-900/40"
          >
            Favorites
          </Link>
          <Link
            to="/finance-university"
            className="rounded-xl border border-zinc-700 px-3 py-1.5 hover:bg-zinc-900/40"
          >
            Finance University
          </Link>
          <ThemeToggle />
        </div>

        {/* current route renders here */}
        <Outlet />
      </div>
    </div>
  );
}

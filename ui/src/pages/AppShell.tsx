import { Link, Outlet } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";

export default function AppShell() {
  return (
    <div className="min-h-screen bg-white text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <div className="mx-auto p-4 max-w-screen-2xl 2xl:max-w-[1600px]">
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
          <ThemeToggle />
        </div>

        {/* current route renders here */}
        <Outlet />
      </div>
    </div>
  );
}

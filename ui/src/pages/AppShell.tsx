import { Link, Outlet } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";

function GearIcon() {
  return (
    <svg
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
      <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.4V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.4 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.4-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.4-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3 1.6 1.6 0 0 0 1-1.4V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.4 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8 1.6 1.6 0 0 0 1.4 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.4 1Z" />
    </svg>
  );
}

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
          <Link
            to="/data-assistant"
            className="rounded-xl border border-zinc-700 px-3 py-1.5 hover:bg-zinc-900/40"
          >
            Data Assistant
          </Link>
          <Link
            to="/settings"
            className="rounded-xl border border-zinc-700 px-3 py-1.5 hover:bg-zinc-900/40 inline-flex items-center gap-2"
          >
            <GearIcon />
            Settings
          </Link>
          <ThemeToggle />
        </div>

        {/* current route renders here */}
        <Outlet />
      </div>
    </div>
  );
}

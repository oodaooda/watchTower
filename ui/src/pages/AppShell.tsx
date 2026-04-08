import { NavLink, Outlet } from "react-router-dom";
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
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    [
      "rounded-xl border px-3 py-1.5 text-sm inline-flex items-center gap-2 transition-colors",
      isActive
        ? "border-sky-400/60 bg-sky-500/10 text-sky-300"
        : "border-zinc-700 text-zinc-200 hover:bg-zinc-900/40",
    ].join(" ");

  return (
    <div className="min-h-screen bg-white text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <div className="mx-auto w-full max-w-[1800px] px-4 md:px-6 lg:px-8 py-4">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <NavLink to="/" end className={navLinkClass}>
            Screner
          </NavLink>
          <NavLink to="/companies" className={navLinkClass}>
            Companies
          </NavLink>
          <NavLink to="/universe" className={navLinkClass}>
            Universe
          </NavLink>
          <NavLink to="/favorites" className={navLinkClass}>
            Favorites
          </NavLink>
          <NavLink to="/portfolio" className={navLinkClass}>
            Portfolio
          </NavLink>
          <NavLink to="/finance-university" className={navLinkClass}>
            Finance University
          </NavLink>
          <NavLink to="/data-assistant" className={navLinkClass}>
            Data Assistant
          </NavLink>
          <NavLink to="/usage" className={navLinkClass}>
            Usage
          </NavLink>
          <NavLink to="/settings" className={navLinkClass}>
            <GearIcon />
            Settings
          </NavLink>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>

        {/* current route renders here */}
        <Outlet />
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const [dark, setDark] = useState<boolean>(() => {
    const saved = localStorage.getItem("wt-theme");
    if (saved) return saved === "dark";
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (dark) {
      root.classList.add("dark");
      localStorage.setItem("wt-theme", "dark");
    } else {
      root.classList.remove("dark");
      localStorage.setItem("wt-theme", "light");
    }
  }, [dark]);

  return (
    <button
      className="ml-auto rounded-xl px-3 py-1 border text-sm
                 border-zinc-300 hover:bg-zinc-100
                 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
      onClick={() => setDark(d => !d)}
      title="Toggle dark mode"
    >
      {dark ? "Light" : "Dark"}
    </button>
  );
}

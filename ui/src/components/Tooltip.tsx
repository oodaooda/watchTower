import { ReactNode } from "react";

type TooltipProps = {
  label: string;
  children?: ReactNode;
};

export default function Tooltip({ label, children }: TooltipProps) {
  return (
    <span className="relative inline-flex items-center group">
      {children}
      <span
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-zinc-400/60 text-[10px] font-semibold text-zinc-300 group-hover:text-white"
        aria-hidden="true"
      >
        i
      </span>
      <span className="pointer-events-none absolute left-0 top-6 z-20 hidden w-56 rounded-xl border border-zinc-700/60 bg-zinc-900 px-3 py-2 text-xs text-zinc-100 shadow-xl group-hover:block group-focus-within:block">
        {label}
      </span>
    </span>
  );
}

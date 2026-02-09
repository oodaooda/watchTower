import { ArrowLeftIcon } from "@heroicons/react/24/outline";
import { useNavigate } from "react-router-dom";

export default function BackButton({
  to,
  label = "Back",
  className = "",
}: {
  to?: string;
  label?: string;
  className?: string;
}) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      onClick={() => (to ? navigate(to) : navigate(-1))}
      className={
        "inline-flex items-center gap-2 rounded-xl border border-zinc-700 px-3 py-1.5 text-sm hover:bg-zinc-900/40 " +
        className
      }
    >
      <ArrowLeftIcon className="h-4 w-4" />
      {label}
    </button>
  );
}

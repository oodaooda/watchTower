import { useState } from "react";
import { askDataAssistant } from "../lib/api";

const card =
  "rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950";

const btn =
  "h-9 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900 " +
  "hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

export default function DataAssistantPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    const q = input.trim();
    if (!q) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    try {
      const res = await askDataAssistant(q);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Could not retrieve an answer right now." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className={`${card} p-6`}>
        <div className="text-xs uppercase tracking-wide text-zinc-500">Data Assistant</div>
        <h1 className="text-2xl font-semibold">Ask about companies</h1>
        <p className="text-sm text-zinc-400">
          Examples: “What’s the P/E of AAPL?” or “Show net income for TSLA for 10 years.”
        </p>
      </div>

      <div className={`${card} p-4 space-y-3`}>
        <div className="min-h-[260px] max-h-[420px] overflow-auto space-y-2 text-sm">
          {messages.length === 0 ? (
            <div className="text-zinc-500">Ask a question to get started.</div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
                <span className="inline-block rounded-xl bg-zinc-100 dark:bg-zinc-800 px-3 py-2">
                  {m.content}
                </span>
              </div>
            ))
          )}
          {loading ? <div className="text-zinc-500">Thinking…</div> : null}
        </div>
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a finance question..."
            className="flex-1 h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
          />
          <button className={btn} onClick={handleSend} disabled={loading}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

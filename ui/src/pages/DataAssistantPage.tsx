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
  type QAData = {
    plan?: {
      companies_requested?: string[];
      companies_resolved?: string[];
      unresolved_companies?: string[];
      actions?: string[];
      years?: number;
      compare?: boolean;
      response_mode?: string;
    };
    queries?: Array<{
      company?: string;
      action?: string;
      sql_template?: string;
      params?: Record<string, string | number | boolean>;
      rows?: number;
      duration_ms?: number;
    }>;
    sources?: string[];
    results?: Record<
      string,
      {
        news_context?: {
          items?: Array<{
            title?: string;
            url?: string;
            source?: string;
            published_at?: string;
          }>;
          articles?: Array<{
            title?: string;
            url?: string;
            snippet?: string;
          }>;
        };
      }
    >;
  };
  const [messages, setMessages] = useState<
    Array<{ role: string; content: string; trace?: string[]; citations?: string[]; data?: QAData }>
  >([]);
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
        {
          role: "assistant",
          content: res.answer,
          trace: res.trace ?? [],
          citations: res.citations ?? [],
          data: (res.data as QAData) ?? {},
        },
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

  const handleComposerKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!loading) handleSend();
    }
  };

  const extractNewsLinks = (data?: QAData) => {
    if (!data?.results) return [];
    const links: Array<{ title: string; url: string; source?: string }> = [];
    for (const result of Object.values(data.results)) {
      const items = result.news_context?.items ?? [];
      for (const item of items) {
        if (!item?.url) continue;
        const title = item.title?.trim() || item.url;
        links.push({ title, url: item.url, source: item.source });
      }
    }
    const dedup = new Map<string, { title: string; url: string; source?: string }>();
    for (const link of links) {
      if (!dedup.has(link.url)) dedup.set(link.url, link);
    }
    return Array.from(dedup.values()).slice(0, 6);
  };

  const extractNewsSnippets = (data?: QAData) => {
    if (!data?.results) return [];
    const snippets: Array<{ title: string; snippet: string; url?: string }> = [];
    for (const result of Object.values(data.results)) {
      const articles = result.news_context?.articles ?? [];
      for (const article of articles) {
        if (!article?.snippet) continue;
        snippets.push({
          title: article.title?.trim() || "News excerpt",
          snippet: article.snippet,
          url: article.url,
        });
      }
    }
    const dedup = new Map<string, { title: string; snippet: string; url?: string }>();
    for (const snippet of snippets) {
      const key = snippet.url || `${snippet.title}:${snippet.snippet.slice(0, 80)}`;
      if (!dedup.has(key)) dedup.set(key, snippet);
    }
    return Array.from(dedup.values()).slice(0, 3);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className={`${card} p-6`}>
        <div className="text-xs uppercase tracking-wide text-zinc-500">Data Assistant</div>
        <h1 className="text-2xl font-semibold">Ask about companies</h1>
        <p className="text-sm text-zinc-400">
          Examples: “What’s the P/E of AAPL?” or “Show net income for TSLA for 10 years.”
        </p>
      </div>

      <div className={`${card} p-4 space-y-3`}>
        <div className="min-h-[460px] max-h-[720px] overflow-auto space-y-2 text-sm">
          {messages.length === 0 ? (
            <div className="text-zinc-500">Ask a question to get started.</div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
                <div className="inline-block max-w-[90%] rounded-xl bg-zinc-100 dark:bg-zinc-800 px-3 py-2 text-left">
                  <div className="whitespace-pre-wrap leading-7">{m.content}</div>
                </div>
                {m.role === "assistant" && m.citations && m.citations.length > 0 ? (
                  <div className="mt-1 flex flex-wrap gap-1 text-xs text-zinc-500">
                    {m.citations.map((c) => (
                      <span
                        key={c}
                        className="rounded-md border border-zinc-300 dark:border-zinc-700 px-2 py-0.5"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                ) : null}
                {m.role === "assistant" && extractNewsSnippets(m.data).length > 0 ? (
                  <div className="mt-2 space-y-2 text-xs">
                    {extractNewsSnippets(m.data).map((snippet, si) => (
                      <div
                        key={`${snippet.url ?? snippet.title}-${si}`}
                        className="max-w-[90%] rounded-lg border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 p-2"
                      >
                        <div className="font-semibold text-zinc-700 dark:text-zinc-200">{snippet.title}</div>
                        <div className="mt-1 text-zinc-600 dark:text-zinc-300 max-h-24 overflow-hidden">
                          {snippet.snippet}
                        </div>
                        {snippet.url ? (
                          <a
                            href={snippet.url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-1 inline-block underline text-zinc-500 hover:opacity-80"
                          >
                            Open source
                          </a>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : null}
                {m.role === "assistant" && m.trace && m.trace.length > 0 ? (
                  <details className="mt-1 text-xs text-zinc-500">
                    <summary className="cursor-pointer select-none">Reasoning trace</summary>
                    <div className="mt-1 whitespace-pre-wrap leading-6">{m.trace.join("\n")}</div>
                    {m.data?.plan ? (
                      <div className="mt-2 rounded-lg border border-zinc-300 dark:border-zinc-700 p-2">
                        <div className="font-semibold mb-1">Plan</div>
                        <div>Requested: {(m.data.plan.companies_requested ?? []).join(", ") || "none"}</div>
                        <div>Resolved: {(m.data.plan.companies_resolved ?? []).join(", ") || "none"}</div>
                        <div>Unresolved: {(m.data.plan.unresolved_companies ?? []).join(", ") || "none"}</div>
                        <div>Actions: {(m.data.plan.actions ?? []).join(", ") || "none"}</div>
                        <div>Years: {m.data.plan.years ?? "n/a"}</div>
                        <div>Compare: {m.data.plan.compare ? "yes" : "no"}</div>
                        <div>Mode: {m.data.plan.response_mode ?? "grounded"}</div>
                      </div>
                    ) : null}
                    {m.data?.queries && m.data.queries.length > 0 ? (
                      <div className="mt-2 rounded-lg border border-zinc-300 dark:border-zinc-700 p-2 space-y-2">
                        <div className="font-semibold">Queries</div>
                        {m.data.queries.map((q, qi) => (
                          <div key={qi} className="rounded-md border border-zinc-300/60 dark:border-zinc-700/60 p-2">
                            <div>
                              {q.company ?? "n/a"} · {q.action ?? "query"}
                            </div>
                            <div className="font-mono break-all">{q.sql_template ?? "n/a"}</div>
                            <div>params: {JSON.stringify(q.params ?? {})}</div>
                            <div>rows: {q.rows ?? 0} · duration: {q.duration_ms ?? 0}ms</div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {m.data?.sources && m.data.sources.length > 0 ? (
                      <div className="mt-2 rounded-lg border border-zinc-300 dark:border-zinc-700 p-2">
                        <div className="font-semibold mb-1">Sources</div>
                        <div>{m.data.sources.join(", ")}</div>
                      </div>
                    ) : null}
                    {extractNewsLinks(m.data).length > 0 ? (
                      <div className="mt-2 rounded-lg border border-zinc-300 dark:border-zinc-700 p-2">
                        <div className="font-semibold mb-1">News Citations</div>
                        <div className="space-y-1">
                          {extractNewsLinks(m.data).map((link) => (
                            <a
                              key={link.url}
                              href={link.url}
                              target="_blank"
                              rel="noreferrer"
                              className="block underline hover:opacity-80"
                            >
                              {link.title}
                              {link.source ? ` (${link.source})` : ""}
                            </a>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </details>
                ) : null}
              </div>
            ))
          )}
          {loading ? <div className="text-zinc-500">Thinking…</div> : null}
        </div>
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder="Ask a finance question..."
            rows={2}
            className="flex-1 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 text-sm resize-none"
          />
          <button className={btn} onClick={handleSend} disabled={loading || !input.trim()}>
            Send
          </button>
        </div>
        <div className="text-xs text-zinc-500">Press Enter to send, Shift+Enter for a new line.</div>
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import {
  ApiKeyOut,
  ApiKeyCreateOut,
  createOpenclawKey,
  fetchOpenclawSettings,
  listOpenclawKeys,
  revokeOpenclawKey,
  updateOpenclawSettings,
} from "../lib/api";

const card =
  "rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950";

const btn =
  "h-9 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900 " +
  "hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

const btnGhost =
  "h-9 px-3 rounded-xl font-medium inline-flex items-center justify-center " +
  "border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-200 " +
  "hover:bg-zinc-100/60 dark:hover:bg-zinc-800/60 focus:outline-none focus:ring-2 focus:ring-sky-500/30";

const STORAGE_KEY = "watchtower_settings_admin_token";

export default function SettingsPage() {
  const [adminToken, setAdminToken] = useState("");
  const [maxKeys, setMaxKeys] = useState(2);
  const [activeKeys, setActiveKeys] = useState(0);
  const [keys, setKeys] = useState<ApiKeyOut[]>([]);
  const [keyName, setKeyName] = useState("");
  const [newKey, setNewKey] = useState<ApiKeyCreateOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) || "";
    if (stored) {
      setAdminToken(stored);
      loadSettings(stored);
    }
  }, []);

  const loadSettings = async (token: string) => {
    try {
      setError(null);
      const settings = await fetchOpenclawSettings(token);
      setMaxKeys(settings.openclaw_max_keys);
      setActiveKeys(settings.active_keys);
      const list = await listOpenclawKeys(token);
      setKeys(list);
    } catch (err) {
      setError((err as Error).message || "Failed to load settings");
    }
  };

  const handleSaveToken = () => {
    localStorage.setItem(STORAGE_KEY, adminToken);
    if (adminToken) loadSettings(adminToken);
  };

  const handleUpdateMax = async () => {
    if (!adminToken) return;
    try {
      setError(null);
      const res = await updateOpenclawSettings(adminToken, maxKeys);
      setMaxKeys(res.openclaw_max_keys);
      setActiveKeys(res.active_keys);
    } catch (err) {
      setError((err as Error).message || "Failed to update settings");
    }
  };

  const handleCreateKey = async () => {
    if (!adminToken || !keyName.trim()) return;
    try {
      setError(null);
      const res = await createOpenclawKey(adminToken, keyName.trim());
      setNewKey(res);
      setKeyName("");
      const list = await listOpenclawKeys(adminToken);
      setKeys(list);
      const settings = await fetchOpenclawSettings(adminToken);
      setActiveKeys(settings.active_keys);
    } catch (err) {
      setError((err as Error).message || "Failed to create key");
    }
  };

  const handleRevoke = async (id: number) => {
    if (!adminToken) return;
    try {
      setError(null);
      await revokeOpenclawKey(adminToken, id);
      const list = await listOpenclawKeys(adminToken);
      setKeys(list);
      const settings = await fetchOpenclawSettings(adminToken);
      setActiveKeys(settings.active_keys);
    } catch (err) {
      setError((err as Error).message || "Failed to revoke key");
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className={`${card} p-6`}>
        <div className="text-xs uppercase tracking-wide text-zinc-500">Settings</div>
        <h1 className="text-2xl font-semibold">OpenClaw API Keys</h1>
        <p className="text-sm text-zinc-400">
          Generate and manage keys for OpenClaw to access WatchTower data.
        </p>
      </div>

      <div className={`${card} p-4 space-y-3`}>
        <div className="text-sm font-semibold">Admin Token</div>
        <div className="flex gap-2">
          <input
            value={adminToken}
            onChange={(e) => setAdminToken(e.target.value)}
            placeholder="Paste admin token"
            className="flex-1 h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
          />
          <button className={btn} onClick={handleSaveToken}>
            Save
          </button>
        </div>
        {!adminToken ? (
          <div className="text-xs text-zinc-500">
            Paste your Settings admin token and click Save to enable key actions.
          </div>
        ) : null}
        {error ? <div className="text-sm text-red-400">{error}</div> : null}
      </div>

      <div className={`${card} p-4 space-y-3`}>
        <div className="text-sm font-semibold">Key Limits</div>
        <div className="flex items-center gap-3">
          <input
            type="number"
            className="h-9 w-24 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
            value={maxKeys}
            onChange={(e) => setMaxKeys(Number(e.target.value))}
          />
          <button className={btnGhost} onClick={handleUpdateMax} disabled={!adminToken}>
            Update
          </button>
          <div className="text-xs text-zinc-500">
            Active keys: {activeKeys}
          </div>
        </div>
      </div>

      <div className={`${card} p-4 space-y-3`}>
        <div className="text-sm font-semibold">Generate New Key</div>
        <div className="flex gap-2">
          <input
            value={keyName}
            onChange={(e) => setKeyName(e.target.value)}
            placeholder="Key name (e.g., OpenClaw VPS)"
            className="flex-1 h-9 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 text-sm"
          />
          <button className={btn} onClick={handleCreateKey} disabled={!adminToken || !keyName.trim()}>
            Generate
          </button>
        </div>
        {!adminToken ? (
          <div className="text-xs text-zinc-500">
            Admin token required to generate keys.
          </div>
        ) : null}
        {newKey ? (
          <div className="rounded-xl border border-amber-300/40 bg-amber-50/60 dark:bg-amber-900/20 px-3 py-2 text-xs">
            <div className="font-semibold">New key (copy now — shown once):</div>
            <div className="mt-1 font-mono">{newKey.key}</div>
          </div>
        ) : null}
      </div>

      <div className={`${card} p-4 space-y-3`}>
        <div className="text-sm font-semibold">Existing Keys</div>
        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-zinc-500">
              <tr>
                <th className="py-2">Name</th>
                <th className="py-2">Prefix</th>
                <th className="py-2">Created</th>
                <th className="py-2">Last Used</th>
                <th className="py-2">Status</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id} className="border-t border-zinc-200 dark:border-zinc-800">
                  <td className="py-2">{k.name}</td>
                  <td className="py-2">{k.key_prefix}</td>
                  <td className="py-2">{k.created_at ?? "—"}</td>
                  <td className="py-2">{k.last_used_at ?? "—"}</td>
                  <td className="py-2">{k.revoked_at ? "Revoked" : "Active"}</td>
                  <td className="py-2 text-right">
                    {!k.revoked_at ? (
                      <button className={btnGhost} onClick={() => handleRevoke(k.id)}>
                        Revoke
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
              {keys.length === 0 ? (
                <tr>
                  <td className="py-2 text-zinc-500" colSpan={6}>No keys found.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

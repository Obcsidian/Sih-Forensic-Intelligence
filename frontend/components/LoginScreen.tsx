"use client";

import { useState } from "react";
import { api, setToken, ApiError } from "@/lib/api";
import type { AuthResponse } from "@/lib/types";

const DEMO_ACCOUNTS: { username: string; password: string; role: string }[] = [
  { username: "investigator", password: "investigator123", role: "full access" },
  { username: "reviewer", password: "reviewer123", role: "label + report" },
  { username: "viewer", password: "viewer123", role: "read-only" },
];

export default function LoginScreen({ onLoggedIn }: { onLoggedIn: (auth: AuthResponse) => void }) {
  const [username, setUsername] = useState("investigator");
  const [password, setPassword] = useState("investigator123");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const auth = await api.login(username, password);
      setToken(auth.access_token);
      onLoggedIn(auth);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the backend API");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-[#0b0d12]">
      <form onSubmit={submit} className="w-[360px] rounded-lg border border-border bg-panel p-8 shadow-2xl">
        <div className="mb-6 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-accent/20 text-accent">◆</div>
          <div>
            <div className="text-lg font-semibold text-white">ForensAI</div>
            <div className="text-xs text-gray-500">AI-assisted forensic triage</div>
          </div>
        </div>

        <label className="mb-1 block text-xs text-gray-400">Username</label>
        <input
          className="mb-3 w-full rounded border border-border bg-panel2 px-3 py-2 text-sm text-white outline-none focus:border-accent"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />

        <label className="mb-1 block text-xs text-gray-400">Password</label>
        <input
          type="password"
          className="mb-4 w-full rounded border border-border bg-panel2 px-3 py-2 text-sm text-white outline-none focus:border-accent"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && <div className="mb-3 rounded border border-bad/40 bg-bad/10 px-3 py-2 text-xs text-bad">{error}</div>}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-accent py-2 text-sm font-medium text-black transition hover:bg-accent/90 disabled:opacity-50"
        >
          {busy ? "Signing in..." : "Sign in"}
        </button>

        <div className="mt-5 border-t border-border pt-4 text-xs text-gray-500">
          <div className="mb-1.5 text-gray-400">Demo accounts (insecure, demo only):</div>
          {DEMO_ACCOUNTS.map((a) => (
            <button
              type="button"
              key={a.username}
              onClick={() => {
                setUsername(a.username);
                setPassword(a.password);
              }}
              className="mb-1 flex w-full items-center justify-between rounded px-2 py-1 text-left hover:bg-panel2"
            >
              <span className="text-gray-300">{a.username}</span>
              <span className="text-gray-600">{a.role}</span>
            </button>
          ))}
        </div>
      </form>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken, ApiError } from "@/lib/api";
import type { AuthResponse } from "@/lib/types";

const DEMO_ACCOUNTS: { username: string; password: string; role: string }[] = [
  { username: "investigator", password: "investigator123", role: "Full Access" },
  { username: "reviewer", password: "reviewer123", role: "Label & Report" },
  { username: "viewer", password: "viewer123", role: "Read Only" },
];

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("investigator");
  const [password, setPassword] = useState("investigator123");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const auth = await api.login(username, password);
      setToken(auth.access_token);
      localStorage.setItem("forensai_token", auth.access_token);
      localStorage.setItem("forensai_username", auth.username);
      localStorage.setItem("forensai_role", auth.role);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the backend API");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[#0b0d12]">
      {/* Blurred glass overlay background */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-[#0d1520] via-[#0a0f18] to-[#0d1017]" />
        <div className="absolute -left-1/4 -top-1/4 h-[600px] w-[600px] rounded-full bg-gradient-to-br from-cyan-500/10 via-violet-500/5 to-transparent blur-[120px]" />
        <div className="absolute -bottom-1/4 -right-1/4 h-[600px] w-[600px] rounded-full bg-gradient-to-tl from-violet-500/10 via-cyan-500/5 to-transparent blur-[120px]" />
        <div className="absolute inset-0 backdrop-blur-2xl" />
      </div>

      {/* Login card */}
      <div className="relative z-10 w-full max-w-md px-4">
        {/* Back button */}
        <button
          onClick={() => router.push("/")}
          className="mb-8 flex items-center gap-2 text-sm text-gray-500 transition-all hover:gap-3 hover:text-cyan-300"
        >
          <span className="text-lg">←</span>
          <span>Back to ForensAI</span>
        </button>

        {/* Login form card */}
        <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] shadow-[0_0_60px_rgba(34,211,238,0.1)] backdrop-blur-xl">
          {/* Top accent line */}
          <div className="h-px w-full bg-gradient-to-r from-transparent via-cyan-400/50 to-transparent" />

          <div className="p-8">
            {/* Logo & title */}
            <div className="mb-8 flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-cyan-400/20 bg-cyan-400/10 text-xl text-cyan-300 shadow-[0_0_30px_rgba(34,211,238,0.2)]">
                ◆
              </div>
              <div>
                <div className="text-xl font-bold text-white">Sign In</div>
                <div className="text-xs text-gray-500">Access your workspace</div>
              </div>
            </div>

            {/* Form */}
            <form onSubmit={submit} className="space-y-5">
              <div>
                <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-gray-400">
                  Username
                </label>
                <input
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white placeholder:text-gray-600 backdrop-blur-sm transition-all focus:border-cyan-400/50 focus:bg-white/10 focus:outline-none focus:ring-2 focus:ring-cyan-400/20"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                />
              </div>

              <div>
                <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-gray-400">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 pr-16 text-sm text-white placeholder:text-gray-600 backdrop-blur-sm transition-all focus:border-cyan-400/50 focus:bg-white/10 focus:outline-none focus:ring-2 focus:ring-cyan-400/20"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-gray-400 backdrop-blur-sm transition-all hover:border-cyan-400/30 hover:text-cyan-300"
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
              </div>

              {error && (
                <div className="rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-300 backdrop-blur-sm">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={busy}
                className="w-full rounded-xl border border-cyan-400/30 bg-gradient-to-r from-cyan-400/20 to-violet-400/20 py-3 text-sm font-semibold text-cyan-300 shadow-[0_0_30px_rgba(34,211,238,0.15)] backdrop-blur-sm transition-all hover:border-cyan-400/50 hover:from-cyan-400/30 hover:to-violet-400/30 hover:shadow-[0_0_40px_rgba(34,211,238,0.25)] disabled:opacity-50"
              >
                {busy ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-400/30 border-t-cyan-400" />
                    Signing in...
                  </span>
                ) : (
                  "Sign In"
                )}
              </button>
            </form>

            {/* Demo accounts */}
            <div className="mt-8 pt-6">
              <div className="mb-4 flex items-center gap-3">
                <div className="h-px flex-1 bg-white/10" />
                <span className="text-[10px] uppercase tracking-widest text-gray-600">Demo Accounts</span>
                <div className="h-px flex-1 bg-white/10" />
              </div>

              <div className="space-y-2">
                {DEMO_ACCOUNTS.map((a) => (
                  <button
                    key={a.username}
                    type="button"
                    onClick={() => {
                      setUsername(a.username);
                      setPassword(a.password);
                    }}
                    className="flex w-full items-center justify-between rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3 transition-all hover:border-cyan-400/30 hover:bg-white/[0.05]"
                  >
                    <div className="text-left">
                      <div className="text-sm font-medium text-white">{a.username}</div>
                      <div className="text-[10px] text-gray-500">{a.role}</div>
                    </div>
                    <div className="flex h-6 w-6 items-center justify-center rounded-full border border-white/10 text-xs text-gray-500">
                      →
                    </div>
                  </button>
                ))}
              </div>

              <p className="mt-4 text-center text-[10px] text-gray-600">
                Demo credentials for testing purposes only
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

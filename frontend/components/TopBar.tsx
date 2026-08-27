"use client";

import { useState } from "react";
import type { Case, ChainVerification } from "@/lib/types";
import type { ViewMode } from "./Workspace";

const MENU_ITEMS = ["Case", "View", "Tools", "Ingest", "Window", "Help"];

export default function TopBar({
  activeCase,
  chain,
  view,
  setView,
  onAddDataSource,
  onCloseCase,
  searchQuery,
  onSearchQueryChange,
  onSearchSubmit,
  onGenerateReport,
  reportBusy,
  role,
  username,
  onLogout,
}: {
  activeCase: Case;
  chain: ChainVerification | null;
  view: ViewMode;
  setView: (v: ViewMode) => void;
  onAddDataSource: () => void;
  onCloseCase: () => void;
  searchQuery: string;
  onSearchQueryChange: (q: string) => void;
  onSearchSubmit: () => void;
  onGenerateReport: () => void;
  reportBusy: boolean;
  role: string;
  username: string;
  onLogout: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);

  const toolbarBtn = (label: string, target: ViewMode, extraClass = "") => (
    <button
      onClick={() => setView(target)}
      className={`${view === target ? "liquid-btn liquid-btn-active" : "liquid-btn opacity-70 hover:opacity-100"} px-3 py-1.5 text-xs font-medium ${extraClass}`}
    >
      {label}
    </button>
  );

  return (
    <div className="glass-panel flex flex-col rounded-2xl border-b-0">
      {/* menu row */}
      <div className="flex items-center justify-between border-b border-border/60 px-4 py-2">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-cyan-400/20 text-[11px] text-cyan-300 shadow-[0_0_15px_rgba(34,211,238,0.2)]">
              ◆
            </span>
            <span className="text-sm font-semibold text-white">ForensAI</span>
          </div>
          <nav className="relative flex items-center gap-3 text-xs text-gray-400">
            {MENU_ITEMS.map((m) => (
              <span key={m} className="cursor-default hover:text-gray-200" onClick={() => setMenuOpen(!menuOpen)}>
                {m}
              </span>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span className="rounded-full border border-border/60 bg-panel2/60 px-3 py-1">
            Case {activeCase.id} · <span className="text-gray-200">{activeCase.name}</span>
          </span>
          {chain && (
            <span className={`flex items-center gap-1 ${chain.valid ? "text-good" : "text-bad"}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${chain.valid ? "bg-good" : "bg-bad"}`} />
              {chain.valid ? "integrity OK" : "integrity BROKEN"}
            </span>
          )}
          <span className="rounded-full border border-border/60 bg-panel2/60 px-3 py-1 text-gray-300">
            {username} ({role})
          </span>
          <button onClick={onLogout} className="text-gray-500 transition hover:text-cyan-300">
            Sign out
          </button>
        </div>
      </div>

      {/* toolbar row */}
      <div className="flex items-center gap-2 px-4 py-2.5">
        <button
          onClick={onAddDataSource}
          className="input-glass px-3 py-1.5 text-xs font-medium text-gray-200 transition-colors hover:border-cyan-400/40 hover:bg-cyan-400/10 hover:text-cyan-300"
        >
          + Add data source
        </button>

        <div className="mx-1 h-5 w-px bg-border" />

        {toolbarBtn("Images / Videos", "evidence")}
        {toolbarBtn("Communications", "communications")}
        {toolbarBtn("Timeline", "timeline")}
        {toolbarBtn("AI triage", "triage")}

        <div className="mx-1 h-5 w-px bg-border" />

        <button
          onClick={onCloseCase}
          className="input-glass px-3 py-1.5 text-xs font-medium text-gray-400 transition-colors hover:border-cyan-400/40 hover:text-cyan-300"
        >
          Close case
        </button>

        <div className="input-glass ml-2 flex flex-1 items-center px-2 py-1.5">
          <span className="mr-2 text-gray-500">⌕</span>
          <input
            className="w-full bg-transparent text-xs text-gray-200 outline-none placeholder:text-gray-600"
            placeholder="Semantic + keyword search"
            value={searchQuery}
            onChange={(e) => onSearchQueryChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onSearchSubmit();
            }}
          />
          <kbd className="ml-2 rounded border border-border px-1 text-[10px] text-gray-600">Enter</kbd>
        </div>

        <button
          onClick={onGenerateReport}
          disabled={reportBusy}
          className="rounded-xl bg-gradient-to-r from-cyan-400/80 to-teal-400/80 px-4 py-1.5 text-xs font-semibold text-black shadow-[0_0_20px_rgba(34,211,238,0.2)] transition-all hover:from-cyan-300 hover:to-teal-300 hover:shadow-[0_0_30px_rgba(34,211,238,0.4)] disabled:opacity-50"
        >
          {reportBusy ? "Generating..." : "Generate report"}
        </button>
      </div>
    </div>
  );
}
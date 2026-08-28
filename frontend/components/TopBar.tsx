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
      className={`rounded px-3 py-1.5 text-xs font-medium transition ${
        view === target ? "bg-accent/20 text-accent" : "text-gray-300 hover:bg-panel3"
      } ${extraClass}`}
    >
      {label}
    </button>
  );

  return (
    <div className="flex flex-col border-b border-border bg-panel">
      {/* menu row */}
      <div className="flex items-center justify-between border-b border-border/60 px-3 py-1.5">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-accent/20 text-[11px] text-accent">
              ◆
            </span>
            <span className="text-sm font-semibold text-white">NetSherlock</span>
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
          <span>
            Case {activeCase.id} · <span className="text-gray-200">{activeCase.name}</span>
          </span>
          {chain && (
            <span className={`flex items-center gap-1 ${chain.valid ? "text-good" : "text-bad"}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${chain.valid ? "bg-good" : "bg-bad"}`} />
              {chain.valid ? "integrity OK" : "integrity BROKEN"}
            </span>
          )}
          <span className="text-gray-500">
            {username} ({role})
          </span>
          <button onClick={onLogout} className="text-gray-500 hover:text-gray-300">
            Sign out
          </button>
        </div>
      </div>

      {/* toolbar row */}
      <div className="flex items-center gap-2 px-3 py-2">
        <button
          onClick={onAddDataSource}
          className="rounded border border-border px-3 py-1.5 text-xs font-medium text-gray-200 hover:bg-panel2"
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
          className="rounded px-3 py-1.5 text-xs font-medium text-gray-400 hover:bg-panel3"
        >
          Close case
        </button>

        <div className="ml-2 flex flex-1 items-center rounded border border-border bg-panel2 px-2 py-1.5">
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
          className="rounded bg-accent px-4 py-1.5 text-xs font-semibold text-black hover:bg-accent/90 disabled:opacity-50"
        >
          {reportBusy ? "Generating..." : "Generate report"}
        </button>
      </div>
    </div>
  );
}

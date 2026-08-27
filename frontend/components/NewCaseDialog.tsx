"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Case } from "@/lib/types";

export default function NewCaseDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (c: Case) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [sourcePath, setSourcePath] = useState("../sample_case");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.createCase({ name, description, source_path: sourcePath });
      await api.ingestCase(created.id);
      onCreated(created);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create/ingest case");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <form
        onSubmit={submit}
        className="glass-card w-[460px] p-7 animate-float"
        style={{ animationDuration: "1s", animationIterationCount: 1 }}
      >
        <div className="mb-5 flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-400/15 text-sm text-cyan-300 shadow-[0_0_15px_rgba(34,211,238,0.2)]">
            +
          </div>
          <div>
            <div className="text-sm font-semibold text-white">Add data source / new case</div>
            <div className="text-[10px] uppercase tracking-wider text-gray-500">Ingest a case-export folder</div>
          </div>
        </div>

        <label className="mb-1 block text-[11px] font-medium text-gray-400">Case name</label>
        <input
          required
          className="input-glass mb-3 w-full px-3 py-2.5 text-sm text-white placeholder:text-gray-600"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Case 2411 - Marlow"
        />

        <label className="mb-1 block text-[11px] font-medium text-gray-400">Description (optional)</label>
        <textarea
          className="input-glass mb-3 w-full resize-none px-3 py-2.5 text-sm text-white placeholder:text-gray-600"
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What is this case about?"
        />

        <label className="mb-1 block text-[11px] font-medium text-gray-400">Source path</label>
        <input
          className="input-glass mb-4 w-full px-3 py-2.5 font-mono text-xs text-white placeholder:text-gray-600"
          value={sourcePath}
          onChange={(e) => setSourcePath(e.target.value)}
        />

        {error && (
          <div className="mb-3 rounded-xl border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-300">{error}</div>
        )}

        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="input-glass flex-1 py-2 text-xs font-medium text-gray-300 transition-colors hover:text-white"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy}
            className="liquid-btn flex-[2] py-2 text-xs font-semibold disabled:opacity-50"
          >
            {busy ? "Ingesting…" : "Create & ingest"}
          </button>
        </div>
      </form>
    </div>
  );
}
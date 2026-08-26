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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <form onSubmit={submit} className="w-[440px] rounded-lg border border-border bg-panel p-6 shadow-2xl">
        <div className="mb-4 text-sm font-semibold text-white">Add data source / new case</div>

        <label className="mb-1 block text-xs text-gray-400">Case name</label>
        <input
          required
          className="mb-3 w-full rounded border border-border bg-panel2 px-3 py-2 text-sm text-white outline-none focus:border-accent"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Case 2411 - Marlow"
        />

        <label className="mb-1 block text-xs text-gray-400">Description (optional)</label>
        <input
          className="mb-3 w-full rounded border border-border bg-panel2 px-3 py-2 text-sm text-white outline-none focus:border-accent"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />

        <label className="mb-1 block text-xs text-gray-400">
          Case-export folder path (server-side path, readable by the backend)
        </label>
        <input
          required
          className="mb-1 w-full rounded border border-border bg-panel2 px-3 py-2 text-sm text-white outline-none focus:border-accent"
          value={sourcePath}
          onChange={(e) => setSourcePath(e.target.value)}
        />
        <div className="mb-3 text-[11px] text-gray-500">
          Contains contacts.csv / calls.csv / messages.csv / device_events.json / photos/ / audio/. Run{" "}
          <code className="text-gray-400">python scripts/seed_demo_case.py</code> from the repo root to generate a
          sample one.
        </div>

        {error && <div className="mb-3 rounded border border-bad/40 bg-bad/10 px-3 py-2 text-xs text-bad">{error}</div>}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-border px-3 py-1.5 text-sm text-gray-300 hover:bg-panel2"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy}
            className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-black hover:bg-accent/90 disabled:opacity-50"
          >
            {busy ? "Ingesting..." : "Create + Ingest"}
          </button>
        </div>
      </form>
    </div>
  );
}

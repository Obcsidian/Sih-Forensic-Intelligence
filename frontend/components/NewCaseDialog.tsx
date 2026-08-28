"use client";

import { useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Case, IngestSummary } from "@/lib/types";

export default function NewCaseDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (c: Case) => void;
}) {
  const [mode, setMode] = useState<"upload" | "path">("upload");

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [sourcePath, setSourcePath] = useState("../sample_case");

  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const [result, setResult] = useState<{ case: Case; summary: IngestSummary } | null>(null);

  function pickFiles(list: FileList | File[] | null) {
    const picked = list ? Array.from(list) : [];
    if (picked.length === 0) return;
    setFiles((prev) => {
      const byName = new Map(prev.map((f) => [f.name, f]));
      for (const f of picked) byName.set(f.name, f);
      return Array.from(byName.values());
    });
    if (!name) {
      if (picked.every((f) => /\.eml$/i.test(f.name))) {
        setName(`${picked.length} email${picked.length !== 1 ? "s" : ""}`);
      } else {
        const first =
          picked.find((f) => /\.(e01|s01|l01|ex01|dd|img|raw|001|vmdk|vhd|vhdx|ufdr|ufd)$/i.test(f.name)) || picked[0];
        setName(first.name.replace(/\.[^.]+$/, ""));
      }
    }
  }

  function removeFile(fname: string) {
    setFiles((prev) => prev.filter((f) => f.name !== fname));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      let created: Case;
      if (mode === "upload") {
        if (files.length === 0) throw new ApiError(400, "Choose a disk image or .UFDR file (or all its segments) first");
        setBusyLabel(files.length > 1 ? `Uploading ${files.length} files...` : "Uploading...");
        created = await api.uploadCase({ name, description, files });
      } else {
        created = await api.createCase({ name, description, source_path: sourcePath });
      }
      setBusyLabel("Ingesting...");
      const summary = await api.ingestCase(created.id);
      if (summary.errors.length > 0) {
        setResult({ case: created, summary });
      } else {
        const fresh = await api.getCase(created.id);
        onCreated(fresh);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create/ingest case");
    } finally {
      setBusy(false);
      setBusyLabel("");
    }
  }

  async function continueToCase() {
    if (!result) return;
    const fresh = await api.getCase(result.case.id);
    onCreated(fresh);
  }

  if (result) {
    const s = result.summary;
    const counts = [
      ["Contacts", s.contacts],
      ["Calls", s.calls],
      ["Messages", s.messages],
      ["Photos", s.photos],
      ["Videos", s.videos],
      ["Audio files", s.audio_files],
      ["Device events", s.device_events],
    ].filter(([, n]) => (n as number) > 0);

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <div className="w-[520px] rounded-lg border border-border bg-panel p-6 shadow-2xl">
          <div className="mb-3 text-sm font-semibold text-white">Ingest finished with warnings</div>

          {counts.length > 0 ? (
            <div className="mb-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-300">
              {counts.map(([label, n]) => (
                <div key={label as string} className="flex justify-between">
                  <span className="text-gray-500">{label}</span>
                  <span>{n}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="mb-3 text-xs text-gray-400">No contacts, calls, messages, or media were extracted.</div>
          )}

          <div className="mb-1 text-xs font-medium text-warn">{s.errors.length} issue(s) during ingest</div>
          <div className="mb-4 max-h-64 overflow-y-auto rounded border border-border bg-panel2 p-2">
            {s.errors.map((e, i) => (
              <div key={i} className="mb-1.5 border-b border-border/40 pb-1.5 text-[11px] text-gray-300 last:mb-0 last:border-0">
                {e}
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-border px-3 py-1.5 text-sm text-gray-300 hover:bg-panel2"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={continueToCase}
              className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-black hover:bg-accent/90"
            >
              Open case anyway
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <form onSubmit={submit} className="w-[480px] rounded-lg border border-border bg-panel p-6 shadow-2xl">
        <div className="mb-4 text-sm font-semibold text-white">New case</div>

        <div className="mb-4 flex rounded border border-border bg-panel2 p-0.5 text-xs">
          <button
            type="button"
            onClick={() => setMode("upload")}
            className={`flex-1 rounded px-2 py-1.5 font-medium transition ${
              mode === "upload" ? "bg-accent text-black" : "text-gray-400 hover:text-gray-200"
            }`}
          >
            Upload disk image / UFDR file
          </button>
          <button
            type="button"
            onClick={() => setMode("path")}
            className={`flex-1 rounded px-2 py-1.5 font-medium transition ${
              mode === "path" ? "bg-accent text-black" : "text-gray-400 hover:text-gray-200"
            }`}
          >
            Server folder path (advanced)
          </button>
        </div>

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

        {mode === "upload" ? (
          <>
            <label className="mb-1 block text-xs text-gray-400">Forensic image, export file, or .eml email(s)</label>
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                pickFiles(e.dataTransfer.files);
              }}
              className={`mb-1 flex cursor-pointer flex-col items-center justify-center rounded border border-dashed px-4 py-6 text-center transition ${
                dragOver ? "border-accent bg-accent/5" : "border-border bg-panel2 hover:border-accent/50"
              }`}
            >
              {files.length > 0 ? (
                <div className="text-sm text-gray-300">Click or drop to add more files</div>
              ) : (
                <>
                  <div className="text-sm text-gray-300">Click to browse, or drag file(s) here</div>
                  <div className="mt-0.5 text-[11px] text-gray-500">
                    .E01 / .S01 / .L01 / .EX01 / .dd / .img / .raw / .001 / .vmdk / .vhd / .vhdx / .UFDR / .eml
                  </div>
                </>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => pickFiles(e.target.files)}
            />

            {files.length > 0 && (
              <div className="mb-1 max-h-32 overflow-y-auto rounded border border-border bg-panel2">
                {files.map((f) => (
                  <div key={f.name} className="flex items-center justify-between border-b border-border/40 px-2 py-1 text-xs last:border-0">
                    <span className="truncate text-gray-200">{f.name}</span>
                    <span className="ml-2 flex items-center gap-2 shrink-0 text-gray-500">
                      {(f.size / (1024 * 1024)).toFixed(1)} MB
                      <button type="button" onClick={() => removeFile(f.name)} className="text-gray-500 hover:text-bad">
                        ✕
                      </button>
                    </span>
                  </div>
                ))}
              </div>
            )}

            <div className="mb-3 text-[11px] text-gray-500">
              For a multi-segment image (.E01, .E02, .E03, ...), select or drop every segment file together. Or drop
              one or more standalone .eml files directly — no disk image needed. Files upload to the backend and are
              ingested automatically.
            </div>
          </>
        ) : (
          <>
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
              <code className="text-gray-400">python scripts/seed_demo_case.py</code> from the repo root to generate
              a sample one. Also accepts a server-side .E01/.UFDR path directly.
            </div>
          </>
        )}

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
            {busy ? busyLabel || "Working..." : "Create + Ingest"}
          </button>
        </div>
      </form>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { api, fetchProtectedBytes } from "@/lib/api";
import { useAuthedBlobUrl } from "@/lib/useAuthedBlobUrl";
import type { AuditLogEntry, EvidenceFile, Person, Transcript } from "@/lib/types";

type Tab = "preview" | "hex" | "text" | "metadata" | "annotations" | "custody";

function fmtBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export default function PreviewPane({
  caseId,
  evidence,
  transcripts,
  people,
  audit,
}: {
  caseId: number;
  evidence: EvidenceFile | null;
  transcripts: Transcript[];
  people: Person[];
  audit: AuditLogEntry[];
}) {
  const [tab, setTab] = useState<Tab>("preview");

  useEffect(() => {
    setTab("preview");
  }, [evidence?.id]);

  if (!evidence) {
    return (
      <div className="flex h-56 shrink-0 items-center justify-center border-t border-border bg-panel text-xs text-gray-600">
        Select a file to preview it here.
      </div>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "preview", label: "Preview" },
    { id: "hex", label: "Hex" },
    { id: "text", label: "Text" },
    { id: "metadata", label: "File Metadata" },
    { id: "annotations", label: "Annotations" },
    { id: "custody", label: "Chain of custody" },
  ];

  return (
    <div className="flex h-64 shrink-0 flex-col border-t border-border bg-panel">
      <div className="flex gap-1 border-b border-border px-2 py-1">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`rounded px-2.5 py-1 text-[11px] ${tab === t.id ? "bg-accent/20 text-accent" : "text-gray-400 hover:bg-panel3"}`}
          >
            {t.label}
          </button>
        ))}
        <span className="ml-3 self-center truncate text-[11px] text-gray-600">{evidence.file_name}</span>
      </div>

      <div className="flex-1 overflow-auto p-3 text-xs">
        {tab === "preview" && <PreviewTab caseId={caseId} evidence={evidence} />}
        {tab === "hex" && <HexTab caseId={caseId} evidence={evidence} />}
        {tab === "text" && <TextTab evidence={evidence} transcripts={transcripts} />}
        {tab === "metadata" && <MetadataTab evidence={evidence} />}
        {tab === "annotations" && <AnnotationsTab evidence={evidence} people={people} />}
        {tab === "custody" && <CustodyTab evidence={evidence} audit={audit} />}
      </div>
    </div>
  );
}

function PreviewTab({ caseId, evidence }: { caseId: number; evidence: EvidenceFile }) {
  const { url, loading, error } = useAuthedBlobUrl(api.evidenceFileUrl(caseId, evidence.id));

  if (loading) return <div className="text-gray-600">Loading preview…</div>;
  if (error) return <div className="text-bad">Could not load file: {error}</div>;
  if (!url) return null;

  if (evidence.kind === "photo") return <img src={url} alt={evidence.file_name} className="max-h-52 rounded border border-border" />;
  if (evidence.kind === "audio")
    return (
      <audio controls src={url} className="w-full">
        Your browser cannot play this audio.
      </audio>
    );
  return <div className="text-gray-500">No inline preview for this file type — use the Hex or File Metadata tab.</div>;
}

function HexTab({ caseId, evidence }: { caseId: number; evidence: EvidenceFile }) {
  const [bytes, setBytes] = useState<Uint8Array | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setBytes(null);
    setError(null);
    fetchProtectedBytes(api.evidenceFileUrl(caseId, evidence.id), 512)
      .then(setBytes)
      .catch((e) => setError(e.message));
  }, [caseId, evidence.id]);

  if (error) return <div className="text-bad">{error}</div>;
  if (!bytes) return <div className="text-gray-600">Reading bytes…</div>;

  const rows = [];
  for (let offset = 0; offset < bytes.length; offset += 16) {
    const chunk = bytes.slice(offset, offset + 16);
    const hex = Array.from(chunk)
      .map((b) => b.toString(16).padStart(2, "0").toUpperCase())
      .join(" ");
    const ascii = Array.from(chunk)
      .map((b) => (b >= 32 && b < 127 ? String.fromCharCode(b) : "."))
      .join("");
    rows.push(
      <div key={offset} className="whitespace-pre font-mono text-[11px] text-gray-400">
        <span className="text-gray-600">{offset.toString(16).padStart(8, "0")}</span>{"  "}
        <span className="text-gray-300">{hex.padEnd(47, " ")}</span>{"  "}
        <span className="text-gray-500">{ascii}</span>
      </div>
    );
  }
  return <div>{rows}</div>;
}

function TextTab({ evidence, transcripts }: { evidence: EvidenceFile; transcripts: Transcript[] }) {
  const transcript = transcripts.find((t) => t.evidence_file_id === evidence.id);
  if (evidence.kind !== "audio") return <div className="text-gray-600">Text extraction is only available for audio (via transcription).</div>;
  if (!transcript) return <div className="text-gray-600">No transcript yet — run case processing or install faster-whisper.</div>;
  return (
    <div>
      <div className="mb-2 text-[11px] text-gray-500">language: {transcript.language || "unknown"}</div>
      <div className="whitespace-pre-wrap text-gray-200">{transcript.text || "(empty transcript)"}</div>
    </div>
  );
}

function MetadataTab({ evidence }: { evidence: EvidenceFile }) {
  const rows: [string, string][] = [
    ["File name", evidence.file_name],
    ["Kind", evidence.kind],
    ["SHA-256", evidence.sha256],
    ["Size", fmtBytes(evidence.size_bytes)],
    ["Captured", evidence.captured_at ? new Date(evidence.captured_at).toLocaleString() : "—"],
    ["Ingested", new Date(evidence.created_at).toLocaleString()],
    ["GPS", evidence.latitude !== null ? `${evidence.latitude?.toFixed(5)}, ${evidence.longitude?.toFixed(5)}` : "—"],
    ["Deleted → recovered", evidence.deleted_then_recovered ? "yes" : "no"],
    ["Original path", evidence.original_path],
  ];
  return (
    <table className="text-[11px]">
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k}>
            <td className="w-40 py-0.5 pr-3 align-top text-gray-500">{k}</td>
            <td className="break-all py-0.5 text-gray-200">{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AnnotationsTab({ evidence, people }: { evidence: EvidenceFile; people: Person[] }) {
  return (
    <div className="space-y-3">
      <div>
        <div className="mb-1 text-gray-500">NSFW pre-screen</div>
        {evidence.nsfw_score === null ? (
          <div className="text-gray-600">Not screened (opennsfw2 not installed, or not run yet).</div>
        ) : (
          <div className={evidence.nsfw_flagged ? "text-bad" : "text-good"}>
            score {evidence.nsfw_score.toFixed(3)} — {evidence.nsfw_flagged ? "flagged for human review" : "not flagged"}
            {evidence.nsfw_flagged && (
              <span className="ml-2 text-gray-500">({evidence.nsfw_reviewed ? "reviewed" : "pending review"})</span>
            )}
          </div>
        )}
        <div className="mt-1 text-[10px] text-gray-600">
          Flag-for-review only — never auto-classified as evidence or auto-deleted.
        </div>
      </div>

      {evidence.kind === "photo" && (
        <div>
          <div className="mb-1 text-gray-500">People labeled in this case</div>
          {people.filter((p) => p.label).length === 0 ? (
            <div className="text-gray-600">No labeled people yet.</div>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {people
                .filter((p) => p.label)
                .map((p) => (
                  <span key={p.id} className="rounded bg-panel3 px-2 py-0.5 text-[10px] text-gray-300">
                    {p.label}
                  </span>
                ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CustodyTab({ evidence, audit }: { evidence: EvidenceFile; audit: AuditLogEntry[] }) {
  const related = audit.filter((a) => {
    try {
      const payload = JSON.parse(a.payload_json);
      return payload.file_name === evidence.file_name || payload.sha256 === evidence.sha256;
    } catch {
      return false;
    }
  });

  if (related.length === 0) return <div className="text-gray-600">No audit entries reference this file directly.</div>;

  return (
    <div className="space-y-1.5">
      {related.map((a) => (
        <div key={a.id} className="rounded border border-border/60 bg-panel2 px-2 py-1.5 text-[11px]">
          <div className="flex gap-2 text-gray-500">
            <span>{new Date(a.timestamp).toLocaleString()}</span>
            <span className="text-accent">{a.action}</span>
            <span>by {a.actor}</span>
          </div>
          <div className="mt-0.5 font-mono text-[10px] text-gray-600">hash {a.hash.slice(0, 16)}…</div>
        </div>
      ))}
    </div>
  );
}

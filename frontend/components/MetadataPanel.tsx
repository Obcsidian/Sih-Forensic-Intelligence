"use client";

import { useAuthedBlobUrl } from "@/lib/useAuthedBlobUrl";
import { api } from "@/lib/api";
import type { EvidenceFile, Person } from "@/lib/types";

function fmtBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export default function MetadataPanel({
  caseId,
  evidence,
  people,
  onMarkNsfwReviewed,
}: {
  caseId: number;
  evidence: EvidenceFile | null;
  people: Person[];
  onMarkNsfwReviewed: (evidenceId: number) => Promise<void>;
}) {
  const { url } = useAuthedBlobUrl(evidence?.kind === "photo" ? api.evidenceFileUrl(caseId, evidence.id) : null);

  if (!evidence) {
    return (
      <div className="w-72 shrink-0 border-l border-border bg-panel p-3 text-xs text-gray-600">
        No file selected.
      </div>
    );
  }

  return (
    <div className="flex w-72 shrink-0 flex-col overflow-y-auto border-l border-border bg-panel p-3 text-xs">
      <div className="mb-2 truncate text-sm font-medium text-white" title={evidence.file_name}>
        {evidence.file_name}
      </div>

      {evidence.kind === "photo" && url && (
        <img src={url} alt={evidence.file_name} className="mb-3 max-h-40 w-full rounded border border-border object-cover" />
      )}

      <Row label="name" value={evidence.file_name} />
      <Row label="path" value={evidence.original_path} mono />
      <Row label="size" value={fmtBytes(evidence.size_bytes)} />
      <Row label="mime/kind" value={evidence.kind} />
      <Row label="sha-256" value={evidence.sha256} mono />
      <Row label="created" value={new Date(evidence.captured_at || evidence.created_at).toLocaleString()} />
      <Row label="source" value="case-export ingest" />
      <Row label="deleted" value={evidence.deleted_then_recovered ? "recovered" : "no"} />

      {evidence.nsfw_score !== null && (
        <div className="mt-3 rounded border border-border/60 bg-panel2 p-2">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-gray-500">NSFW pre-screen</span>
            <span className={evidence.nsfw_flagged ? "text-bad" : "text-good"}>{evidence.nsfw_score.toFixed(2)}</span>
          </div>
          {evidence.nsfw_flagged && !evidence.nsfw_reviewed && (
            <button
              onClick={() => onMarkNsfwReviewed(evidence.id)}
              className="w-full rounded bg-warn/20 py-1 text-[11px] text-warn hover:bg-warn/30"
            >
              Mark reviewed
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="mb-1.5 border-b border-border/40 pb-1.5">
      <div className="text-[10px] uppercase tracking-wide text-gray-600">{label}</div>
      <div className={`break-all text-gray-300 ${mono ? "font-mono text-[10px]" : ""}`}>{value}</div>
    </div>
  );
}

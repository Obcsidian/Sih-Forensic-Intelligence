"use client";

import { useState } from "react";
import type { Call, Case, Contact, EvidenceFile, Message, Person, TimelineEvent, Transcript } from "@/lib/types";
import type { CommTab, EvidenceFilter, TriageTab, ViewMode } from "./Workspace";

const KIND_ICON: Record<string, { icon: string; color: string }> = {
  photo: { icon: "□", color: "text-cyan-300" },
  video: { icon: "►", color: "text-violet-300" },
  audio: { icon: "♪", color: "text-emerald-300" },
  document: { icon: "∑", color: "text-amber-300" },
  other: { icon: "·", color: "text-gray-400" },
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="mb-2 px-2">
      <div
        className="mb-1 flex cursor-pointer items-center justify-between rounded-lg px-2 py-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-gray-500 transition-colors hover:bg-white/5 hover:text-gray-300"
        onClick={() => setOpen(!open)}
      >
        <span>{title}</span>
        <span className="text-gray-600">{open ? "▾" : "▸"}</span>
      </div>
      {open && <div className="space-y-0.5 pb-1">{children}</div>}
    </div>
  );
}

function Row({
  icon,
  label,
  count,
  active,
  onClick,
  tone,
}: {
  icon: string;
  label: string;
  count?: number;
  active?: boolean;
  onClick?: () => void;
  tone?: string;
}) {
  return (
    <div
      className={`tree-row ${active ? "active" : ""}`}
      onClick={onClick}
    >
      <span className={`w-4 text-center text-[12px] ${tone || "text-gray-400"}`}>{icon}</span>
      <span className="flex-1 truncate text-[12px] text-gray-200">{label}</span>
      {count !== undefined && (
        <span className="rounded-full border border-white/5 bg-white/5 px-1.5 py-px text-[9.5px] font-medium text-gray-400">
          {count.toLocaleString()}
        </span>
      )}
    </div>
  );
}

export default function TreeSidebar({
  sourcePath,
  caseStatus,
  evidence,
  people,
  transcripts,
  timeline,
  contacts,
  calls,
  messages,
  activeView,
  activeFilterLabel,
  onNavigate,
}: {
  sourcePath: string;
  caseStatus: Case["status"];
  evidence: EvidenceFile[];
  people: Person[];
  transcripts: Transcript[];
  timeline: TimelineEvent[];
  contacts: Contact[];
  calls: Call[];
  messages: Message[];
  activeView: ViewMode;
  activeFilterLabel: string;
  onNavigate: (v: ViewMode, opts?: { evidenceFilter?: EvidenceFilter; triageTab?: TriageTab; commTab?: CommTab }) => void;
}) {
  const photoCount = evidence.filter((e) => e.kind === "photo").length;
  const videoCount = evidence.filter((e) => e.kind === "video").length;
  const audioCount = evidence.filter((e) => e.kind === "audio").length;
  const docCount = evidence.filter((e) => e.kind === "document").length;
  const otherCount = evidence.filter((e) => e.kind === "other").length;
  const deletedRecovered = evidence.filter((e) => e.deleted_then_recovered).length;
  const geotagged = evidence.filter((e) => e.latitude !== null).length;
  const nsfwFlagged = evidence.filter((e) => e.nsfw_flagged).length;
  const anomalyCount = timeline.filter((e) => e.event_type === "anomaly").length;

  const isEv = (label: string) => activeView === "evidence" && activeFilterLabel === label;

  return (
    <div className="glass-panel flex w-64 shrink-0 flex-col overflow-y-auto border-r border-border/50 py-3">
      <div className="mx-3 mb-3 rounded-2xl border border-white/5 bg-white/[0.04] p-2.5">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan-400/15 text-sm text-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.15)]">■</div>
          <div className="min-w-0">
            <div className="truncate text-[11px] font-semibold text-white">
              {sourcePath.split(/[\\/]/).pop() || sourcePath}
            </div>
            <div className="text-[9.5px] uppercase tracking-wider text-gray-500">Data Source</div>
          </div>
        </div>
        <div className={`mt-2 flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${caseStatus === "ready" ? "bg-emerald-400/10 text-emerald-300" : caseStatus === "failed" ? "bg-red-400/10 text-red-300" : "bg-amber-400/10 text-amber-300"}`}>
          <span className="h-1 w-1 rounded-full bg-current" />
          {caseStatus}
        </div>
      </div>

      <Section title="File Types">
        <Row icon="◻" label="Photos" count={photoCount} tone="text-cyan-300" active={isEv("Photos")} onClick={() => onNavigate("evidence", { evidenceFilter: { kinds: ["photo"], label: "Photos" } })} />
        <Row icon="◉" label="Videos" count={videoCount} tone="text-violet-300" active={isEv("Videos")} onClick={() => onNavigate("evidence", { evidenceFilter: { kinds: ["video"], label: "Videos" } })} />
        <Row icon="◈" label="Audio" count={audioCount} tone="text-emerald-300" active={isEv("Audio")} onClick={() => onNavigate("evidence", { evidenceFilter: { kinds: ["audio"], label: "Audio" } })} />
        <Row icon="☐" label="Documents" count={docCount} tone="text-amber-300" active={isEv("Documents")} onClick={() => onNavigate("evidence", { evidenceFilter: { kinds: ["document"], label: "Documents" } })} />
        <Row icon="●" label="Other" count={otherCount} active={isEv("Other")} onClick={() => onNavigate("evidence", { evidenceFilter: { kinds: ["other"], label: "Other" } })} />
        <Row icon="↩" label="Recovered" count={deletedRecovered} tone="text-rose-300" active={isEv("Deleted (recovered)")} onClick={() => onNavigate("evidence", { evidenceFilter: { onlyDeletedRecovered: true, label: "Deleted (recovered)" } })} />
      </Section>

      <Section title="AI Analysis">
        <Row icon="◎" label="Face Clusters" count={people.length} tone="text-sky-300" active={activeView === "triage" && false} onClick={() => onNavigate("triage", { triageTab: "faces" })} />
        <Row icon="¶" label="Transcripts" count={transcripts.length} tone="text-indigo-300" onClick={() => onNavigate("evidence", { evidenceFilter: { kinds: ["audio"], label: "Audio" } })} />
        <Row icon="⚠" label="Anomalies" count={anomalyCount} tone="text-amber-300" onClick={() => onNavigate("triage", { triageTab: "anomalies" })} />
        <Row icon="⊘" label="NSFW flagged" count={nsfwFlagged} tone="text-rose-300" onClick={() => onNavigate("triage", { triageTab: "nsfw" })} />
      </Section>

      <Section title="Extracted Content">
        <Row icon="⊞" label="Contacts" count={contacts.length} tone="text-emerald-300" onClick={() => onNavigate("communications", { commTab: "contacts" })} />
        <Row icon="☏" label="Calls" count={calls.length} tone="text-sky-300" onClick={() => onNavigate("communications", { commTab: "calls" })} />
        <Row icon="»" label="Messages" count={messages.length} tone="text-violet-300" onClick={() => onNavigate("communications", { commTab: "messages" })} />
        <Row icon="⊕" label="Geotagged" count={geotagged} tone="text-teal-300" active={isEv("Geotagged photos")} onClick={() => onNavigate("evidence", { evidenceFilter: { onlyGeotagged: true, label: "Geotagged photos" } })} />
      </Section>
    </div>
  );
}
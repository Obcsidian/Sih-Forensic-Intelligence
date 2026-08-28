"use client";

import { useState } from "react";
import type { Call, Contact, DataSource, EvidenceFile, Message, Person, TimelineEvent, Transcript } from "@/lib/types";
import type { CommTab, EvidenceFilter, TriageTab, ViewMode } from "./Workspace";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="mb-1">
      <div
        className="flex cursor-pointer items-center justify-between px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-gray-500 hover:text-gray-300"
        onClick={() => setOpen(!open)}
      >
        <span>{title}</span>
        <span className="text-gray-600">{open ? "▾" : "▸"}</span>
      </div>
      {open && <div className="pb-1">{children}</div>}
    </div>
  );
}

function Row({
  icon,
  label,
  count,
  active,
  onClick,
}: {
  icon: string;
  label: string;
  count?: number;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <div className={`tree-row ${active ? "active" : ""}`} onClick={onClick}>
      <span className="w-4 text-center text-gray-500">{icon}</span>
      <span className="flex-1 truncate text-gray-300">{label}</span>
      {count !== undefined && <span className="text-gray-500">{count.toLocaleString()}</span>}
    </div>
  );
}

export default function TreeSidebar({
  dataSources,
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
  onAddDataSource,
}: {
  dataSources: DataSource[];
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
  onAddDataSource: () => void;
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
    <div className="flex w-64 shrink-0 flex-col overflow-y-auto border-r border-border bg-panel py-2 text-sm">
      <Section title="Data Sources">
        {dataSources.map((ds) => (
          <div key={ds.id}>
            <Row icon="⛁" label={ds.name} active={false} onClick={() => onNavigate("evidence")} />
            <div className="px-8 pb-1 text-[10px] text-gray-600">status: {ds.status}</div>
          </div>
        ))}
        <div
          className="tree-row cursor-pointer text-gray-500 hover:text-accent"
          onClick={onAddDataSource}
        >
          <span className="w-4 text-center">+</span>
          <span className="flex-1">Add data source</span>
        </div>
      </Section>

      <Section title="File Types">
        <Row icon="🖼" label="Photos" count={photoCount} active={isEv("Photos")} onClick={() => onNavigate("evidence", { evidenceFilter: { kinds: ["photo"], label: "Photos" } })} />
        <Row icon="🎬" label="Videos" count={videoCount} active={isEv("Videos")} onClick={() => onNavigate("evidence", { evidenceFilter: { kinds: ["video"], label: "Videos" } })} />
        <Row icon="🎧" label="Audio" count={audioCount} active={isEv("Audio")} onClick={() => onNavigate("evidence", { evidenceFilter: { kinds: ["audio"], label: "Audio" } })} />
        <Row icon="📄" label="Documents" count={docCount} active={isEv("Documents")} onClick={() => onNavigate("evidence", { evidenceFilter: { kinds: ["document"], label: "Documents" } })} />
        <Row icon="▪" label="Other" count={otherCount} active={isEv("Other")} onClick={() => onNavigate("evidence", { evidenceFilter: { kinds: ["other"], label: "Other" } })} />
        <Row
          icon="⟲"
          label="Deleted (recovered)"
          count={deletedRecovered}
          active={isEv("Deleted (recovered)")}
          onClick={() => onNavigate("evidence", { evidenceFilter: { onlyDeletedRecovered: true, label: "Deleted (recovered)" } })}
        />
      </Section>

      <Section title="AI Analysis">
        <Row icon="👤" label="Face Clusters" count={people.length} active={activeView === "triage" && false} onClick={() => onNavigate("triage", { triageTab: "faces" })} />
        <Row icon="📝" label="Transcripts" count={transcripts.length} onClick={() => onNavigate("evidence", { evidenceFilter: { kinds: ["audio"], label: "Audio" } })} />
        <Row icon="⚠" label="Anomalies" count={anomalyCount} onClick={() => onNavigate("triage", { triageTab: "anomalies" })} />
        <Row icon="🔞" label="NSFW flagged" count={nsfwFlagged} onClick={() => onNavigate("triage", { triageTab: "nsfw" })} />
      </Section>

      <Section title="Extracted Content">
        <Row icon="👥" label="Contacts" count={contacts.length} onClick={() => onNavigate("communications", { commTab: "contacts" })} />
        <Row icon="☎" label="Calls" count={calls.length} onClick={() => onNavigate("communications", { commTab: "calls" })} />
        <Row icon="💬" label="Messages" count={messages.length} onClick={() => onNavigate("communications", { commTab: "messages" })} />
        <Row
          icon="📍"
          label="Geotagged photos"
          count={geotagged}
          active={isEv("Geotagged photos")}
          onClick={() => onNavigate("evidence", { evidenceFilter: { onlyGeotagged: true, label: "Geotagged photos" } })}
        />
      </Section>
    </div>
  );
}

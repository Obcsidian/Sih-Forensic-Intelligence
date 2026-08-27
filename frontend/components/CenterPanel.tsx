"use client";

import { useMemo, useState } from "react";
import { useAuthedBlobUrl } from "@/lib/useAuthedBlobUrl";
import { api } from "@/lib/api";
import type { Call, Contact, EvidenceFile, Message, Person, SearchHit, TimelineEvent, Transcript } from "@/lib/types";
import type { CommTab, EvidenceFilter, TriageTab, ViewMode } from "./Workspace";

function fmtBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
function fmtTime(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}
function shortHash(h: string) {
  return `${h.slice(0, 10)}…`;
}

const EVENT_ICON: Record<string, string> = {
  call: "▶",
  message: "«",
  photo: "□",
  video: "►",
  audio: "♪",
  app_install: "↓",
  app_uninstall: "↑",
  file_deleted: "✕",
  file_recovered: "↩",
  anomaly: "!",
};

export default function CenterPanel(props: {
  caseId: number;
  view: ViewMode;
  evidence: EvidenceFile[];
  evidenceFilter: EvidenceFilter;
  people: Person[];
  triageTab: TriageTab;
  setTriageTab: (t: TriageTab) => void;
  commTab: CommTab;
  setCommTab: (t: CommTab) => void;
  contacts: Contact[];
  calls: Call[];
  messages: Message[];
  timeline: TimelineEvent[];
  transcripts: Transcript[];
  searchResults: SearchHit[] | null;
  searching: boolean;
  selectedEvidence: EvidenceFile | null;
  setSelectedEvidence: (e: EvidenceFile | null) => void;
  selectedPerson: Person | null;
  setSelectedPerson: (p: Person | null) => void;
  onLabelPerson: (personId: number, label: string) => Promise<void>;
  onRecluster: () => Promise<void>;
  loading: boolean;
}) {
  const {
    caseId,
    view,
    evidence,
    evidenceFilter,
    people,
    triageTab,
    setTriageTab,
    commTab,
    setCommTab,
    contacts,
    calls,
    messages,
    timeline,
    transcripts,
    searchResults,
    searching,
    selectedEvidence,
    setSelectedEvidence,
    selectedPerson,
    setSelectedPerson,
    onLabelPerson,
    onRecluster,
    loading,
  } = props;

  const [evidenceView, setEvidenceView] = useState<"table" | "thumbnail" | "cluster">("table");
  const [reclustering, setReclustering] = useState(false);

  const filteredEvidence = useMemo(() => {
    let list = evidence;
    if (evidenceFilter.kinds) list = list.filter((e) => evidenceFilter.kinds!.includes(e.kind));
    if (evidenceFilter.onlyGeotagged) list = list.filter((e) => e.latitude !== null);
    if (evidenceFilter.onlyDeletedRecovered) list = list.filter((e) => e.deleted_then_recovered);
    return list;
  }, [evidence, evidenceFilter]);

  if (loading) {
    return <div className="flex flex-1 items-center justify-center text-sm text-gray-500">Loading case data…</div>;
  }

  if (view === "search") {
    return (
      <div className="flex-1 overflow-y-auto">
        <div className="border-b border-border px-3 py-2 text-xs text-gray-500">
          {searching ? "Searching…" : `${searchResults?.length ?? 0} result(s)`}
        </div>
        {(searchResults ?? []).map((hit, i) => (
          <div key={i} className="border-b border-border/60 px-3 py-2 text-xs">
            <div className="mb-1 flex items-center gap-2 text-gray-500">
              <span className="rounded bg-panel3 px-1.5 py-0.5 text-[10px] uppercase text-accent">{hit.source_type}</span>
              <span>#{hit.source_id}</span>
              <span className="ml-auto">score {hit.score.toFixed(3)}</span>
            </div>
            <div className="text-gray-300">{hit.text}</div>
          </div>
        ))}
        {searchResults && searchResults.length === 0 && !searching && (
          <div className="p-6 text-center text-sm text-gray-600">No matches.</div>
        )}
      </div>
    );
  }

  if (view === "timeline") {
    return (
      <div className="flex-1 overflow-y-auto">
        <div className="border-b border-border px-3 py-2 text-xs text-gray-500">{timeline.length} events</div>
        {timeline.map((e) => (
          <div key={`${e.event_type}-${e.id}`} className="flex gap-3 border-b border-border/40 px-3 py-2 text-xs">
            <span className="w-36 shrink-0 text-gray-500">{fmtTime(e.timestamp)}</span>
            <span className="w-5 shrink-0 text-center">{EVENT_ICON[e.event_type] || "•"}</span>
            <span className={`flex-1 ${e.event_type === "anomaly" ? "text-warn" : "text-gray-300"}`}>{e.summary}</span>
          </div>
        ))}
      </div>
    );
  }

  if (view === "communications") {
    return (
      <div className="flex flex-1 flex-col">
        <div className="flex gap-1 border-b border-border px-2 py-1.5">
          {(["messages", "calls", "contacts"] as CommTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setCommTab(t)}
              className={`rounded px-3 py-1 text-xs capitalize ${commTab === t ? "bg-accent/20 text-accent" : "text-gray-400 hover:bg-panel3"}`}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto">
          {commTab === "messages" &&
            messages.map((m) => (
              <div key={m.id} className="border-b border-border/40 px-3 py-2 text-xs">
                <div className="mb-0.5 flex gap-2 text-gray-500">
                  <span>{fmtTime(m.timestamp)}</span>
                  <span className="text-gray-600">[{m.app}]</span>
                  <span>
                    {m.sender} → {m.recipient}
                  </span>
                </div>
                <div className="text-gray-300">{m.body}</div>
              </div>
            ))}
          {commTab === "calls" &&
            calls.map((c) => (
              <div key={c.id} className="flex gap-3 border-b border-border/40 px-3 py-2 text-xs">
                <span className="w-36 text-gray-500">{fmtTime(c.timestamp)}</span>
                <span className="w-20 capitalize text-gray-400">{c.direction}</span>
                <span className="flex-1 text-gray-300">{c.number}</span>
                <span className="text-gray-500">{c.duration_seconds}s</span>
              </div>
            ))}
          {commTab === "contacts" &&
            contacts.map((c) => (
              <div key={c.id} className="flex gap-3 border-b border-border/40 px-3 py-2 text-xs">
                <span className="flex-1 text-gray-300">{c.name || "(unnamed)"}</span>
                <span className="text-gray-500">{c.phone_number}</span>
              </div>
            ))}
        </div>
      </div>
    );
  }

  if (view === "triage") {
    return (
      <div className="flex flex-1 flex-col">
        <div className="flex items-center gap-1 border-b border-border px-2 py-1.5">
          {(["faces", "anomalies", "nsfw"] as TriageTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTriageTab(t)}
              className={`rounded px-3 py-1 text-xs capitalize ${triageTab === t ? "bg-accent/20 text-accent" : "text-gray-400 hover:bg-panel3"}`}
            >
              {t === "nsfw" ? "NSFW review" : t}
            </button>
          ))}
          {triageTab === "faces" && (
            <button
              onClick={async () => {
                setReclustering(true);
                try {
                  await onRecluster();
                } finally {
                  setReclustering(false);
                }
              }}
              className="ml-auto rounded border border-border px-2 py-1 text-[11px] text-gray-400 hover:bg-panel3 disabled:opacity-50"
              disabled={reclustering}
            >
              {reclustering ? "Re-clustering…" : "Re-cluster faces"}
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto">
          {triageTab === "faces" && (
            <div className="grid grid-cols-4 gap-3 p-3">
              {people.length === 0 && (
                <div className="col-span-4 py-8 text-center text-xs text-gray-600">
                  No face clusters yet — install torch + facenet-pytorch and re-ingest, or click &quot;Re-cluster faces&quot;.
                </div>
              )}
              {people.map((p) => (
                <PersonCard key={p.id} caseId={caseId} person={p} evidence={evidence} onLabel={onLabelPerson} />
              ))}
            </div>
          )}
          {triageTab === "anomalies" && (
            <div>
              {timeline
                .filter((e) => e.event_type === "anomaly")
                .map((e) => (
                  <div key={e.id} className="flex gap-3 border-b border-border/40 px-3 py-2 text-xs">
                    <span className="w-36 text-gray-500">{fmtTime(e.timestamp)}</span>
                    <span className="text-warn">{e.summary}</span>
                  </div>
                ))}
            </div>
          )}
          {triageTab === "nsfw" && (
            <div>
              {evidence
                .filter((e) => e.nsfw_flagged)
                .map((e) => (
                  <div
                    key={e.id}
                    className="flex cursor-pointer items-center gap-3 border-b border-border/40 px-3 py-2 text-xs hover:bg-panel2"
                    onClick={() => setSelectedEvidence(e)}
                  >
                    <span className="flex-1 text-gray-300">{e.file_name}</span>
                    <span className="text-gray-500">score {e.nsfw_score?.toFixed(2)}</span>
                    <span className={e.nsfw_reviewed ? "text-good" : "text-warn"}>
                      {e.nsfw_reviewed ? "reviewed" : "pending review"}
                    </span>
                  </div>
                ))}
              {evidence.filter((e) => e.nsfw_flagged).length === 0 && (
                <div className="py-8 text-center text-xs text-gray-600">Nothing flagged.</div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // view === "evidence"
  return (
    <div className="flex flex-1 flex-col">
      <div className="flex items-center gap-1 border-b border-border px-2 py-1.5">
        {(["table", "thumbnail", "cluster"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setEvidenceView(t)}
            className={`rounded px-3 py-1 text-xs capitalize ${evidenceView === t ? "bg-accent/20 text-accent" : "text-gray-400 hover:bg-panel3"}`}
          >
            {t === "cluster" ? "Cluster grid" : t}
          </button>
        ))}
        <span className="ml-3 text-xs text-gray-600">{evidenceFilter.label}</span>
        <span className="ml-auto text-xs text-gray-500">{filteredEvidence.length} results</span>
      </div>

      <div className="flex-1 overflow-auto">
        {evidenceView === "table" && (
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-panel text-gray-500">
              <tr>
                <th className="px-3 py-1.5 font-medium">Name</th>
                <th className="px-3 py-1.5 font-medium">Hash</th>
                <th className="px-3 py-1.5 font-medium">AI</th>
                <th className="px-3 py-1.5 font-medium">Location</th>
                <th className="px-3 py-1.5 font-medium">Modified</th>
                <th className="px-3 py-1.5 font-medium">Size</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvidence.map((e) => (
                <tr
                  key={e.id}
                  onClick={() => setSelectedEvidence(e)}
                  className={`cursor-pointer border-t border-border/40 hover:bg-panel2 ${
                    selectedEvidence?.id === e.id ? "bg-[#103a44]" : ""
                  }`}
                >
                  <td className="px-3 py-1.5 text-gray-200">{e.file_name}</td>
                  <td className="px-3 py-1.5 font-mono text-gray-500">{shortHash(e.sha256)}</td>
                  <td className="px-3 py-1.5">
                    <AiBadges evidence={e} />
                  </td>
                  <td className="max-w-[220px] truncate px-3 py-1.5 text-gray-500">{e.original_path}</td>
                  <td className="px-3 py-1.5 text-gray-500">{fmtTime(e.captured_at || e.created_at)}</td>
                  <td className="px-3 py-1.5 text-gray-500">{fmtBytes(e.size_bytes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {evidenceView === "thumbnail" && (
          <div className="grid grid-cols-6 gap-3 p-3">
            {filteredEvidence
              .filter((e) => e.kind === "photo")
              .map((e) => (
                <Thumbnail key={e.id} caseId={caseId} evidence={e} selected={selectedEvidence?.id === e.id} onClick={() => setSelectedEvidence(e)} />
              ))}
            {filteredEvidence.filter((e) => e.kind !== "photo").length > 0 && (
              <div className="col-span-6 mt-2 text-[11px] text-gray-600">
                {filteredEvidence.filter((e) => e.kind !== "photo").length} non-image file(s) hidden from thumbnail view — see Table.
              </div>
            )}
          </div>
        )}

        {evidenceView === "cluster" && (
          <div className="grid grid-cols-4 gap-3 p-3">
            {people.map((p) => (
              <PersonCard key={p.id} caseId={caseId} person={p} evidence={evidence} onLabel={onLabelPerson} />
            ))}
            {people.length === 0 && (
              <div className="col-span-4 py-8 text-center text-xs text-gray-600">No face clusters for this case yet.</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function AiBadges({ evidence }: { evidence: EvidenceFile }) {
  const badges: { label: string; cls: string }[] = [];
  if (evidence.kind === "photo") badges.push({ label: "face", cls: "text-accent" });
  if (evidence.kind === "audio") badges.push({ label: "speech", cls: "text-accent" });
  if (evidence.nsfw_flagged) badges.push({ label: "nsfw", cls: "text-bad" });
  if (evidence.deleted_then_recovered) badges.push({ label: "recovered", cls: "text-warn" });
  if (badges.length === 0) return <span className="text-gray-600">—</span>;
  return (
    <span className="flex gap-2">
      {badges.map((b) => (
        <span key={b.label} className={b.cls}>
          {b.label}
        </span>
      ))}
    </span>
  );
}

function Thumbnail({
  caseId,
  evidence,
  selected,
  onClick,
}: {
  caseId: number;
  evidence: EvidenceFile;
  selected: boolean;
  onClick: () => void;
}) {
  const { url, loading } = useAuthedBlobUrl(api.evidenceFileUrl(caseId, evidence.id));
  return (
    <div
      onClick={onClick}
      className={`cursor-pointer overflow-hidden rounded border ${selected ? "border-accent" : "border-border"} bg-panel2`}
    >
      <div className="flex h-24 items-center justify-center bg-black/30">
        {loading && <span className="text-[10px] text-gray-600">loading…</span>}
        {url && <img src={url} alt={evidence.file_name} className="h-full w-full object-cover" />}
      </div>
      <div className="truncate px-1.5 py-1 text-[10px] text-gray-400">{evidence.file_name}</div>
    </div>
  );
}

function PersonCard({
  caseId,
  person,
  evidence,
  onLabel,
}: {
  caseId: number;
  person: Person;
  evidence: EvidenceFile[];
  onLabel: (id: number, label: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(person.label);
  // best effort: representative face's evidence isn't directly resolvable client-side without
  // the face row, so we just show a person icon placeholder plus stats.
  return (
    <div className="rounded border border-border bg-panel2 p-3 text-xs">
      <div className="mb-2 flex h-20 items-center justify-center rounded bg-black/30 text-3xl text-gray-400">⊕</div>
      {editing ? (
        <input
          autoFocus
          className="mb-1 w-full rounded border border-border bg-panel px-1.5 py-1 text-xs text-white outline-none focus:border-accent"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          onBlur={async () => {
            setEditing(false);
            await onLabel(person.id, label);
          }}
          onKeyDown={async (e) => {
            if (e.key === "Enter") {
              setEditing(false);
              await onLabel(person.id, label);
            }
          }}
        />
      ) : (
        <div className="mb-1 cursor-text truncate text-gray-200" onClick={() => setEditing(true)}>
          {person.label || `Unlabeled cluster #${person.cluster_key}`}
        </div>
      )}
      <div className="text-gray-500">{person.face_count} face(s)</div>
    </div>
  );
}
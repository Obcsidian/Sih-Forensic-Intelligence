"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type {
  AuditLogEntry,
  AuthResponse,
  Call,
  Case,
  ChainVerification,
  Contact,
  DataSource,
  EvidenceFile,
  EvidenceKind,
  Message,
  Person,
  SearchHit,
  TimelineEvent,
  Transcript,
} from "@/lib/types";
import TopBar from "./TopBar";
import TreeSidebar from "./TreeSidebar";
import CenterPanel from "./CenterPanel";
import PreviewPane from "./PreviewPane";
import MetadataPanel from "./MetadataPanel";
import StatusBar from "./StatusBar";
import NewCaseDialog from "./NewCaseDialog";
import AddDataSourceDialog from "./AddDataSourceDialog";
import LoginScreen from "./LoginScreen";

export type ViewMode = "evidence" | "communications" | "timeline" | "triage" | "search";
export type TriageTab = "faces" | "anomalies" | "nsfw";
export type CommTab = "contacts" | "calls" | "messages";

export interface EvidenceFilter {
  kinds?: EvidenceKind[];
  onlyGeotagged?: boolean;
  onlyDeletedRecovered?: boolean;
  label: string;
}

const ALL_EVIDENCE_FILTER: EvidenceFilter = { label: "All evidence" };

export default function Workspace() {
  const [auth, setAuth] = useState<AuthResponse | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  const [cases, setCases] = useState<Case[]>([]);
  const [activeCase, setActiveCase] = useState<Case | null>(null);
  const [showNewCaseDialog, setShowNewCaseDialog] = useState(false);
  const [showAddDataSourceDialog, setShowAddDataSourceDialog] = useState(false);
  const [chain, setChain] = useState<ChainVerification | null>(null);

  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [evidence, setEvidence] = useState<EvidenceFile[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [calls, setCalls] = useState<Call[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [audit, setAudit] = useState<AuditLogEntry[]>([]);
  const [caseLoading, setCaseLoading] = useState(false);

  const [view, setView] = useState<ViewMode>("evidence");
  const [evidenceFilter, setEvidenceFilter] = useState<EvidenceFilter>(ALL_EVIDENCE_FILTER);
  const [triageTab, setTriageTab] = useState<TriageTab>("faces");
  const [commTab, setCommTab] = useState<CommTab>("messages");

  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceFile | null>(null);
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);

  const [reportBusy, setReportBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  // restore session on load
  useEffect(() => {
    const token = typeof window !== "undefined" ? window.localStorage.getItem("netsherlock_token") : null;
    if (!token) {
      setAuthChecked(true);
      return;
    }
    api
      .me()
      .then((me) => setAuth({ ...me, access_token: token }))
      .catch(() => {
        // token expired/invalid
      })
      .finally(() => setAuthChecked(true));
  }, []);

  const loadCases = useCallback(async () => {
    const list = await api.listCases();
    setCases(list);
    return list;
  }, []);

  useEffect(() => {
    if (!auth) return;
    loadCases().catch(() => setToast("Could not load cases"));
    api.verifyAudit().then(setChain).catch(() => {});
  }, [auth, loadCases]);

  const loadCaseData = useCallback(async (caseId: number) => {
    setCaseLoading(true);
    try {
      const [ev, ppl, tr, ct, cl, ms, tl, au, ds] = await Promise.all([
        api.listEvidence(caseId),
        api.listPeople(caseId),
        api.listTranscripts(caseId),
        api.listContacts(caseId),
        api.listCalls(caseId),
        api.listMessages(caseId),
        api.listTimeline(caseId),
        api.listAudit(caseId),
        api.listDataSources(caseId),
      ]);
      setEvidence(ev);
      setPeople(ppl);
      setTranscripts(tr);
      setContacts(ct);
      setCalls(cl);
      setMessages(ms);
      setTimeline(tl);
      setAudit(au);
      setDataSources(ds);
    } finally {
      setCaseLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!activeCase) return;
    loadCaseData(activeCase.id);
    api.verifyAudit().then(setChain).catch(() => {});
  }, [activeCase, loadCaseData]);

  function handleLoggedIn(a: AuthResponse) {
    setAuth(a);
  }

  function handleLogout() {
    window.localStorage.removeItem("netsherlock_token");
    setAuth(null);
    setActiveCase(null);
    setCases([]);
  }

  function handleNavigate(v: ViewMode, opts?: { evidenceFilter?: EvidenceFilter; triageTab?: TriageTab; commTab?: CommTab }) {
    setView(v);
    setSelectedEvidence(null);
    if (opts?.evidenceFilter) setEvidenceFilter(opts.evidenceFilter);
    else if (v === "evidence") setEvidenceFilter(ALL_EVIDENCE_FILTER);
    if (opts?.triageTab) setTriageTab(opts.triageTab);
    if (opts?.commTab) setCommTab(opts.commTab);
  }

  async function handleSearchSubmit() {
    if (!activeCase || !searchQuery.trim()) return;
    setView("search");
    setSearching(true);
    try {
      const hits = await api.search(activeCase.id, searchQuery.trim());
      setSearchResults(hits);
    } catch (err) {
      setToast(err instanceof ApiError ? err.message : "Search failed (is sentence-transformers installed?)");
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function handleGenerateReport() {
    if (!activeCase) return;
    setReportBusy(true);
    try {
      const report = await api.generateReport(activeCase.id, false);
      const url = `${api.API_URL}${api.reportDownloadUrl(activeCase.id, report.id, "html")}`;
      setToast(`Report generated — opening ${url}`);
      window.open(url, "_blank");
    } catch (err) {
      setToast(err instanceof ApiError ? err.message : "Report generation failed");
    } finally {
      setReportBusy(false);
    }
  }

  async function refreshCase() {
    if (!activeCase) return;
    const fresh = await api.getCase(activeCase.id);
    setActiveCase(fresh);
    await loadCaseData(activeCase.id);
  }

  if (!authChecked) {
    return <div className="flex h-screen items-center justify-center bg-[#0b0d12] text-gray-500">Loading…</div>;
  }

  if (!auth) {
    return <LoginScreen onLoggedIn={handleLoggedIn} />;
  }

  if (!activeCase) {
    return (
      <>
        <CaseChooser
          cases={cases}
          onOpen={(c) => setActiveCase(c)}
          onNew={() => setShowNewCaseDialog(true)}
          onLogout={handleLogout}
          username={auth.username}
          role={auth.role}
        />
        {showNewCaseDialog && (
          <NewCaseDialog
            onClose={() => setShowNewCaseDialog(false)}
            onCreated={async (c) => {
              setShowNewCaseDialog(false);
              await loadCases();
              setActiveCase(c);
            }}
          />
        )}
      </>
    );
  }

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#0b0d12] text-gray-200">
      <TopBar
        activeCase={activeCase}
        chain={chain}
        view={view}
        setView={(v) => handleNavigate(v)}
        onAddDataSource={() => setShowAddDataSourceDialog(true)}
        onCloseCase={() => setActiveCase(null)}
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        onSearchSubmit={handleSearchSubmit}
        onGenerateReport={handleGenerateReport}
        reportBusy={reportBusy}
        role={auth.role}
        username={auth.username}
        onLogout={handleLogout}
      />

      <div className="flex min-h-0 flex-1">
        <TreeSidebar
          dataSources={dataSources}
          evidence={evidence}
          people={people}
          transcripts={transcripts}
          timeline={timeline}
          contacts={contacts}
          calls={calls}
          messages={messages}
          activeView={view}
          activeFilterLabel={evidenceFilter.label}
          onNavigate={handleNavigate}
          onAddDataSource={() => setShowAddDataSourceDialog(true)}
        />

        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex min-h-0 flex-1">
            <div className="flex min-h-0 flex-[3] flex-col border-r border-border">
              <CenterPanel
                caseId={activeCase.id}
                view={view}
                evidence={evidence}
                evidenceFilter={evidenceFilter}
                people={people}
                triageTab={triageTab}
                setTriageTab={setTriageTab}
                commTab={commTab}
                setCommTab={setCommTab}
                contacts={contacts}
                calls={calls}
                messages={messages}
                timeline={timeline}
                transcripts={transcripts}
                searchResults={searchResults}
                searching={searching}
                selectedEvidence={selectedEvidence}
                setSelectedEvidence={setSelectedEvidence}
                selectedPerson={selectedPerson}
                setSelectedPerson={setSelectedPerson}
                onLabelPerson={async (personId, label) => {
                  await api.labelPerson(activeCase.id, personId, label);
                  const ppl = await api.listPeople(activeCase.id);
                  setPeople(ppl);
                }}
                onRecluster={async () => {
                  await api.recluster(activeCase.id);
                  await refreshCase();
                }}
                loading={caseLoading}
              />
            </div>

            <MetadataPanel
              caseId={activeCase.id}
              evidence={selectedEvidence}
              people={people}
              onMarkNsfwReviewed={async (id) => {
                await api.markNsfwReviewed(activeCase.id, id);
                const ev = await api.listEvidence(activeCase.id);
                setEvidence(ev);
                setSelectedEvidence(ev.find((e) => e.id === id) || null);
              }}
            />
          </div>

          <PreviewPane
            caseId={activeCase.id}
            evidence={selectedEvidence}
            transcripts={transcripts}
            people={people}
            audit={audit}
          />
        </div>
      </div>

      <StatusBar evidence={evidence} chain={chain} caseStatus={activeCase.status} />

      {showNewCaseDialog && (
        <NewCaseDialog
          onClose={() => setShowNewCaseDialog(false)}
          onCreated={async (c) => {
            setShowNewCaseDialog(false);
            await loadCases();
            setActiveCase(c);
          }}
        />
      )}

      {showAddDataSourceDialog && (
        <AddDataSourceDialog
          caseId={activeCase.id}
          onClose={() => setShowAddDataSourceDialog(false)}
          onIngested={async () => {
            setShowAddDataSourceDialog(false);
            await refreshCase();
          }}
        />
      )}

      {toast && (
        <div
          className="fixed bottom-10 right-4 max-w-sm rounded border border-border bg-panel2 px-4 py-2 text-xs text-gray-200 shadow-xl"
          onClick={() => setToast(null)}
        >
          {toast}
        </div>
      )}
    </div>
  );
}

function CaseChooser({
  cases,
  onOpen,
  onNew,
  onLogout,
  username,
  role,
}: {
  cases: Case[];
  onOpen: (c: Case) => void;
  onNew: () => void;
  onLogout: () => void;
  username: string;
  role: string;
}) {
  return (
    <div className="flex h-screen w-screen flex-col bg-[#0b0d12] text-gray-200">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded bg-accent/20 text-accent">◆</span>
          <span className="font-semibold text-white">NetSherlock</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-400">
          <span>
            {username} ({role})
          </span>
          <button onClick={onLogout} className="hover:text-gray-200">
            Sign out
          </button>
        </div>
      </div>

      <div className="mx-auto mt-16 w-[560px]">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-white">Cases</h1>
          <button onClick={onNew} className="rounded bg-accent px-3 py-1.5 text-xs font-semibold text-black hover:bg-accent/90">
            + New case
          </button>
        </div>

        {cases.length === 0 ? (
          <div className="rounded border border-dashed border-border p-8 text-center text-sm text-gray-500">
            No cases yet. Click &quot;New case&quot; to ingest a case-export folder (see{" "}
            <code className="text-gray-400">sample_case/</code>).
          </div>
        ) : (
          <div className="space-y-2">
            {cases.map((c) => (
              <button
                key={c.id}
                onClick={() => onOpen(c)}
                className="flex w-full items-center justify-between rounded border border-border bg-panel px-4 py-3 text-left hover:border-accent/50 hover:bg-panel2"
              >
                <div>
                  <div className="text-sm font-medium text-white">
                    Case {c.id} · {c.name}
                  </div>
                  <div className="text-xs text-gray-500">{c.source_path}</div>
                </div>
                <span
                  className={`rounded px-2 py-0.5 text-[10px] uppercase tracking-wide ${
                    c.status === "ready"
                      ? "bg-good/15 text-good"
                      : c.status === "failed"
                      ? "bg-bad/15 text-bad"
                      : "bg-warn/15 text-warn"
                  }`}
                >
                  {c.status}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

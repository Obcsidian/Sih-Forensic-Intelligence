"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type {
  AuditLogEntry,
  AuthResponse,
  Call,
  Case,
  ChainVerification,
  Contact,
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
  const router = useRouter();
  const [auth, setAuth] = useState<AuthResponse | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  
  const [cases, setCases] = useState<Case[]>([]);
  const [activeCase, setActiveCase] = useState<Case | null>(null);
  const [showNewCaseDialog, setShowNewCaseDialog] = useState(false);
  const [chain, setChain] = useState<ChainVerification | null>(null);
  
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
  
  useEffect(() => {
    const token = localStorage.getItem("forensai_token");
    if (!token) { router.push("/landing"); return; }
    api.me().then((me) => setAuth({ ...me, access_token: token })).catch(() => { router.push("/landing"); }).finally(() => setAuthChecked(true));
  }, [router]);
  
  const loadCases = useCallback(async () => {
    const list = await api.listCases();
    setCases(list);
    return list;
  }, []);
  
  const loadCaseData = useCallback(async (caseId: number) => {
    setCaseLoading(true);
    try {
      const [ev, ppl, tr, ct, cl, ms, tl, au] = await Promise.all([
        api.listEvidence(caseId), api.listPeople(caseId), api.listTranscripts(caseId),
        api.listContacts(caseId), api.listCalls(caseId), api.listMessages(caseId),
        api.listTimeline(caseId), api.listAudit(caseId),
      ]);
      setEvidence(ev); setPeople(ppl); setTranscripts(tr); setContacts(ct);
      setCalls(cl); setMessages(ms); setTimeline(tl); setAudit(au);
    } finally { setCaseLoading(false); }
  }, []);
  
  useEffect(() => {
    if (!auth) return;
    loadCases().catch(() => setToast("Could not load cases"));
    api.verifyAudit().then(setChain).catch(() => {});
  }, [auth, loadCases]);
  
  useEffect(() => {
    if (!activeCase) return;
    loadCaseData(activeCase.id);
    api.verifyAudit().then(setChain).catch(() => {});
  }, [activeCase, loadCaseData]);
  
  function handleLoggedIn(a: AuthResponse) { setAuth(a); }
function handleLogout() {
    localStorage.removeItem("forensai_token");
    localStorage.removeItem("forensai_username");
    localStorage.removeItem("forensai_role");
    setAuth(null); setActiveCase(null); setCases([]);
    router.push("/landing");
  }
  
  function handleNavigate(v: ViewMode, opts?: { evidenceFilter?: EvidenceFilter; triageTab?: TriageTab; commTab?: CommTab }) {
    setView(v); setSelectedEvidence(null);
    if (opts?.evidenceFilter) setEvidenceFilter(opts.evidenceFilter);
    else if (v === "evidence") setEvidenceFilter(ALL_EVIDENCE_FILTER);
    if (opts?.triageTab) setTriageTab(opts.triageTab);
    if (opts?.commTab) setCommTab(opts.commTab);
  }
  
  async function handleSearchSubmit() {
    if (!activeCase || !searchQuery.trim()) return;
    setView("search"); setSearching(true);
    try { setSearchResults(await api.search(activeCase.id, searchQuery.trim())); }
    catch (err) { setToast(err instanceof ApiError ? err.message : "Search failed"); setSearchResults([]); }
    finally { setSearching(false); }
  }
  
  async function handleGenerateReport() {
    if (!activeCase) return;
    setReportBusy(true);
    try {
      const report = await api.generateReport(activeCase.id, false);
      setToast("Report generated");
      window.open(`${api.API_URL}${api.reportDownloadUrl(activeCase.id, report.id, "html")}`, "_blank");
    } catch (err) { setToast(err instanceof ApiError ? err.message : "Report failed"); }
    finally { setReportBusy(false); }
  }
  
  async function refreshCase() {
    if (!activeCase) return;
    const fresh = await api.getCase(activeCase.id);
    setActiveCase(fresh);
    await loadCaseData(activeCase.id);
  }
  
if (!authChecked) return (
    <div className="flex h-screen items-center justify-center bg-[#0b0d12]">
      <div className="flex flex-col items-center gap-3">
        <div className="flex h-8 w-8 animate-spin items-center justify-center rounded-full border-2 border-cyan-400/30 border-t-cyan-400" />
        <div className="text-xs text-gray-500">Loading...</div>
      </div>
    </div>
  );
  if (!auth) return null;
  if (!activeCase) {
    return (
      <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#0b0d12] text-gray-200">
        {/* Header */}
        <header className="flex shrink-0 items-center justify-between border-b border-white/5 bg-white/[0.02] px-8 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400/15 text-lg text-cyan-300 shadow-[0_0_20px_rgba(34,211,238,0.2)]">
              ◆
            </div>
            <div>
              <div className="text-base font-bold text-white">ForensAI</div>
              <div className="text-[10px] uppercase tracking-wider text-gray-500">Forensic Intelligence Platform</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3.5 py-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
              <span className="text-xs font-medium text-gray-200">{auth.username}</span>
              <span className="text-[10px] uppercase tracking-wider text-gray-500">({auth.role})</span>
            </div>
            <button onClick={handleLogout} className="rounded-lg border border-white/5 bg-white/5 px-4 py-1.5 text-xs font-medium text-gray-400 transition-all hover:border-cyan-400/30 hover:text-cyan-300">
              Sign Out
            </button>
          </div>
        </header>

        {/* Main content */}
        <main className="flex flex-1 items-start justify-center overflow-y-auto px-8 py-12">
          <div className="w-full max-w-5xl">
            {/* Title section */}
            <div className="mb-8 flex items-end justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold text-white">Cases</h1>
                <p className="mt-2 text-sm text-gray-500">Select a case to begin investigation</p>
              </div>
              <button onClick={() => setShowNewCaseDialog(true)} className="liquid-btn flex items-center gap-2 px-5 py-2.5 text-sm font-semibold">
                <span className="text-base">+</span>
                <span>New Case</span>
              </button>
            </div>

            {/* Cases grid */}
            {cases.length === 0 ? (
              <div className="glass-card flex flex-col items-center justify-center py-20 text-center">
                <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-2xl bg-cyan-400/10 text-4xl text-cyan-300">
                  ⧉
                </div>
                <div className="text-base font-semibold text-gray-300">No cases yet</div>
                <div className="mt-2 max-w-sm text-sm text-gray-600">Create your first case to start investigating digital evidence</div>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {cases.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setActiveCase(c)}
                    className="glass-card group flex h-full flex-col gap-4 p-5 text-left transition-all hover:border-cyan-400/40 hover:shadow-[0_0_30px_rgba(34,211,238,0.1)]"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-cyan-400/10 text-xl text-cyan-300">
                        {c.status === "ready" ? "◉" : c.status === "failed" ? "⊘" : "◌"}
                      </div>
                      <span className={`status-badge ${c.status === "ready" ? "status-good" : c.status === "failed" ? "status-bad" : "status-warn"}`}>
                        {c.status}
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold text-white">{c.name}</div>
                      <div className="mt-1 truncate text-[11px] text-gray-500">{c.source_path}</div>
                    </div>
                    <div className="flex items-center justify-between border-t border-white/5 pt-3 text-[10px] text-gray-600">
                      <span>Case #{c.id}</span>
                      <span className="opacity-0 transition-opacity group-hover:opacity-100">Open →</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </main>

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
      </div>
    );
  }
  
  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#0b0d12] text-gray-200">
      <TopBar activeCase={activeCase} chain={chain} view={view} setView={handleNavigate} onAddDataSource={() => setShowNewCaseDialog(true)} onCloseCase={() => setActiveCase(null)} searchQuery={searchQuery} onSearchQueryChange={setSearchQuery} onSearchSubmit={handleSearchSubmit} onGenerateReport={handleGenerateReport} reportBusy={reportBusy} role={auth.role} username={auth.username} onLogout={handleLogout} />
      <div className="flex min-h-0 flex-1">
        <TreeSidebar sourcePath={activeCase.source_path} caseStatus={activeCase.status} evidence={evidence} people={people} transcripts={transcripts} timeline={timeline} contacts={contacts} calls={calls} messages={messages} activeView={view} activeFilterLabel={evidenceFilter.label} onNavigate={handleNavigate} />
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex min-h-0 flex-1">
            <div className="flex min-h-0 flex-[3] flex-col border-r border-border">
              <CenterPanel caseId={activeCase.id} view={view} evidence={evidence} evidenceFilter={evidenceFilter} people={people} triageTab={triageTab} setTriageTab={setTriageTab} commTab={commTab} setCommTab={setCommTab} contacts={contacts} calls={calls} messages={messages} timeline={timeline} transcripts={transcripts} searchResults={searchResults} searching={searching} selectedEvidence={selectedEvidence} setSelectedEvidence={setSelectedEvidence} selectedPerson={selectedPerson} setSelectedPerson={setSelectedPerson} onLabelPerson={async (personId, label) => { await api.labelPerson(activeCase.id, personId, label); setPeople(await api.listPeople(activeCase.id)); }} onRecluster={async () => { await api.recluster(activeCase.id); await refreshCase(); }} loading={caseLoading} />
            </div>
            <MetadataPanel caseId={activeCase.id} evidence={selectedEvidence} people={people} onMarkNsfwReviewed={async (id) => { await api.markNsfwReviewed(activeCase.id, id); setEvidence(await api.listEvidence(activeCase.id)); setSelectedEvidence((await api.listEvidence(activeCase.id)).find(e => e.id === id) || null); }} />
          </div>
          <PreviewPane caseId={activeCase.id} evidence={selectedEvidence} transcripts={transcripts} people={people} audit={audit} />
        </div>
      </div>
      <StatusBar evidence={evidence} chain={chain} caseStatus={activeCase.status} />
      {showNewCaseDialog && <NewCaseDialog onClose={() => setShowNewCaseDialog(false)} onCreated={async (c) => { setShowNewCaseDialog(false); await loadCases(); setActiveCase(c); }} />}
      {toast && <div className="toast-notification fixed bottom-10 right-4 max-w-sm px-4 py-2 text-xs text-gray-200 cursor-pointer" onClick={() => setToast(null)}>{toast}</div>}
    </div>
  );
}

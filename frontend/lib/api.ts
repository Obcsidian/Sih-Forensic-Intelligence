import type {
  AuditLogEntry,
  AuthResponse,
  Call,
  Case,
  ChainVerification,
  Contact,
  EvidenceFile,
  FaceDetection,
  Graph,
  IngestSummary,
  Message,
  Person,
  ProcessCaseResult,
  Report,
  SearchHit,
  TimelineEvent,
  Transcript,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const TOKEN_KEY = "forensai_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (
    init?.body &&
    !(init.body instanceof URLSearchParams) &&
    !(init.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function fetchProtectedBlob(path: string): Promise<Blob> {
  const token = getToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_URL}${path}`, { headers });
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  return res.blob();
}

export async function fetchProtectedBytes(path: string, maxBytes = 512): Promise<Uint8Array> {
  const token = getToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  headers.set("Range", `bytes=0-${maxBytes - 1}`);
  const res = await fetch(`${API_URL}${path}`, { headers });
  if (!res.ok && res.status !== 206) throw new ApiError(res.status, res.statusText);
  const buf = await res.arrayBuffer();
  return new Uint8Array(buf).slice(0, maxBytes);
}

export const api = {
  API_URL,

  async login(username: string, password: string): Promise<AuthResponse> {
    const body = new URLSearchParams();
    body.set("username", username);
    body.set("password", password);
    return request<AuthResponse>("/auth/login", { method: "POST", body });
  },
  me: () => request<AuthResponse>("/auth/me"),

  listCases: () => request<Case[]>("/cases"),
  getCase: (id: number) => request<Case>(`/cases/${id}`),
  createCase: (data: { name: string; description?: string; source_path: string }) =>
    request<Case>("/cases", { method: "POST", body: JSON.stringify(data) }),
  uploadCase: (data: { name: string; description?: string; files: File[] }) => {
    const form = new FormData();
    form.set("name", data.name);
    if (data.description) form.set("description", data.description);
    for (const f of data.files) form.append("files", f);
    return request<Case>("/cases/upload", { method: "POST", body: form });
  },
  ingestCase: (id: number) => request<IngestSummary>(`/cases/${id}/ingest`, { method: "POST" }),

  listEvidence: (caseId: number, nsfwFlagged?: boolean) =>
    request<EvidenceFile[]>(
      `/cases/${caseId}/evidence${nsfwFlagged !== undefined ? `?nsfw_flagged=${nsfwFlagged}` : ""}`
    ),
  evidenceFileUrl: (caseId: number, evidenceId: number) => `/cases/${caseId}/evidence/${evidenceId}/file`,
  markNsfwReviewed: (caseId: number, evidenceId: number) =>
    request<EvidenceFile>(`/cases/${caseId}/evidence/${evidenceId}/nsfw-review`, { method: "POST" }),

  listPeople: (caseId: number) => request<Person[]>(`/cases/${caseId}/people`),
  labelPerson: (caseId: number, personId: number, label: string) =>
    request<Person>(`/cases/${caseId}/people/${personId}`, {
      method: "PATCH",
      body: JSON.stringify({ label }),
    }),
  listFaces: (caseId: number, personId?: number) =>
    request<FaceDetection[]>(`/cases/${caseId}/faces${personId !== undefined ? `?person_id=${personId}` : ""}`),
  recluster: (caseId: number) => request<{ people_found: number }>(`/cases/${caseId}/faces/recluster`, { method: "POST" }),

  listTranscripts: (caseId: number, q?: string) =>
    request<Transcript[]>(`/cases/${caseId}/transcripts${q ? `?q=${encodeURIComponent(q)}` : ""}`),

  search: (caseId: number, query: string, topK = 15) =>
    request<SearchHit[]>(`/cases/${caseId}/search`, {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK }),
    }),

  listTimeline: (caseId: number) => request<TimelineEvent[]>(`/cases/${caseId}/timeline`),

  listAnomalies: (caseId: number) => request<TimelineEvent[]>(`/cases/${caseId}/anomalies`),
  recomputeAnomalies: (caseId: number) =>
    request<TimelineEvent[]>(`/cases/${caseId}/anomalies/recompute`, { method: "POST" }),

  getGraph: (caseId: number) => request<Graph>(`/cases/${caseId}/graph`),

  listContacts: (caseId: number) => request<Contact[]>(`/cases/${caseId}/contacts`),
  listCalls: (caseId: number) => request<Call[]>(`/cases/${caseId}/calls`),
  listMessages: (caseId: number) => request<Message[]>(`/cases/${caseId}/messages`),

  listReports: (caseId: number) => request<Report[]>(`/cases/${caseId}/reports`),
  generateReport: (caseId: number, redacted: boolean) =>
    request<Report>(`/cases/${caseId}/reports`, { method: "POST", body: JSON.stringify({ redacted }) }),
  reportDownloadUrl: (caseId: number, reportId: number, fmt: "html" | "pdf") =>
    `/cases/${caseId}/reports/${reportId}/download?fmt=${fmt}`,

  listAudit: (caseId?: number) => request<AuditLogEntry[]>(`/audit${caseId ? `?case_id=${caseId}` : ""}`),
  verifyAudit: () => request<ChainVerification>("/audit/verify"),
};

export type { ProcessCaseResult };

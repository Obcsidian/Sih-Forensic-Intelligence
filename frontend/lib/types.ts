export type Role = "investigator" | "reviewer" | "read_only";

export interface AuthResponse {
  access_token: string;
  token_type: string;
  role: Role;
  username: string;
}

export type CaseStatus = "created" | "ingesting" | "processing" | "ready" | "failed";

export interface Case {
  id: number;
  name: string;
  description: string;
  source_path: string;
  status: CaseStatus;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface IngestSummary {
  contacts: number;
  calls: number;
  messages: number;
  photos: number;
  videos: number;
  audio_files: number;
  device_events: number;
  errors: string[];
}

export type EvidenceKind = "photo" | "video" | "audio" | "document" | "other";

export interface EvidenceFile {
  id: number;
  case_id: number;
  kind: EvidenceKind;
  original_path: string;
  file_name: string;
  sha256: string;
  size_bytes: number;
  captured_at: string | null;
  latitude: number | null;
  longitude: number | null;
  deleted_then_recovered: boolean;
  nsfw_score: number | null;
  nsfw_flagged: boolean;
  nsfw_reviewed: boolean;
  created_at: string;
}

export interface Person {
  id: number;
  case_id: number;
  label: string;
  cluster_key: number;
  representative_face_id: number | null;
  face_count: number;
  created_at: string;
}

export interface FaceDetection {
  id: number;
  case_id: number;
  evidence_file_id: number;
  person_id: number | null;
  box_x: number;
  box_y: number;
  box_w: number;
  box_h: number;
  embedding_json: string;
  detection_confidence: number;
  created_at: string;
}

export interface Transcript {
  id: number;
  case_id: number;
  evidence_file_id: number;
  text: string;
  language: string;
  embedding_json: string | null;
  created_at: string;
}

export interface Contact {
  id: number;
  case_id: number;
  name: string;
  phone_number: string;
}

export type CallDirection = "incoming" | "outgoing" | "missed";

export interface Call {
  id: number;
  case_id: number;
  number: string;
  direction: CallDirection;
  duration_seconds: number;
  timestamp: string;
}

export interface Message {
  id: number;
  case_id: number;
  sender: string;
  recipient: string;
  body: string;
  timestamp: string;
  app: string;
  embedding_json: string | null;
}

export type TimelineEventType =
  | "call"
  | "message"
  | "photo"
  | "video"
  | "audio"
  | "app_install"
  | "app_uninstall"
  | "file_deleted"
  | "file_recovered"
  | "anomaly";

export interface TimelineEvent {
  id: number;
  case_id: number;
  event_type: TimelineEventType;
  timestamp: string;
  summary: string;
  source_table: string;
  source_id: number;
  latitude: number | null;
  longitude: number | null;
}

export interface SearchHit {
  source_type: "transcript" | "message";
  source_id: number;
  text: string;
  score: number;
}

export interface GraphNode {
  id: string;
  label: string;
  call_count: number;
  message_count: number;
}
export interface GraphEdge {
  source: string;
  target: string;
  weight: number;
}
export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Report {
  id: number;
  case_id: number;
  redacted: boolean;
  html_path: string;
  pdf_path: string | null;
  generated_by: number | null;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  case_id: number | null;
  actor: string;
  action: string;
  payload_json: string;
  timestamp: string;
  prev_hash: string;
  hash: string;
}

export interface ChainVerification {
  valid: boolean;
  total_entries: number;
  first_broken_entry_id: number | null;
  reason: string | null;
}

export interface ProcessCaseResult {
  faces_detected: number;
  people_found: number;
  transcripts_created: number;
  anomalies_found: number;
  nsfw_screened: number;
  warnings: string[];
}

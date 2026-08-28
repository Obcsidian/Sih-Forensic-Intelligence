# NetSherlock (working title)

**An open-source digital forensic investigation platform — Autopsy, reimagined with AI-driven triage and reporting.**

---

## 1. Problem Statement

Commercial digital forensics suites (Cellebrite, Magnet AXIOM) are powerful but expensive, closed-source, and out of reach for smaller labs, NGOs, independent investigators, and academic use. Meanwhile, open-source tools like Autopsy provide solid forensic parsing but lack modern AI-assisted triage — investigators still manually scroll through thousands of photos, hours of audio, and endless message threads.

**NetSherlock** forks Autopsy's proven forensic core and layers on AI capabilities — facial recognition, transcription, semantic search, and automated reporting — to drastically cut investigation time while preserving the forensic integrity (hashing, chain-of-custody) that makes evidence admissible.

---

## 2. Key Features

### Forensic Core (inherited / extended from Autopsy)
- UFDR and E01 extraction ingestion
- SHA-256 hashing at ingest + append-only, hash-chained audit log for tamper-evidence
- Chain-of-custody tracking
- Full Sleuth Kit (TSK) file system parsing

### AI-Augmented Capabilities
- **Facial Recognition & Clustering** — detect and cluster people across large photo/video collections to rapidly triage who appears in a case
- **Speech-to-Text** — transcribe call recordings and voice notes for full-text search, with automatic language detection and multi-language transcription (translation-to-English planned)
- **Text-to-Speech** — accessible audio playback of flagged evidence and case summaries for review
- **Automated Report Generation** — aggregates flagged evidence and AI outputs into structured, exportable documentation
- **Entity & Relationship Graph** — auto-extract contacts and phone numbers, visualize communication patterns as a graph
- **Timeline Reconstruction** — merges call logs, messages, and GPS/EXIF metadata into a single chronological view
- **Semantic Search** — embedding-based search across transcripts and messages (e.g. "conversations about money," not just exact keywords)
- **NSFW/CSAM Pre-Screening Flag** — flags media for priority human review (flag-only, never auto-classifies as evidence — see Limitations)
- **Redaction Tool** — blurs faces/names in exported reports for court disclosure
- **Anomaly Detection** — flags unusual patterns (e.g. deleted-then-recovered files, briefly installed apps)
- **Role-Based Access Control** — investigator / reviewer / read-only roles for legally sound chain-of-custody
- **Plugin Marketplace** — drop-in AI ingest modules built on Autopsy's Jython plugin framework

---

## 3. Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Forensic ingest & parsing | Autopsy (fork) + Sleuth Kit | Proven UFDR/E01 parsing, don't reinvent |
| Case database | SQLite (`.aut`) | Native Autopsy format, read-only access from AI layer |
| AI outputs storage | PostgreSQL | Keeps AI data separate from Autopsy's own DB |
| Backend API | FastAPI + Pydantic | Fast, typed, async-friendly |
| Background jobs | Celery + Redis | AI tasks (face clustering, transcription) are slow — don't block the API |
| ORM | SQLAlchemy / SQLModel | Clean DB layer over Postgres |
| Facial recognition | InsightFace (buffalo_l) + FAISS/HDBSCAN | Faster & more accurate than DeepFace at scale; clustering of embeddings |
| Speech-to-text | faster-whisper | Fast local transcription; `small`/`medium` for demo, `large-v3` for production |
| Text-to-speech | Piper / Coqui TTS | Lightweight and fast for demo reliability |
| Semantic search | sentence-transformers + vector index | Embedding search over transcripts/messages |
| Report generation | Jinja2 + WeasyPrint | HTML → PDF templating |
| Frontend | Next.js + Tailwind + shadcn/ui | Fast to build, clean UI components |
| Graph visualization | react-force-graph / d3 | Relationship and timeline views |
| Frontend state | Zustand / React Query | Simpler than Redux for a fast build cycle |
| Integrity | SHA-256 + hash-chained audit log | Tamper-evident chain-of-custody |

---

## 4. Architecture Overview

```
UFDR / E01 file
      │
      ▼
Autopsy Core (fork) ── ingests, parses, hashes ── writes to .aut (SQLite)
      │
      ▼
FastAPI + Celery/Redis AI Layer
  ├─ Facial Recognition (InsightFace + clustering)
  ├─ Speech-to-Text (faster-whisper)
  ├─ Text-to-Speech (Piper/Coqui)
  ├─ Semantic Search (embeddings)
  ├─ Anomaly Detection
  └─ Report Generator (Jinja2 + WeasyPrint)
      │
      ▼
PostgreSQL (AI outputs: clusters, transcripts, flags, reports)
      │
      ▼
Next.js + Tailwind Dashboard
  ├─ Face Cluster View
  ├─ Transcript Search
  ├─ Timeline & Relationship Graph
  ├─ Report Download/Preview
  └─ Role-Based Access Control
```

---

## 5. Setup & Installation

```bash
# 1. Clone and build the Autopsy fork
git clone <your-fork-url>
cd autopsy
# follow Autopsy build instructions (Java/Jython environment)

# 2. Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# start Redis + Celery worker
redis-server &
celery -A app.worker worker --loglevel=info &
uvicorn app.main:app --reload

# 3. Frontend
cd frontend
npm install
npm run dev
```

Sample dataset: *[link to sample UFDR/E01 test image]*

---

## 6. Usage Walkthrough

1. Ingest a UFDR/E01 case into Autopsy
2. Trigger AI processing (facial recognition, transcription) via the dashboard
3. Review face clusters and search transcripts
4. Explore the relationship graph and timeline
5. Generate and export a structured PDF/HTML report

*(Screenshots/GIF to be added here)*

---

## 7. Chain-of-Custody & Integrity Approach

Every ingested file is hashed (SHA-256) at acquisition time, matching Autopsy's existing integrity model. All AI-layer actions (clustering, transcription, flagging) are recorded in an append-only, hash-chained audit log, so any tampering with the AI-generated findings is detectable — while the original evidence and its Autopsy-native hash trail remain untouched.

---

## 8. Limitations & Responsible Use

- Facial recognition and transcription are **assistive triage tools**, not definitive evidence — all AI outputs must be verified by a certified examiner before use in proceedings
- Face matching may produce false positives/negatives, especially across lighting, angle, and image quality variation
- The NSFW/CSAM pre-screening flag is strictly a **flag-for-human-review** mechanism — it never auto-classifies or auto-deletes content, and all flagged material still requires manual, qualified review
- Transcription accuracy varies with audio quality, accents, and background noise
- This tool does not replace forensic certification or legal chain-of-custody procedures required in your jurisdiction

---

## 9. Roadmap

- [ ] Full plugin marketplace for community AI ingest modules
- [ ] Cross-case entity correlation (link people/numbers across multiple cases)
- [ ] Mobile app support for field triage
- [ ] Cloud/on-prem hybrid deployment options
- [ ] Expanded language support for STT/TTS

For the full Autopsy feature-by-feature parity checklist (what upstream Autopsy has that NetSherlock doesn't yet, and the suggested build order), see [PROJECT_PROPOSAL.md §7](PROJECT_PROPOSAL.md#7-autopsy-feature-parity-roadmap).

---

## 10. Contributing

Contributions welcome! Please open an issue before submitting a PR to discuss scope. See `CONTRIBUTING.md` for guidelines.

---

## 11. License

*(Specify license — e.g. Apache 2.0, matching Autopsy's licensing terms)*

---

## 12. Team & Credits

*(Add team members / acknowledgments here)*
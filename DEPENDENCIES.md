# Dependencies — NetSherlock (Sih-Forensic-Intelligence)

All dependencies required to set up and run this project locally.

## 1. System-level prerequisites

Install these before touching `pip`/`npm`:

| Tool | Purpose | Notes |
|---|---|---|
| Python 3.11+ | Backend runtime | `python -m venv venv` recommended |
| Node.js 18+ / npm | Frontend runtime | Next.js 16 requires a recent Node LTS |
| Redis | Celery broker/result backend | Optional for local dev — if unreachable, Celery tasks run eagerly (inline) per `.env.example` |
| PostgreSQL | AI-output storage (production) | Optional for local dev — SQLite (`netsherlock.db`) is the zero-setup default |
| Java + Jython env | Autopsy fork build (forensic core) | Only needed if building/running the Autopsy ingest core; see Autopsy's own build docs |
| ffmpeg | Audio/video decoding for faster-whisper / opencv | Required on PATH for speech-to-text and video frame extraction to work |

## 2. Backend (Python) — `backend/requirements.txt`

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Core (required to run the API at all)**
- fastapi==0.115.0
- uvicorn[standard]==0.30.6
- sqlmodel==0.0.22
- pydantic-settings==2.5.2
- python-jose[cryptography]==3.3.0
- passlib[bcrypt]==1.7.4
- bcrypt==4.0.1 *(pinned — passlib 1.7.4 needs `bcrypt.__about__.__version__`, removed in bcrypt>=4.1)*
- python-multipart==0.0.9
- celery==5.4.0
- redis==5.0.8
- jinja2==3.1.4
- xhtml2pdf==0.2.16

**AI layer** (lazy-imported — API runs without these; missing features degrade to a "model not installed" response)
- faster-whisper==1.0.3 *(speech-to-text)*
- pyttsx3==2.90 *(text-to-speech)*
- sentence-transformers==3.1.1 *(semantic search embeddings)*
- faiss-cpu==1.8.0.post1 *(vector similarity search)*
- facenet-pytorch==2.6.0 *(facial recognition)*
- torch==2.4.1 *(ML backend)*
- scikit-learn==1.5.2 *(clustering)*
- opencv-python==4.10.0.84 *(image/video processing)*
- opennsfw2==0.13.0 *(NSFW pre-screening flag)*
- numpy==1.26.4
- Pillow==10.4.0

**Dev/test**
- pytest==8.3.3
- httpx==0.27.2

## 3. Frontend (Node) — `frontend/package.json`

```bash
cd frontend
npm install
```

**Dependencies**
- next@16.3.3
- react@18.3.1
- react-dom@18.3.1

**Dev dependencies**
- @types/node@20.14.10
- @types/react@18.3.3
- @types/react-dom@18.3.0
- autoprefixer@10.4.19
- postcss@8.5.26
- tailwindcss@3.4.4
- typescript@5.5.3

> README also lists `shadcn/ui`, `react-force-graph`/`d3`, and `Zustand`/`React Query` as planned frontend stack choices — not yet present in `package.json`. Add them when those features are implemented.

## 4. Running everything

```bash
# Redis (if not using eager/inline Celery mode)
redis-server &

# Backend
cd backend
celery -A app.worker worker --loglevel=info &
uvicorn app.main:app --reload

# Frontend
cd frontend
npm run dev
```

Copy `backend/.env.example` to `backend/.env` and adjust values (`DATABASE_URL`, `SECRET_KEY`, `CELERY_BROKER_URL`, `WHISPER_MODEL`, etc.) before running.

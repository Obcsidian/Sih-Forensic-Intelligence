# Changelog

All notable changes to **ForensAI** are documented here.

## [Unreleased] — UI Overhaul + AI Integration

### UI Overhaul — Bento Grid + Liquid Glass + 3D
- **`frontend/app/globals.css`** — Added `.glass-panel`, `.glass-card`, `.liquid-btn`, `.bento-grid`, `.depth-3d`, `.input-glass`, `.status-badge` utilities, shimmer/float/pulse-glow keyframes, custom scrollbar.
- **`frontend/tailwind.config.ts`** — Added `float`, `pulse-glow`, `shimmer` animations and color tokens.
- **`frontend/components/LoginScreen.tsx`** — Glass morphism login form with animated orbs.
- **`frontend/components/TopBar.tsx`** — Liquid-glass nav bar, gradient "Generate report" CTA.
- **`frontend/components/TreeSidebar.tsx`** — Bento sidebar with sectioned file types / AI analysis / extracted content; clean text-based icons (◻ ◉ ◈ ☐ ↩ ⊞ ☏ » ⊕ ⊘ ⚠ ◎ ¶).
- **`frontend/components/CenterPanel.tsx`** — Glass event icons, person card refresh.
- **`frontend/components/MetadataPanel.tsx`** — Glass metadata panel with NSFW review card.
- **`frontend/components/PreviewPane.tsx`** — Glass preview pane with rounded tabs.
- **`frontend/components/StatusBar.tsx`** — Bottom status bar with chain-of-custody indicators.
- **`frontend/components/NewCaseDialog.tsx`** — Glass modal for new-case ingestion.
- **`frontend/components/Workspace.tsx`** — Fixed syntax errors (`export interface ViewMode` → `export type ViewMode`, missing template literals, broken braces); redesigned case-chooser to a 3-column responsive grid with header.

### New Pages
- **`frontend/app/landing/page.tsx`** — New landing page: hero section, 8 feature cards with blue-themed icons, CTAs to `/login`.
- **`frontend/app/login/page.tsx`** — Standalone login page at `/login` with blurred glass background, password Show/Hide toggle, demo-account cards.
- **`frontend/app/page.tsx`** — Root page: shows loading screen, checks token, redirects to `/landing` or renders `<Workspace />`.
- **`frontend/app/layout.tsx`** — Untouched (kept minimal Next.js root).

### New Components
- **`frontend/components/LoadingScreen.tsx`** — 1.5s animated loading with progress bar and status text.

### Backend — AI Gateway Integration
- **`backend/app/services/ai_gateway.py`** *(NEW)* — Unified AI client supporting chat, vision, embeddings, audio transcription, and TTS; daily quota meter, retry-with-backoff, local-fallback flag.
- **`backend/app/services/face_recognition.py`** — Rewritten to call gateway vision first, local facenet-pytorch fallback, hash-based pseudo-embeddings; added `process_evidence_file()` and `cluster_case()` for the worker.
- **`backend/app/services/transcription.py`** — Rewritten: gateway Whisper → local faster-whisper → empty result fallback.
- **`backend/app/services/nsfw_screening.py`** — Rewritten: gateway vision JSON scoring → local opennsfw2 fallback; conservative `FLAG_THRESHOLD = 0.7`.
- **`backend/app/services/semantic_search.py`** — Rewritten with gateway embeddings → local sentence-transformers → zero-vector fallback; `SearchHit` dataclass.
- **`backend/app/services/anomaly_detection.py`** — Rewritten with rule-based baselines (deleted-recovered, brief app installs) + gateway chat reasoning; severity-tagged `Anomaly` dataclass.
- **`backend/app/services/entity_extraction.py`** — *(NEW)* Gateway chat JSON extraction → regex fallback for phones/emails; auto-creates `Contact` rows.
- **`backend/app/config.py`** — Added `ai_gateway_*` settings (api_key, base_url, models, daily_limit, fallback flag).
- **`backend/.env.example`** — Added `AI_GATEWAY_API_KEY`, `AI_GATEWAY_BASE_URL`, `AI_GATEWAY_ENABLED`, `AI_FALLBACK_LOCAL`, `AI_DAILY_LIMIT`, model-selection vars.

### Fixed
- **Password Show/Hide** — Toggle now sits inside the input field, not outside.
- **Landing page redirect** — `/` no longer requires typing `/landing`.
- **Case chooser alignment** — Fixed layout, responsive 3-column grid, better card structure.
- **Workspace `export interface ViewMode`** syntax error — Changed to `export type ViewMode`.
- **Template-literal and brace mismatches** in `Workspace.tsx`.

### Behavior
- All emojis replaced with clean text/icons that match the blue glass theme.
- Loading screen appears for 1.5s on first page load.
- Smooth scroll animations on landing-page feature cards via `IntersectionObserver`.
- Free-tier AI usage: 5,000 requests/day cap; graceful degradation when gateway is unreachable.

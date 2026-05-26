# ADM

## Tech Stack

### Frontend
- Nuxt 4 (Vue 3, TypeScript)
- Pinia
- TailwindCSS
- wavesurfer.js

### Backend
- FastAPI
- PostgreSQL
- SQLAlchemy / Alembic
- JWT

---

## Setup

### Backend

```bash
cd ADM_b
./scripts/init_db.sh   # first run (idempotent)
source venv/bin/activate
uvicorn app.main:app --reload
```

`init_db.sh` generates `.env`, creates DB roles, runs migrations, and sets up storage directories automatically.

Backend: `http://localhost:8000`

### Frontend

```bash
cd ADM_f
pnpm install
pnpm dev
```

Frontend: `http://localhost:3000`

---

## Requirements

- Python 3.11+
- Node.js 20+
- pnpm
- PostgreSQL 15+
- ffmpeg

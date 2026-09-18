# Environment Setup (same for all 5 members)

Goal: everyone runs the exact same versions of everything, so "works on my
machine" never happens. We do this with **Docker** — you do not need to
install Python, Node, or Postgres locally at all.

## 1. Prerequisites (only these two)

- Docker Desktop (or Docker Engine + Compose on Linux)
- Git

That's it. Everything else (Python 3.12, Node 20, Postgres 16 + pgvector)
is pinned inside the Dockerfiles and docker-compose.yml, so every laptop
gets identical versions.

## 2. Clone & configure

```bash
git clone <repo-url>
cd muscle-max
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Fill in `backend/.env`:
- `LLM_API_KEY` — get this from whoever is holding the team's API key (do
  **not** commit it — `.env` is gitignored).
- Leave `POSTGRES_*` and `DJANGO_*` values as-is unless you have a reason
  to change them; they already match `docker-compose.yml`.

## 3. Run everything

```bash
docker compose up --build
```

First run installs everything and takes a few minutes. After that,
`docker compose up` is fast. This starts:

| Service  | URL                         |
|----------|------------------------------|
| frontend | http://localhost:5173        |
| backend  | http://localhost:8000/api/   |
| admin    | http://localhost:8000/admin/ |
| db       | localhost:5432 (Postgres)    |

## 4. Day-to-day commands

Run these while `docker compose up` is running, in a second terminal:

```bash
# Django migrations after pulling new model changes
docker compose exec backend python manage.py migrate

# Create a migration after you change a model
docker compose exec backend python manage.py makemigrations

# Create your own admin login
docker compose exec backend python manage.py createsuperuser

# Rebuild the chatbot's knowledge base after product data changes
docker compose exec backend python manage.py ingest_knowledge_base

# Install a new npm package
docker compose exec frontend npm install <package>

# Install a new pip package (then add it to requirements.txt yourself)
docker compose exec backend pip install <package>
```

## 5. If you'd rather not use Docker

Only do this if Docker genuinely won't run on your machine — it will drift
from everyone else's setup over time, so treat it as a fallback:

**Backend**
```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Install Postgres 16 locally + the pgvector extension, matching .env
python manage.py migrate
python manage.py runserver
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

## 6. Common issues

- **Port already in use** — something else on your machine is using 5432,
  8000, or 5173. Stop it, or change the left-hand port in
  `docker-compose.yml` (only change your own copy, don't commit it).
- **"relation does not exist" DB errors** — you're missing a migration:
  `docker compose exec backend python manage.py migrate`.
- **Frontend can't reach backend** — check `frontend/.env`'s
  `VITE_API_BASE_URL` matches where the backend is actually running.

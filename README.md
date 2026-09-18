# Muscle Max

AI-powered e-commerce platform for a fitness/supplement business — customers
browse and buy products, and can ask a RAG-grounded chatbot questions that
are answered from Muscle Max's real product and business data (not guesses).

**Stack:** Django + Django REST Framework (backend/API) · React + Vite
(frontend) · PostgreSQL + pgvector (database + vector store) · an LLM API
for the chatbot's answer generation.

## Repo layout

```
muscle-max/
├── backend/          Django project — REST API, models, RAG pipeline
├── frontend/          React app — storefront, cart, checkout, chatbot widget
├── docs/              Everything the team needs to build this without drifting
├── docker-compose.yml One command to run the whole stack identically for everyone
└── .github/workflows  CI checks on every PR
```

## Start here

Read `docs/` in this order — it's written so all 5 of you end up with the
same setup, the same API contract, and no merge surprises:

1. **`docs/SETUP.md`** — get the identical dev environment running (Docker, one command).
2. **`docs/ARCHITECTURE.md`** — how the pieces fit together.
3. **`docs/TASK_DIVISION.md`** — who owns what module.
4. **`docs/GIT_WORKFLOW.md`** — branch names, commit format, PR rules.
5. **`docs/API_WORKFLOW.md`** — every endpoint, request/response shape, and how frontend calls backend.
6. **`docs/DATABASE_SCHEMA.md`** — tables and relationships.
7. **`docs/RAG_PIPELINE.md`** — how the chatbot actually retrieves & answers.
8. **`docs/CODING_STANDARDS.md`** — naming, formatting, folder conventions so 5 people's code looks like 1 person wrote it.

## Quick start (once Docker is installed)

```bash
git clone <your-repo-url> && cd muscle-max
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api/
- Django admin: http://localhost:8000/admin/

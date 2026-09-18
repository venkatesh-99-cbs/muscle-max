# Task Division — 5 Members

A suggested split by module ownership, so responsibilities and Django
app boundaries line up 1:1. Swap names in once assigned; keep the
module boundaries since the rest of the docs assume this split.

| # | Member | Backend ownership                          | Frontend ownership                              |
|---|--------|----------------------------------------------|---------------------------------------------------|
| 1 | —      | `accounts` app — auth, JWT, user model         | Login/Register pages, `AuthContext`                |
| 2 | —      | `products` app — catalog, categories, admin CRUD | Product listing + product detail pages           |
| 3 | —      | `cart` + `orders` apps — cart, checkout, order status | Cart drawer, checkout page, order history page |
| 4 | —      | `chatbot` app — RAG pipeline (ingest, retriever, generator) | Chat widget UI, message history              |
| 5 | —      | Infra + integration: Docker setup, CI, DB migrations review, deployment | Layout/Navbar/Footer, routing, shared components (`components/common`) |

## Why this split

Each backend app in `docs/ARCHITECTURE.md` maps to exactly one owner, so
there's a single point of contact when the API contract needs to
change. Frontend features are paired with the backend they consume, so
the same person can build both sides of a feature end-to-end if that's
more efficient — or hand off cleanly at the `docs/API_WORKFLOW.md`
boundary if two different people are doing frontend vs. backend for the
same feature.

## Cross-cutting responsibilities (everyone)

- Keep `docs/API_WORKFLOW.md` and `docs/DATABASE_SCHEMA.md` current for
  anything you change (see `GIT_WORKFLOW.md`).
- Write your own Django app's `admin.py` registrations so the demo's
  admin panel is usable for your module.
- Test your endpoints with `curl` or the DRF browsable API
  (`http://localhost:8000/api/<app>/`) before telling the frontend owner
  it's ready.

## Suggested build order (2–3 day hackathon pace)

**Day 1** — Everyone: `SETUP.md` working locally. Member 1 ships auth.
Member 2 ships product model + list/detail endpoints + product pages.
Member 5 gets Docker/CI green.

**Day 2** — Member 3 ships cart + checkout. Member 4 gets ingestion +
retriever working against seeded product data. Members 1–2 wire up
frontend auth + product pages against real endpoints.

**Day 3** — Member 4 finishes the `/chatbot/ask/` endpoint + chat widget
integration. Everyone: checkout flow end-to-end, admin panel usable,
polish + demo rehearsal.

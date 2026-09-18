# API Workflow

Base URL (local dev): `http://localhost:8000/api/`

All request/response bodies are JSON. Authenticated endpoints require a
header: `Authorization: Bearer <access_token>`.

## How frontend and backend agree on a contract

1. Whoever owns a backend app (see `TASK_DIVISION.md`) defines the
   serializer + view + URL for their endpoints **first**, and updates the
   table below in the same PR.
2. The frontend owner for that feature builds against the table below,
   not against guesses — if the shape isn't listed here yet, ask before
   building the UI for it.
3. Any breaking change to an endpoint (renamed field, changed status
   code) must be called out in the PR description and mentioned in the
   team chat, since 2+ people are usually depending on it.

## Auth (`accounts`)

| Method | Endpoint                  | Auth | Body                              | Response                          |
|--------|----------------------------|------|------------------------------------|------------------------------------|
| POST   | `/accounts/register/`      | no   | `{email, password, name}`          | `{id, email, name}`                |
| POST   | `/accounts/login/`         | no   | `{email, password}`                | `{access, refresh}`                |
| POST   | `/accounts/token/refresh/` | no   | `{refresh}`                        | `{access}`                         |
| GET    | `/accounts/me/`            | yes  | —                                   | `{id, email, name}`                |

## Products (`products`)

| Method | Endpoint                | Auth | Body            | Response                                                        |
|--------|---------------------------|------|-----------------|--------------------------------------------------------------------|
| GET    | `/products/`               | no   | query: `?search=&category=` | `[{id, name, price, category, image, in_stock}]`     |
| GET    | `/products/<id>/`          | no   | —               | `{id, name, price, category, image, description, specs, in_stock}`|
| POST   | `/products/` *(admin)*     | yes  | full product     | `{id, ...}`                                                        |
| PATCH  | `/products/<id>/` *(admin)*| yes  | partial fields   | `{id, ...}`                                                        |
| DELETE | `/products/<id>/` *(admin)*| yes  | —               | `204 No Content`                                                    |

## Cart (`cart`)

| Method | Endpoint            | Auth | Body                               | Response                              |
|--------|----------------------|------|--------------------------------------|-----------------------------------------|
| GET    | `/cart/`              | yes  | —                                     | `{items: [{id, product, quantity}], total}` |
| POST   | `/cart/items/`        | yes  | `{product: <id>, quantity}`          | `{id, product, quantity}`                |
| PATCH  | `/cart/items/<id>/`   | yes  | `{quantity}`                          | `{id, product, quantity}`                |
| DELETE | `/cart/items/<id>/`   | yes  | —                                     | `204 No Content`                          |

## Orders (`orders`)

| Method | Endpoint            | Auth | Body                                            | Response                                    |
|--------|----------------------|------|---------------------------------------------------|------------------------------------------------|
| POST   | `/orders/`            | yes  | `{shipping_address, payment_method}`               | `{id, status, items, total, created_at}`        |
| GET    | `/orders/`            | yes  | —                                                   | `[{id, status, total, created_at}]`             |
| GET    | `/orders/<id>/`       | yes  | —                                                   | `{id, status, items, total, created_at}`        |
| PATCH  | `/orders/<id>/` *(admin)* | yes | `{status}`                                       | `{id, status}`                                   |

## Chatbot (`chatbot`)

| Method | Endpoint          | Auth | Body                   | Response                                                     |
|--------|--------------------|------|--------------------------|------------------------------------------------------------------|
| POST   | `/chatbot/ask/`     | no   | `{question: string}`     | `{answer: string, sources: [{type, id, title}], grounded: bool}` |

`grounded: false` means the retriever found nothing relevant above the
similarity threshold, and `answer` will be the "I don't know based on
the available Muscle Max information" fallback — see `RAG_PIPELINE.md`.

## Status codes used consistently

- `200` success (GET/PATCH), `201` created (POST), `204` no content (DELETE)
- `400` validation error → `{field_name: ["error message"]}`
- `401` missing/expired token, `403` authenticated but not allowed
- `404` not found

## Admin-managed chatbot knowledge

Product changes auto-feed the chatbot (re-run
`python manage.py ingest_knowledge_base` after bulk edits, or wire it to
a Django signal — team decision, note it here once decided). Non-product
business info (policies, FAQs, delivery info) lives in
`chatbot` app models and is edited via Django admin, then re-ingested
the same way.

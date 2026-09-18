# Architecture

## High-level

```
                      ┌─────────────────────┐
                      │   React frontend     │
                      │ (storefront, cart,   │
                      │  checkout, chat UI)  │
                      └──────────┬───────────┘
                                 │ REST (JSON, JWT auth)
                      ┌──────────▼───────────┐
                      │   Django + DRF API    │
                      │  (backend/musclemax)  │
                      └──────────┬───────────┘
           ┌─────────────────────┼─────────────────────┐
           │                     │                      │
   ┌───────▼───────┐    ┌────────▼────────┐   ┌─────────▼─────────┐
   │  E-commerce    │    │  Chatbot / RAG   │   │   Accounts /      │
   │  apps: products,│   │  app: retriever, │   │   Admin (Django   │
   │  cart, orders   │    │  generator, LLM  │   │   built-in admin) │
   └───────┬────────┘    └────────┬─────────┘   └─────────┬─────────┘
           │                      │                        │
           └──────────────┬───────┴────────────────────────┘
                           │
                  ┌────────▼─────────┐
                  │   PostgreSQL      │
                  │ + pgvector ext.   │
                  │ (business data +  │
                  │  embeddings live  │
                  │  in the same DB)  │
                  └────────┬──────────┘
                           │
                  ┌────────▼─────────┐
                  │   LLM API         │
                  │ (embeddings +     │
                  │  answer generation)│
                  └───────────────────┘
```

## Why one Postgres instance for both e-commerce data AND vectors

Using `pgvector` means the RAG system queries the *same* database that
holds live product/price/stock data — no separate vector DB to keep in
sync. When a product's price changes, re-running the ingestion command
re-embeds it and the chatbot's answers reflect reality immediately.

## Backend app boundaries (Django apps)

| App          | Owns                                                          |
|--------------|----------------------------------------------------------------|
| `accounts`   | User model, auth (JWT), registration/login                    |
| `products`   | Product catalog, categories, stock                             |
| `cart`       | Per-user cart + cart items                                     |
| `orders`     | Checkout, order + order-item records, order status             |
| `chatbot`    | Knowledge base ingestion, retriever, generator, `/ask` endpoint|

Each app is self-contained: its own `models.py`, `serializers.py`,
`views.py`, `urls.py`. Cross-app access goes through model imports or
serializers — not through raw SQL reaching into another app's tables.

## Frontend structure

- `src/pages/` — one component per route (HomePage, ProductPage, CartPage, CheckoutPage…).
- `src/features/<domain>/` — domain-specific components used only within that feature (e.g. `features/cart/CartDrawer.jsx`).
- `src/components/common/` — generic, reusable UI (Button, Modal, Spinner).
- `src/components/layout/` — Navbar, Footer, PageLayout.
- `src/services/` — one file per backend resource (`productsApi.js`, `cartApi.js`…), all HTTP calls funnel through `services/api.js`.
- `src/context/` — global state (auth session, cart count badge).

## Request flow example: customer asks the chatbot a question

1. `ChatWidget.jsx` (frontend) calls `chatbotApi.askChatbot(question)`.
2. Hits `POST /api/chatbot/ask/` on the Django backend.
3. `chatbot/views.py` calls `rag/retriever.py` → embeds the question,
   queries `pgvector` for the top-k matching chunks.
4. Passes question + retrieved chunks to `rag/generator.py`, which
   prompts the LLM with an instruction to answer **only** from context,
   and to say it doesn't know otherwise.
5. Response returned to frontend as JSON and rendered in the chat UI.

See `docs/RAG_PIPELINE.md` for the full detail on steps 3–4, and
`docs/API_WORKFLOW.md` for the exact endpoint contract.

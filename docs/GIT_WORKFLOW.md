# Git Workflow (team of 5)

## Branches

- `main` — always deployable/demo-ready. No direct commits.
- `develop` — integration branch. Everyone's PRs merge here first.
- `feature/<app>-<short-description>` — e.g. `feature/cart-add-item`,
  `feature/chatbot-retriever`, `feature/frontend-checkout-page`.

```
main
 └── develop
       ├── feature/products-catalog-api
       ├── feature/frontend-product-page
       ├── feature/chatbot-rag-ingest
       ├── feature/cart-checkout-flow
       └── feature/orders-admin-status
```

## Daily flow

1. `git checkout develop && git pull`
2. `git checkout -b feature/<app>-<description>`
3. Work, commit in small chunks.
4. `git push -u origin feature/<app>-<description>`
5. Open a PR into `develop`. Tag one teammate to review (ideally whoever
   owns the app you touched, or the frontend owner if you changed an API
   contract they depend on).
6. Squash-merge once approved and CI passes.

## Commit message format

```
<app>: <short imperative description>

feat(products): add category filter to product list endpoint
fix(cart): correct quantity update on duplicate add
docs(api): update chatbot endpoint response shape
```

## Before opening a PR that touches an API endpoint

Update `docs/API_WORKFLOW.md` in the same PR. Anyone building the
frontend for that endpoint should not have to read your view code to
know the response shape.

## Before opening a PR that touches a model

Include the migration file, and update `docs/DATABASE_SCHEMA.md` in the
same PR.

## Merge conflicts

Because each person mostly owns one Django app / one frontend feature
(see `TASK_DIVISION.md`), conflicts should be rare. If they happen in
shared files (`urls.py`, `settings.py`, `App.jsx`), resolve live on a
call rather than guessing — those files are easy to silently break.

## Environment files

`.env` files are gitignored on purpose — never commit real secrets.
When `.env.example` needs a new variable, add it there (with a dummy
value) and post in the team chat so everyone updates their local `.env`.

# Coding Standards

So five people's code reads as one codebase.

## Python / Django (backend)

- Format with `black` and `isort` before committing (add to your editor's
  format-on-save, or run `black . && isort .` in `backend/`).
- One Django app = one bounded domain. Don't reach into another app's
  models directly for writes — import and call, or go through its
  serializer.
- Views: use DRF generic views / viewsets, not raw function views, unless
  there's a specific reason (note the reason in a comment if so).
- Every model field that isn't obviously self-explanatory gets a
  `help_text`.
- Environment-specific or secret values always go through
  `os.getenv(...)` in `settings.py` — never hardcoded, never committed.

## JavaScript / React (frontend)

- Components: `PascalCase.jsx`. Hooks: `useCamelCase.js`. Everything
  else: `camelCase.js`.
- One component per file. If a component grows past ~150 lines,
  consider splitting.
- All backend calls go through `src/services/*Api.js` — components never
  call `axios`/`fetch` directly, so the API contract lives in one place
  per resource.
- Prefer function components + hooks; no class components.
- Keep page-level layout/routing logic in `src/pages/`; keep reusable
  pieces in `src/components/`.

## Naming conventions (both sides)

- API JSON fields: `snake_case` (matches Django/DRF defaults) — the
  frontend converts to `camelCase` at the service layer if needed, not
  ad hoc in components.
- URLs: kebab-case, plural nouns (`/products/`, `/cart/items/`).
- Django app names: lowercase, singular-domain (`products`, not
  `Product` or `products_app`).

## Commit hygiene

- Small, focused commits over one giant "final version" commit.
- No commented-out dead code left in — delete it, git history has it if
  needed.
- No `console.log` / `print()` debugging left in merged code.

## Pull requests

- Link the doc you updated (API_WORKFLOW.md / DATABASE_SCHEMA.md) if
  applicable — see `GIT_WORKFLOW.md`.
- Description should say what changed and how to test it, not just
  "updates."

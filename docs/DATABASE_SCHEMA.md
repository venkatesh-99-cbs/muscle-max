# Database Schema (PostgreSQL + pgvector)

This is the planned shape — the owner of each app creates the actual
Django models under `backend/apps/<app>/models.py` and keeps this file in
sync in the same PR as any model change.

## accounts

**User** (extends Django's `AbstractUser`)
- id, email (unique, used as login), name, is_staff, date_joined

## products

**Category**
- id, name, slug

**Product**
- id, name, slug, description, price, specs (JSON), category (FK → Category)
- image, stock_quantity, is_active, created_at, updated_at

## cart

**Cart**
- id, user (FK → User, one active cart per user)

**CartItem**
- id, cart (FK → Cart), product (FK → Product), quantity

## orders

**Order**
- id, user (FK → User), status (`pending`/`paid`/`shipped`/`delivered`/`cancelled`)
- shipping_address, payment_method, total, created_at

**OrderItem**
- id, order (FK → Order), product (FK → Product), quantity, price_at_purchase

## chatbot

**BusinessInfo**
- id, category (`policy`/`faq`/`delivery`/`general`), title, content, updated_at

**KnowledgeChunk**
- id, source_type (`product`/`business_info`), source_id, text
- embedding (`vector`, via pgvector — dimension matches the chosen embedding model)
- metadata (JSON, e.g. product name/price for citation display)
- updated_at

## Relationships

```
User 1───∞ Order 1───∞ OrderItem ∞───1 Product
User 1───1 Cart 1───∞ CartItem  ∞───1 Product
Product ∞───1 Category
Product 1───∞ KnowledgeChunk (source_type="product")
BusinessInfo 1───∞ KnowledgeChunk (source_type="business_info")
```

## Enabling pgvector

The `pgvector/pgvector:pg16` Docker image already has the extension
installed — just enable it once per database:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Put this in a Django migration (`RunSQL`) for the `chatbot` app so it
runs automatically for everyone on `migrate`, rather than relying on
each person running it manually.

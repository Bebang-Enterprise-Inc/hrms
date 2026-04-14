# Mosaic Solutions API Documentation

**Authoritative spec (machine-readable):** `docs/api/MOSAIC_API_OPENAPI_2026-04-14.json`
(OpenAPI 3.0.3 — use this for any ambiguity; this markdown is a human summary)

**Source:** Google Docs shared by Rajat Verma on Oct 3, 2025
**Google Doc:** https://docs.google.com/document/d/1KcixaVE1Ez3SgQKt-U74BUq3eLCJ3zZ6JbGM2A956O4
**Downloaded:** 2026-02-07; OpenAPI JSON received 2026-04-14
**Also saved at:** `F:\Dropbox\Projects\Dice-Roll-Game-Digital\docs\api\MOSAIC_API.md`

---

## Introduction

The Mosaic API allows your business to seamlessly integrate your website or application with our Point-of-Sale (POS) Systems. All communication between clients and the API is secured using JSON over HTTPS. All timestamps in responses are provided in the ISO-8601 format with UTC timezone unless otherwise specified.

## Environments

| Environment | Base URL | Description |
|-------------|----------|-------------|
| Testing/Staging | `https://stg-api.mosaicpos.com` | Use for development and testing |
| Production | `https://api.mosaic-pos.com` | Use for live production systems |

---

## 1. Authentication

The API uses the **OAuth 2.0 client_credentials** grant type. You must first exchange your `client_id` and `client_secret` for an `access_token`. This token must then be passed in the `Authorization` header of all subsequent requests as a Bearer token.

### 1.1 Create Access Token

**POST** `/oauth/token`

**Request:**
```json
{
  "client_id": "<your-client-id>",
  "client_secret": "<your-secret-key>",
  "grant_type": "client_credentials"
}
```

**Response (200 OK):**
```json
{
  "token_type": "Bearer",
  "expires_in": 86400,
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9..."
}
```

---

## 2. Orders

### 2.1 Get Orders

**GET** `/api/v1/orders`

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `filter[business_date]` | Yes | Filter orders by business date (Y-m-d) | `2025-09-16` |
| `page[number]` | No | Page number (min 1) | `1` |
| `page[size]` | No | Items per page (max 100) | `100` |

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": 46231,
      "location_id": 295,
      "reference_id": null,
      "business_date": "2023-02-22",
      "pax_count": 1,
      "price_breakdown": {
        "gross_sales": 1.1,
        "net_sales": 0.8929,
        "vatable_sales": 0.8929,
        "vat_amount": 0.1071,
        "total_discounts": 0
      },
      "billed_at": "2023-02-22T00:37:31.000000Z",
      "paid_at": "2023-02-22T00:37:38.000000Z",
      "items": [
        {
          "product_id": 30419,
          "name": "Product Name",
          "price": 1,
          "quantity": 1,
          "net_sales": 0.8929,
          "modifiers": []
        }
      ],
      "payment_methods": [
        {
          "payment_type": "Cash",
          "paid_amount": 1.1,
          "returned_amount": 0
        }
      ]
    }
  ],
  "meta": { "current_page": 1, "last_page": 1, "total": 2 }
}
```

### 2.2 Create Order

**POST** `/api/v1/orders`

```json
{
  "location_id": 18,
  "service_type_id": 3,
  "business_date": "2025-09-16",
  "ordered_at": "2025-09-16 13:08:07",
  "price_breakdown": {
    "gross_sales": 90, "net_sales": 6, "vatable_sales": 80.36,
    "vat_amount": 9.64, "vat_exempt_sales": 0, "zero_rated_sales": 0,
    "total_discounts": 0, "delivery_fee": 0
  },
  "items": [
    {
      "product_sku": "SUADA",
      "name": "Iced Kape Sua Da",
      "price": 75, "quantity": 1,
      "gross_sales": 90, "net_sales": 10,
      "vatable_sales": 80.36, "vat_amount": 9.64,
      "vat_exempt_sales": 0, "zero_rated_sales": 0,
      "discount_amount": 33,
      "modifiers": [], "discount": null
    }
  ],
  "payment_details": [
    { "payment_type": "Cash", "paid_amount": 90, "returned_amount": 10 }
  ]
}
```

### 2.3 Get Order by ID — `GET /api/v1/orders/{id}`
### 2.4 Get Order by Reference — `GET /api/v1/order_references/{order}`
### 2.5 Cancel Order — `POST /api/v1/orders/{order_id}/cancel`

---

## 3. Locations and Taxes

### 3.1 Get Locations — `GET /api/v1/locations`
### 3.2 Update Location — `PUT /api/v1/locations/{id}`
### 3.3 Get Taxes by Location — `GET /api/v1/locations/{location_id}/taxes`

---

## 4. Catalog Management

### 4.1 Get Product Categories — `GET /api/v1/product_categories`
### 4.2 Get Product Groups — `GET /api/v1/product_categories/{id}/groups`
### 4.3 Get Products — `GET /api/v1/products`
### 4.4 Create Product — `POST /api/v1/products`
### 4.5 Update Product — `PUT /api/v1/products/{id}`
### 4.6 Get Modifier Groups — `GET /api/v1/modifier_groups`
### 4.7 Get Modifiers — `GET /api/v1/modifier_groups/{id}/modifiers`

---

## 5. Service Types — `GET /api/v1/service_types`

## 6. Payments

### 6.1 Get Payment Categories — `GET /api/v1/payment_categories`
### 6.2 Get Payment Types — `GET /api/v1/payment_types`
### 6.3 Create Payment Type — `POST /api/v1/payment_types`

## 7. Discounts

### 7.1-7.5 Full CRUD at `/api/v1/discounts` and `/api/v1/discounts/{id}`

See dedicated file: `docs/api/MOSAIC_DISCOUNTS_API.md` (or Dice Roll Game copy)

## 8. Webhooks

Full CRUD at `/api/v1/webhooks` and `/api/v1/webhooks/{id}`:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/webhooks` | List all webhooks for the authenticated credential group |
| POST | `/api/v1/webhooks` | Create a webhook: `{url, events}` — returns `{data: {id, url, events, created_at, updated_at}}` |
| PUT | `/api/v1/webhooks/{id}` | Update events or URL for an existing webhook |
| DELETE | `/api/v1/webhooks/{id}` | Delete a webhook |

### 8.1 Supported Events (7 total, per OpenAPI enum 2026-04-14)

| Event | Trigger | BEI usage |
|-------|---------|-----------|
| `order.created` | New order opened | Not used (too early for revenue) |
| `order.paid` | Payment received | Candidate for future real-time revenue stream |
| `order.ready` | Kitchen completed | Not used |
| `order.completed` | Order closed | S189: upsert to `pos_orders` with `ingestion_source='webhook'` |
| `order.cancelled` | Order voided | S169: tombstone `cancelled_at` on `pos_orders` |
| `location.created` | Store added | Not used |
| `location.updated` | Store metadata changed | Not used |

### 8.2 Signature / authentication on inbound webhooks

**The OpenAPI doc does NOT document any signature scheme** (no `signature`, `hmac`, or
webhook-signing fields in the spec as of 2026-04-14). Our handler
(`hrms/api/mosaic_webhook.py`) therefore uses Path B "round-trip" auth:

1. Receive webhook payload
2. Extract `order_id` and `location_id`
3. OAuth with the credential group for that `location_id`
4. `GET /api/v1/orders/{order_id}` — expected status depends on event:
   - `order.cancelled` → expect HTTP 404 (order gone)
   - `order.completed` → expect HTTP 200 (order exists, fetch authoritative payload)
5. Only accept the webhook if the round-trip matches

The handler also has an optional SPECULATIVE HMAC check (`MOSAIC_WEBHOOK_SECRET`
env var) for when/if Mosaic publishes a signing spec in the future — it's
defensive code that falls through to Path B when no secret is set.

### 8.3 Rate limits, retries, delivery guarantees

**Not documented.** Treat as best-effort; reconcile with poll sync daily via
`scripts/s189_reconciliation_audit.py`.

### 8.4 Known operational issues (2026-04-14)

- `GET /api/v1/webhooks` returns HTTP 500 for ~11 of 12 BEI credential groups,
  even with exponential backoff retries. **Do not rely on it as a truth source.**
  Use our delivery evidence (`v_webhook_coverage` in Supabase) instead.
- S169 registered 12 `order.cancelled` webhooks 2026-04-07, but 7-day webhook
  coverage is 0% — Mosaic is not delivering. Investigation ongoing; self-healing
  re-registration runs daily via `scripts/s189_webhook_registration_reconciler.py`.

---

For complete request/response examples, see:
- `docs/api/MOSAIC_API_OPENAPI_2026-04-14.json` (machine-readable, authoritative)
- `F:\Dropbox\Projects\Dice-Roll-Game-Digital\docs\api\MOSAIC_API.md` (mirror)

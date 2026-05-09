# Mosaic API ↔ Supabase Forensic Audit
_Generated: 2026-05-09T14:48:59.133299_

**Sample: 12 store-days. MATCH: 11, MISMATCH: 1, ERROR: 0**

## Per-store-day comparison

| Store | Date | Scenario | Mosaic Bills (PAID) | Supabase Bills (PAID) | Mosaic ₱ Gross | Supabase ₱ Gross | Δ Bills | Δ ₱ | Verdict |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| SM  Manila | 2026-05-03 | SM Manila — peak weekend (Sun) | 336 | 336 | 193,378.59 | 193,378.58 | +0 | +0.01 | **MATCH** |
| SM Megamall | 2026-05-07 | SM Megamall — recovered 149 missing bill | 305 | 305 | 164,591.67 | 164,591.66 | +0 | +0.01 | **MATCH** |
| SM North EDSA | 2026-05-07 | SM North EDSA — recovered 101 missing bi | 370 | 370 | 203,358.04 | 203,358.04 | +0 | +0.00 | **MATCH** |
| Ayala Solenad | 2026-05-07 | Ayala Solenad — recovered 95 missing bil | 155 | 155 | 90,323.04 | 90,323.04 | +0 | +0.00 | **MATCH** |
| The Grid - Rockwell | 2026-05-02 | The Grid Rockwell — synthetic-id collisi | 361 | 361 | 140,740.53 | 140,800.53 | +0 | -60.00 | **MISMATCH** |
| Araneta Gateway | 2026-05-03 | Araneta Gateway — credential group + col | 260 | 260 | 107,225.10 | 107,225.10 | +0 | +0.00 | **MATCH** |
| BF Homes | 2026-05-03 | BF Homes — recovered 106 missing bills | 257 | 257 | 160,056.90 | 160,056.89 | +0 | +0.01 | **MATCH** |
| D'Verde Calamba | 2026-05-05 | D'Verde Calamba — small store + early-cu | 80 | 80 | 45,260.61 | 45,260.61 | +0 | +0.00 | **MATCH** |
| SM Bicutan | 2026-05-05 | SM Bicutan — control mid-volume Tue | 170 | 170 | 83,107.51 | 83,107.51 | +0 | +0.00 | **MATCH** |
| SM Caloocan | 2026-05-04 | SM Caloocan — control normal Mon | 121 | 121 | 50,792.78 | 50,792.78 | +0 | +0.00 | **MATCH** |
| Megawide PITX | 2026-05-02 | Megawide PITX — control weekend | 142 | 142 | 51,459.81 | 51,459.81 | +0 | +0.00 | **MATCH** |
| Ayala Market Market | 2026-05-05 | Ayala Market Market — was 61 missing bil | 229 | 229 | 101,736.50 | 101,736.49 | +0 | +0.01 | **MATCH** |

## Per-store-day full detail (Mosaic + Supabase)

### SM  Manila (2339) — 2026-05-03
_SM Manila — peak weekend (Sun)_

| Metric | Mosaic | Supabase | Δ |
|---|---:|---:|---:|
| Raw orders returned | 376 | 356 | +20 |
| Distinct bill numbers | 356 | 356 | +0 |
| Distinct PAID bills | 336 | 336 | +0 |
| Sum PAID gross | 193,378.59 | 193,378.58 | +0.01 |
| Sum PAID net | 174,390.62 | 174,390.48 | +0.14 |
| Cancelled count | 0 | 0 | +0 |
| First paid_at | 2026-05-03T02:10:27.000000Z | 2026-05-03 02:10:27+00 | — |
| Last paid_at | 2026-05-03T13:09:47.000000Z | 2026-05-03 13:09:47+00 | — |
| Payment status mix (Mosaic) | {'PAID': 336, 'VOIDED': 20} | | |
| Payment status mix (Supabase) | | {'PAID': 336, 'VOIDED': 20, 'OTHER': 0} | |

**Verdict: MATCH**

### SM Megamall (2338) — 2026-05-07
_SM Megamall — recovered 149 missing bills_

| Metric | Mosaic | Supabase | Δ |
|---|---:|---:|---:|
| Raw orders returned | 309 | 307 | +2 |
| Distinct bill numbers | 307 | 307 | +0 |
| Distinct PAID bills | 305 | 305 | +0 |
| Sum PAID gross | 164,591.67 | 164,591.66 | +0.01 |
| Sum PAID net | 148,475.85 | 148,475.79 | +0.06 |
| Cancelled count | 0 | 0 | +0 |
| First paid_at | 2026-05-07T03:05:44.000000Z | 2026-05-07 03:05:44+00 | — |
| Last paid_at | 2026-05-07T13:59:16.000000Z | 2026-05-07 13:59:16+00 | — |
| Payment status mix (Mosaic) | {'PAID': 305, 'VOIDED': 2} | | |
| Payment status mix (Supabase) | | {'PAID': 305, 'VOIDED': 2, 'OTHER': 0} | |

**Verdict: MATCH**

### SM North EDSA (2284) — 2026-05-07
_SM North EDSA — recovered 101 missing bills_

| Metric | Mosaic | Supabase | Δ |
|---|---:|---:|---:|
| Raw orders returned | 384 | 377 | +7 |
| Distinct bill numbers | 377 | 377 | +0 |
| Distinct PAID bills | 370 | 370 | +0 |
| Sum PAID gross | 203,358.04 | 203,358.04 | +0.00 |
| Sum PAID net | 184,557.68 | 184,557.62 | +0.06 |
| Cancelled count | 0 | 0 | +0 |
| First paid_at | 2026-05-07T03:03:49.000000Z | 2026-05-07 03:03:49+00 | — |
| Last paid_at | 2026-05-07T13:50:59.000000Z | 2026-05-07 13:50:59+00 | — |
| Payment status mix (Mosaic) | {'PAID': 370, 'VOIDED': 7} | | |
| Payment status mix (Supabase) | | {'PAID': 370, 'VOIDED': 7, 'OTHER': 0} | |

**Verdict: MATCH**

### Ayala Solenad (2547) — 2026-05-07
_Ayala Solenad — recovered 95 missing bills_

| Metric | Mosaic | Supabase | Δ |
|---|---:|---:|---:|
| Raw orders returned | 163 | 159 | +4 |
| Distinct bill numbers | 159 | 159 | +0 |
| Distinct PAID bills | 155 | 155 | +0 |
| Sum PAID gross | 90,323.04 | 90,323.04 | +0.00 |
| Sum PAID net | 81,692.29 | 81,692.29 | +0.00 |
| Cancelled count | 0 | 0 | +0 |
| First paid_at | 2026-05-07T04:01:12.000000Z | 2026-05-07 04:01:12+00 | — |
| Last paid_at | 2026-05-07T12:55:10.000000Z | 2026-05-07 12:55:10+00 | — |
| Payment status mix (Mosaic) | {'VOIDED': 4, 'PAID': 155} | | |
| Payment status mix (Supabase) | | {'PAID': 155, 'VOIDED': 4, 'OTHER': 0} | |

**Verdict: MATCH**

### The Grid - Rockwell (2250) — 2026-05-02
_The Grid Rockwell — synthetic-id collision case_

| Metric | Mosaic | Supabase | Δ |
|---|---:|---:|---:|
| Raw orders returned | 363 | 362 | +1 |
| Distinct bill numbers | 361 | 361 | +0 |
| Distinct PAID bills | 361 | 361 | +0 |
| Sum PAID gross | 140,740.53 | 140,800.53 | -60.00 |
| Sum PAID net | 128,384.80 | 128,438.36 | -53.56 |
| Cancelled count | 0 | 0 | +0 |
| First paid_at | 2026-05-02T02:16:11.000000Z | 2026-05-02 02:16:11+00 | — |
| Last paid_at | 2026-05-02T14:09:40.000000Z | 2026-05-02 14:09:40+00 | — |
| Payment status mix (Mosaic) | {'PAID': 361} | | |
| Payment status mix (Supabase) | | {'PAID': 362, 'VOIDED': 0, 'OTHER': 0} | |

**Verdict: MISMATCH**

### Araneta Gateway (2557) — 2026-05-03
_Araneta Gateway — credential group + collision_

| Metric | Mosaic | Supabase | Δ |
|---|---:|---:|---:|
| Raw orders returned | 262 | 261 | +1 |
| Distinct bill numbers | 261 | 261 | +0 |
| Distinct PAID bills | 260 | 260 | +0 |
| Sum PAID gross | 107,225.10 | 107,225.10 | +0.00 |
| Sum PAID net | 97,573.01 | 97,573.00 | +0.01 |
| Cancelled count | 0 | 0 | +0 |
| First paid_at | 2026-05-03T02:26:11.000000Z | 2026-05-03 02:26:11+00 | — |
| Last paid_at | 2026-05-03T13:19:50.000000Z | 2026-05-03 13:19:50+00 | — |
| Payment status mix (Mosaic) | {'PAID': 260, 'VOIDED': 1} | | |
| Payment status mix (Supabase) | | {'PAID': 260, 'VOIDED': 1, 'OTHER': 0} | |

**Verdict: MATCH**

### BF Homes (2217) — 2026-05-03
_BF Homes — recovered 106 missing bills_

| Metric | Mosaic | Supabase | Δ |
|---|---:|---:|---:|
| Raw orders returned | 289 | 273 | +16 |
| Distinct bill numbers | 273 | 273 | +0 |
| Distinct PAID bills | 257 | 257 | +0 |
| Sum PAID gross | 160,056.90 | 160,056.89 | +0.01 |
| Sum PAID net | 144,889.22 | 144,889.15 | +0.07 |
| Cancelled count | 0 | 0 | +0 |
| First paid_at | 2026-05-03T02:05:05.000000Z | 2026-05-03 02:05:05+00 | — |
| Last paid_at | 2026-05-03T13:35:39.000000Z | 2026-05-03 13:35:39+00 | — |
| Payment status mix (Mosaic) | {'PAID': 257, 'VOIDED': 16} | | |
| Payment status mix (Supabase) | | {'PAID': 257, 'VOIDED': 16, 'OTHER': 0} | |

**Verdict: MATCH**

### D'Verde Calamba (2766) — 2026-05-05
_D'Verde Calamba — small store + early-cutoff day_

| Metric | Mosaic | Supabase | Δ |
|---|---:|---:|---:|
| Raw orders returned | 82 | 81 | +1 |
| Distinct bill numbers | 81 | 81 | +0 |
| Distinct PAID bills | 80 | 80 | +0 |
| Sum PAID gross | 45,260.61 | 45,260.61 | +0.00 |
| Sum PAID net | 40,850.38 | 40,850.37 | +0.01 |
| Cancelled count | 0 | 0 | +0 |
| First paid_at | 2026-05-05T01:51:55.000000Z | 2026-05-05 01:51:55+00 | — |
| Last paid_at | 2026-05-05T12:45:49.000000Z | 2026-05-05 12:45:49+00 | — |
| Payment status mix (Mosaic) | {'PAID': 80, 'VOIDED': 1} | | |
| Payment status mix (Supabase) | | {'PAID': 80, 'VOIDED': 1, 'OTHER': 0} | |

**Verdict: MATCH**

### SM Bicutan (2412) — 2026-05-05
_SM Bicutan — control mid-volume Tue_

| Metric | Mosaic | Supabase | Δ |
|---|---:|---:|---:|
| Raw orders returned | 172 | 171 | +1 |
| Distinct bill numbers | 171 | 171 | +0 |
| Distinct PAID bills | 170 | 170 | +0 |
| Sum PAID gross | 83,107.51 | 83,107.51 | +0.00 |
| Sum PAID net | 75,511.38 | 75,511.35 | +0.03 |
| Cancelled count | 0 | 0 | +0 |
| First paid_at | 2026-05-05T03:09:55.000000Z | 2026-05-05 03:09:55+00 | — |
| Last paid_at | 2026-05-05T13:17:34.000000Z | 2026-05-05 13:17:34+00 | — |
| Payment status mix (Mosaic) | {'PAID': 170, 'VOIDED': 1} | | |
| Payment status mix (Supabase) | | {'PAID': 170, 'VOIDED': 1, 'OTHER': 0} | |

**Verdict: MATCH**

### SM Caloocan (2464) — 2026-05-04
_SM Caloocan — control normal Mon_

| Metric | Mosaic | Supabase | Δ |
|---|---:|---:|---:|
| Raw orders returned | 121 | 121 | +0 |
| Distinct bill numbers | 121 | 121 | +0 |
| Distinct PAID bills | 121 | 121 | +0 |
| Sum PAID gross | 50,792.78 | 50,792.78 | +0.00 |
| Sum PAID net | 46,377.61 | 46,377.60 | +0.01 |
| Cancelled count | 0 | 0 | +0 |
| First paid_at | 2026-05-04T03:25:44.000000Z | 2026-05-04 03:25:44+00 | — |
| Last paid_at | 2026-05-04T12:49:42.000000Z | 2026-05-04 12:49:42+00 | — |
| Payment status mix (Mosaic) | {'PAID': 121} | | |
| Payment status mix (Supabase) | | {'PAID': 121, 'VOIDED': 0, 'OTHER': 0} | |

**Verdict: MATCH**

### Megawide PITX (2179) — 2026-05-02
_Megawide PITX — control weekend_

| Metric | Mosaic | Supabase | Δ |
|---|---:|---:|---:|
| Raw orders returned | 149 | 145 | +4 |
| Distinct bill numbers | 145 | 145 | +0 |
| Distinct PAID bills | 142 | 142 | +0 |
| Sum PAID gross | 51,459.81 | 51,459.81 | +0.00 |
| Sum PAID net | 46,684.26 | 46,684.25 | +0.01 |
| Cancelled count | 0 | 0 | +0 |
| First paid_at | 2026-05-02T00:58:57.000000Z | 2026-05-02 00:58:57+00 | — |
| Last paid_at | 2026-05-02T12:25:13.000000Z | 2026-05-02 12:25:13+00 | — |
| Payment status mix (Mosaic) | {'PAID': 142, 'VOIDED': 3} | | |
| Payment status mix (Supabase) | | {'PAID': 142, 'VOIDED': 3, 'OTHER': 0} | |

**Verdict: MATCH**

### Ayala Market Market (2287) — 2026-05-05
_Ayala Market Market — was 61 missing bills_

| Metric | Mosaic | Supabase | Δ |
|---|---:|---:|---:|
| Raw orders returned | 239 | 232 | +7 |
| Distinct bill numbers | 232 | 232 | +0 |
| Distinct PAID bills | 229 | 229 | +0 |
| Sum PAID gross | 101,736.50 | 101,736.49 | +0.01 |
| Sum PAID net | 92,115.48 | 92,115.45 | +0.03 |
| Cancelled count | 0 | 0 | +0 |
| First paid_at | 2026-05-05T02:05:15.000000Z | 2026-05-05 02:05:15+00 | — |
| Last paid_at | 2026-05-05T13:12:04.000000Z | 2026-05-05 13:12:04+00 | — |
| Payment status mix (Mosaic) | {'PAID': 229, 'VOIDED': 3} | | |
| Payment status mix (Supabase) | | {'PAID': 229, 'VOIDED': 3, 'OTHER': 0} | |

**Verdict: MATCH**

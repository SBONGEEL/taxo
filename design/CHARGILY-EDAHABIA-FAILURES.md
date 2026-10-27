# Chargily — failed EDAHABIA checkouts (TAXO, Algeria) — for Chargily support

**Merchant**: TAXO · **Mode**: live (`pay.chargily.net/api/v2`, `livemode: true`) · **Period**: since 2026-10-14 · **Read from**: Chargily API
`GET /checkouts` on 2026-10-27, cross-checked with TAXO's own records. **No customer name, phone, email or card is included.**

## 1) EDAHABIA — every live attempt ended `failed` (6 of 6)

| Checkout id | Created (UTC) | Algeria time | Amount | Chargily status | Last update (UTC) | Purpose | Payer |
|---|---|---|---|---|---|---|---|
| `01m509934a5n9wm00xhzh0mvx0` | 2026-10-15 17:20:39 | 18:20 | 200 DZD | `failed` | 2026-10-15 17:50:15 (+30 min) | subscription | user A (captain) |
| `01m509d4jz3c64fge0v9aez8j1` | 2026-10-15 17:22:52 | 18:22 | 200 DZD | `failed` | 2026-10-15 17:50:09 (+27 min) | subscription | user A (captain) |
| `01m5607x9cnhkm9gzqz3qc8dma` | 2026-10-17 22:38:10 | 23:38 | 500 DZD | `failed` | 2026-10-17 23:05:12 (+27 min) | wallet_topup | TAXO internal test account |
| `01m5dqjpe5rkeah97v60w4p3dn` | 2026-10-20 22:40:41 | 23:40 | 200 DZD | `failed` | 2026-10-20 23:10:11 (+30 min) | subscription | user B (captain) |
| `01m5yxxz9sjp70ye765fcy7t8t` | 2026-10-27 14:58:48 | 15:58 | 200 DZD | `failed` | 2026-10-27 15:25:09 (+26 min) | subscription | user A (captain) |
| `01m5yzzfkzqpv1k8kzh2z1z3f8` | 2026-10-27 15:34:34 | 16:34 | 200 DZD | `failed` | 2026-10-27 16:00:16 (+26 min) | subscription | user B (captain) |

**What the payer reports (27 Oct, checkout `01m5yzzfkzqpv1k8kzh2z1z3f8`)**: TAXO → Chargily → EDAHABIA → card page on `epay.poste.dz`
(order **WPlBrqlpb3**, 200.00 DZD, page said the session ends at 16:39 Algeria time) → card entered → **confirm** → the browser went to
**Google**, not back to Chargily. **No money was deducted.** Repeatable. Chargily marked the checkout `failed` about 26 minutes later.

**Our side (checked)**: `success_url` and `failure_url` are `https://driver.tajora.ly/wallet/pay/return` — a live HTTPS page (HTTP 200). CIB
checkouts in the same period reach `processing`, so the failure is specific to EDAHABIA.

## 2) CIB — checkouts still `processing` at Chargily (4)

| Checkout id | Created (UTC) | Algeria time | Amount | Chargily status | Last update (UTC) | Purpose | Payer |
|---|---|---|---|---|---|---|---|
| `01m5094mpg0112zt8cpg4yjtth` | 2026-10-15 17:18:13 | 18:18 | 200 DZD | `processing` | 2026-10-15 18:05:08 (+47 min) | subscription | user A (captain) |
| `01m5604savhydn4r6b527zhpex` | 2026-10-17 22:36:27 | 23:36 | 500 DZD | `processing` | 2026-10-18 03:20:08 (+284 min) | wallet_topup | TAXO internal test account |
| `01m57r8sgytc2ncdn6jw487etm` | 2026-10-18 14:57:19 | 15:57 | 200 DZD | `processing` | 2026-10-18 14:57:25 (+0 min) | subscription | user A (captain) |
| `01m57r9rn8swvnebwj2kb3ptzm` | 2026-10-18 14:57:51 | 15:57 | 200 DZD | `processing` | 2026-10-18 14:58:04 (+0 min) | subscription | user A (captain) |

These never reached `paid` or `failed`; TAXO cancelled them on its side after the payment window (nothing credited).

## Questions for Chargily

1. **Why does every EDAHABIA payment for this merchant fail?** Is EDAHABIA fully activated for our live account with Algérie Poste?
   Please share the Algérie Poste / SATIM error behind each `failed` checkout above.
2. **Why does `epay.poste.dz` send the payer to Google after "confirm"** instead of back to Chargily (`/payments/failure/...`)?
3. **How long is the EDAHABIA session** on `epay.poste.dz` — from checkout creation or from opening the card page?
4. **CIB checkouts stuck in `processing`** (table 2): what is their final state, and was any money taken?

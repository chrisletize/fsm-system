# FieldKit — Design Doc Addendum
*Session: October 2026 | Topic: Card Payments — FieldKit pay-links and the LKit billing site*
*Written to match FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md conventions. No migration yet — see "What blocks the build".*

---

## The problem this solves

FieldKit produces invoices and statements but has no way to take a card. There
is no payment processor integrated anywhere in the codebase — verified
2026-10-01, no Stripe/Square/Authorize.net/Braintree/PayPal references at all.
`payment_methods` does contain a "Credit Card" row, but that is only a manual
record that a card was charged *somewhere else*; nothing is authorized,
captured or reconciled by the system.

Two separate needs surfaced on 2026-10-01:

1. **FieldKit** — the four service companies' customers should be able to pay a
   service invoice by card. Volume is expected to be **low**: per Chris, after
   talking it through with Michele, "we mostly only take checks vs credit cards
   at this point anyways, we just need the credit card processing for
   flexibility for residential customers."
2. **LKit** — a new, separate site where Chris's own company bills the four
   service companies it supports. Different payer, different scale, different
   risk profile entirely.

These are deliberately treated as two deployments sharing one payment layer,
not one system with a company switch.

## Core decision: pay-links, not a portal

Settled 2026-10-01 after walking the trade-offs, and confirmed on the FieldKit
side with Michele. **Both systems use tokenized pay-links. Neither gets a
customer portal.**

Explicitly ruled out, for both: customer accounts/logins, invoice and payment
history browsing, saved cards, autopay. Do not build toward these.

The reasoning:

- The service companies have **thousands of customers**, most of whom receive a
  couple of invoices a year. Provisioning and supporting accounts for that
  population — password resets landing on the office every week — costs more
  than it returns, and adoption would be poor.
- A property manager will not create an account to pay a $400 invoice. A link
  that opens straight onto a hosted payment page converts; a login wall does
  not.
- FieldKit is **one database per company with no shared table** (see CLAUDE.md).
  A portal would need a single identity for a property manager who is a
  customer of both Get a Grip and Kleanit Charlotte, which means either
  cross-company identity — cutting directly against the architecture — or
  making them log in separately per company, which is worse than no portal.
- A pay-link has a far smaller attack surface, which matters because this is
  the first part of the system exposed to the public internet.

A full portal remains a *maybe someday* for **LKit only**, where the customer
base is a handful of related companies rather than thousands of strangers. It is
not in scope here.

### Statement-aware links

Links must be able to cover **a statement balance spanning several invoices**,
not just one invoice. This is the one genuine portal benefit worth keeping: a
property management company with many properties wants to settle one balance,
not click twelve links. The statements system already exists (sibling project at
`~/docker/statements/`, which generates per-customer and batch statements), so a
link scoped to a statement is the natural unit alongside a link scoped to a
single invoice.

## Core decision: processor-agnostic, hosted and tokenized

**Hosted/tokenized.** Card data never touches FieldKit's or LKit's servers. The
payment page is the processor's (redirect or their hosted fields), and what comes
back is a token plus a transaction id. This is the decision that most constrains
everything else and it was taken deliberately — it keeps PCI scope at the
smallest tier rather than putting card entry on our own infrastructure.

**Processor-agnostic.** Chris expects to change processors over time, for both
systems. So:

- One internal provider interface, with a thin adapter per processor.
- Every payment stores **which provider** handled it and **that provider's
  transaction id**.
- No processor-specific field, status string or error code leaks into business
  logic or templates. Business code sees our own vocabulary; the adapter
  translates.

One honest caveat to carry forward: **one-off payments port easily, stored card
tokens do not.** Vaulted cards are processor-specific, so if saved cards or
autopay are ever added, switching processors later means a vault migration.
Flexibility is cheap precisely as long as we do not store cards — which is
another reason the no-saved-cards decision above is worth holding to.

## Pricing: LKit dual-prices, FieldKit (recommended) does not

### LKit: dual pricing

LKit posts a **regular (card) price** and a **discounted price for check or
debit**, sized to cover the card cost. Chris arrived at this himself, and it is
the right structure: a discount is not a surcharge, so it sidesteps both of the
rules that make a flat "+3.5% for card" a problem —

- Visa caps credit **surcharges** at 3% (lowered from 4% in 2023; Mastercard 4%),
  and a surcharge may never exceed actual cost of acceptance. 3.5% as a surcharge
  is over Visa's cap. As a discount off the posted price, the cap does not apply.
- Surcharging **debit and prepaid cards is prohibited** under US network rules
  even when run as credit. Discounting for debit is not surcharging, so grouping
  debit with check is fine.

**The math, which direction matters:**

```
check/debit price = card price x 0.965        <- correct
card price        = check price x 1.035       <- leaves ~0.12% uncovered
```

The fee is charged on the amount actually run, so grossing up the check price by
3.5% does not recover 3.5%. Set the card price as the posted price and derive the
check price downward from it.

Two notes: debit is not free to process (usually well under 1%), so bundling it
with check means absorbing that — a deliberate choice, not an oversight. And any
processor-sold "cash discount program" must be confirmed to be genuine dual
pricing; some are repackaged surcharging that inherits every rule above.

### FieldKit: no surcharge in v1 (recommended)

**Recommendation, pending Chris's confirmation: FieldKit neither surcharges nor
dual-prices in v1.** Absorb the fee on the small number of residential card
payments.

The original ask was for work orders to show two totals — one for check/cash and
one 3.5% higher for card, customer's choice. That is a reasonable thing to want,
but it collides with the invoice lifecycle: **FieldKit deliberately freezes
invoice totals at Hardened/Sent**, because the tax engine resolves and freezes
the rate that applied on the effective date, and because silently changing a
total after the customer has a copy makes the office's copy disagree with
theirs. A total that is not knowable until the payer chooses a method fights that
directly.

Given card volume is low and mostly residential, skipping it in v1 removes:

- the frozen-total conflict,
- per-company and per-customer surcharge configuration,
- the is-the-surcharge-taxable question (varies by state; NC and FL both in play,
  and it would feed the cash-basis tax engine),
- and credit-vs-debit detection, which a blanket 3.5% would require to stay
  compliant.

If it is wanted later, the shape that fits the existing model is a **separate fee
recorded against the payment**, with the invoice showing both prices
informationally — never mutating a frozen invoice. Decide that explicitly rather
than discovering it mid-build.

## Data model

### What already exists and is reused

The receivables side needs no reshaping. In particular:

- `payments` already carries `status`, `voided_at/by`, `void_reason`, and
  `refunded_amount / refunded_at / refund_reference / refund_notes`. Refunds are
  already modelled.
- `payment_applications` already has **`reverses_application_id`** — a reversal
  is a new row that reverses a prior application, not a mutation of it. This is
  exactly the right shape for a chargeback, and it means the accounting for
  "money came back out" already exists and is already correct for cash-basis
  reporting (the reversal is an event on its own date, not an edit to the
  original payment's date).

A successful card payment therefore lands as an ordinary `payments` row plus one
or more `payment_applications` rows, with `payment_method_id` pointing at the
existing "Credit Card" method. Nothing downstream — balances, statements, the
tax report, the invoice display status — needs to know the money arrived online.

### New: provider columns on `payments`

```sql
ALTER TABLE payments
    ADD COLUMN payment_provider        VARCHAR(40),   -- 'stripe', 'square', ... NULL for manual entries
    ADD COLUMN provider_transaction_id VARCHAR(255),  -- the processor's id, for reconciliation + refunds
    ADD COLUMN provider_fee            NUMERIC(12,2); -- what the processor took, if reported
```

`payment_provider IS NULL` means a human keyed it in, which is every existing
row and will remain the common case.

### New: `payment_links`

One row per link issued. A link is **single-purpose and expiring** — it names
what it covers and for how much, so a forwarded link cannot be turned into a
window onto anything else.

```sql
CREATE TABLE payment_links (
    id              SERIAL PRIMARY KEY,
    token           VARCHAR(64) NOT NULL UNIQUE,   -- app-generated, high entropy; the only thing in the URL
    scope           VARCHAR(20) NOT NULL CHECK (scope IN ('invoice', 'statement')),
    invoice_id      INTEGER REFERENCES invoices(id),  -- set when scope = 'invoice'
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    amount_due      NUMERIC(12,2) NOT NULL,        -- snapshot at issue time
    expires_at      TIMESTAMP NOT NULL,
    paid_at         TIMESTAMP NULL,
    payment_id      INTEGER REFERENCES payments(id),
    -- audit + soft delete per CLAUDE.md's blanket rule
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);
```

Notes on the deliberate choices here:

- **The token is the only credential.** It is generated by us (`secrets`), never
  derived from an invoice number or customer id, so it is not guessable and
  carries no information. Same principle as `work_order_attachments.stored_filename`
  (migration 030): nothing user- or sequence-derived in a public identifier.
- **`amount_due` is a snapshot, not a live lookup.** If the balance changes after
  the link goes out — a check arrives, a credit is applied — the link must not
  silently charge a stale amount. On open, the page re-reads the live balance and
  refuses the payment if it no longer matches, rather than charging the snapshot.
- **Expiry is mandatory, not optional.** A link that works forever is a
  liability; re-issuing is cheap.
- A statement-scoped link has no single `invoice_id`; it resolves to the
  customer's open invoices at payment time and applies across them oldest-first,
  which is the behaviour the existing application model already supports.

### New: `payment_webhook_events`

```sql
CREATE TABLE payment_webhook_events (
    id                  SERIAL PRIMARY KEY,
    payment_provider    VARCHAR(40) NOT NULL,
    provider_event_id   VARCHAR(255) NOT NULL,   -- the processor's own event id
    event_type          VARCHAR(80)  NOT NULL,   -- normalized by the adapter, not the raw provider string
    payload             JSONB,
    received_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at        TIMESTAMP NULL,
    process_error       TEXT,
    UNIQUE (payment_provider, provider_event_id)
);
```

The `UNIQUE (payment_provider, provider_event_id)` is the whole point: processors
retry webhooks, and the same event will arrive more than once. Insert-first,
then act, so a duplicate delivery is a no-op rather than a double-applied
payment. Keeping the raw `payload` means a mis-processed event can be replayed
after a bug fix instead of being reconstructed from the processor's dashboard.

## Money moving without anyone clicking: webhooks

This is the part that differs most from everything else in FieldKit. Every other
write in this system happens because a logged-in human submitted a form. Card
payments do not:

- A payment can complete **after** the customer closes the tab, so the browser
  redirect is not a reliable signal of success. The webhook is the source of
  truth; the redirect is only a convenience for the payer.
- A **chargeback** arrives days or weeks later, unprompted, and the money is
  already gone before we hear about it.

So the webhook endpoint is a first-class part of the design, not a late add-on:
signature-verified (every processor signs; verify before trusting), idempotent
via the table above, and never dependent on a session.

## Refunds and chargebacks

**Refunds** are initiated by the office and are already modelled: set
`refunded_amount / refunded_at / refund_reference`, and write a reversing
`payment_applications` row dated the day of the refund. Where a card was
surcharged or dual-priced, the fee portion is refunded proportionally. Cash-basis
reporting follows automatically because the reversal carries its own date.

**Chargebacks** are not optional and cannot be refused — the bank pulls the money
and adds a fee (typically $15–25), then gives a short window to contest. Design
implications:

- Arrive by webhook; recorded as a reversing application plus a `payments.status`
  change, never by editing the original payment.
- The office needs to see that an invoice's money went back out, so a disputed
  state is likely wanted on the invoice display status (derived, like every other
  status in this codebase — not a stored second source of truth).
- **Disputes are won with documentation**, and FieldKit already holds the right
  evidence: signed occupied-release PDFs (migration 030), completion notes,
  status history with timestamps, and per-unit equipment deploy/retrieve records
  (migration 031). Worth noting that the release-form work became a
  dispute-defence asset as a side effect.

**For LKit specifically, this is close to a non-issue.** The payers are the four
service companies Chris is part of; he would settle any problem directly and
adjust his own tax reporting rather than routing it through the processor. That
reasoning holds for refunds, which nobody is obliged to run through a processor.
It does not generalise to chargebacks — but with these payers, they will not
realistically occur.

## Security posture

- Card data never reaches our servers (hosted/tokenized). No PAN, no CVV, no
  expiry stored anywhere, ever.
- The pay-link token is the only public credential, is app-generated and
  high-entropy, expires, and is single-purpose.
- Webhook signatures verified before any payload is trusted.
- The payment surface is **public internet**, unlike the rest of FieldKit which
  sits behind `login_required`. That argues for the LKit site being its own
  deployment (as the sibling `statements` project already is) rather than new
  public routes inside the internal app, and for the FieldKit pay-link page
  being the narrowest possible public route — one token in, one hosted redirect
  out, no customer browsing.
- Merchant descriptor matters operationally: a payer who does not recognise the
  name on their statement files a chargeback. The descriptor should read as the
  company that sent the invoice, not as LKit or the processor.

## Build sequence

**LKit first.** It is the low-stakes place to prove the hosted-page and webhook
pattern: a handful of related payers, effectively zero dispute risk, no tax
engine entanglement, and pricing that is two numbers. Once it works, the same
adapter and webhook handling drop into FieldKit, where thousands of customers and
cash-basis tax logic make mistakes expensive.

The counterargument, recorded honestly: LKit needs a new app, domain and
deployment before any payment code runs at all, whereas FieldKit already has the
invoices, statements and customers sitting there — so FieldKit pay-links would
ship sooner if seeing something work matters more than sequencing the risk.

## What blocks the build

1. **Processor choice.** The abstraction can be designed without it; the first
   adapter cannot be written against nothing. Questions that actually matter:
   card-not-present rate, debit/ACH pricing separately, hosted payment page
   (redirect or hosted fields), support for a compliant dual-pricing program,
   signed and replayable webhooks for both payments and disputes, and whether an
   existing merchant account at any of the four companies can be reused.
2. **Confirmation that FieldKit v1 skips surcharging** (recommended above).
3. **Whether a surcharge/discount is taxable in NC and FL** — only needed if (2)
   goes the other way.

Items 2 and 3 are decisions. Item 1 is a business negotiation. None of the three
require code to resolve, and all three change what the code looks like, which is
why this document exists before the migration does.

## Deliberately not in scope

Customer accounts or logins. Invoice/payment history browsing. Saved cards.
Autopay. Recurring billing. ACH (worth revisiting later for the LKit side, where
the payers are businesses writing large checks and ACH is far cheaper than
cards — but not v1).

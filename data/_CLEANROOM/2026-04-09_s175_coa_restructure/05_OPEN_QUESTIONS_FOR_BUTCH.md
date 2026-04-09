# Open Questions for Butch Formoso (S175 Blockers)

**Status:** Plan rewrite is ready to proceed mechanically. These 3 questions are the only items that **block execution** of Phase 1 (first franchise fee collection under Fork 1). Mechanical plan rewrite can happen in parallel — execution cannot start until Butch answers.

**How to send:** Single message to Accounting Private (Google Chat space `spaces/AAAA9RN0JZQ`) tagging Butch (`users/105250372171687902932`). Phrase questions directly, attach the Collection Agent Letter draft for context. Draft ready in `tmp/send_butch_s175_questions.py` (to be created with the pattern from `tmp/send_butch_coa_question.py`).

---

## OQ-1 (CRITICAL — blocks Phase 1) — BFC BIR OR booklet status

**Question:**
> Butch — for the Fork 1 collection-agent model to work, BFC needs to issue its own Official Receipts for franchise fees (not BEI). Does BEBANG FRANCHISE CORP. already have a printed + registered OR booklet from RDO 044? If not, what's the timeline to print one?

**Why it blocks:** The collection-agent letter (§4.1) requires BFC to issue the OR. If BFC has no OR booklet, **no franchise fee can be collected at all** during the interim — not by BEI, not by BFC. The letter cannot take effect.

**Possible answers + impact:**
- **A. "BFC has an OR booklet already":** Phase 1 can proceed immediately after Company creation. Letter signs, first collection happens same day.
- **B. "BFC has no OR booklet, printing takes ~2 weeks":** Phase 1 still proceeds (BFC Company creation + template COA + intercompany accounts), but Phase 1 execution does NOT include collecting any franchise fees until BFC's OR booklet arrives. Phase 1 becomes "GL structure ready, collection paused".
- **C. "BFC is not VAT-ready yet, needs BIR supplementary registration":** Then even an OR booklet wouldn't work — BFC first needs to operationalize VAT filing at RDO 044. Delay 3-4 weeks. Consider Fork 2 (interim BEI revenue) as stopgap with planned Phase 2 restatement — but this loses the substance-over-form cleanness.

**Recommendation:** If answer is A, proceed. If B, proceed with paused collection. If C, escalate — neither Fork 1 nor Fork 2 works cleanly until BFC is BIR-operational.

---

## OQ-2 (HIGH — affects interim VAT cash flow) — BFC Output VAT payment mechanism

**Question:**
> Butch — once BFC starts invoicing franchise fees, BFC will owe 12% Output VAT to BIR on its 2550Q filings. BFC has no operating bank account. How should we fund BFC's VAT payment to BIR?
>
> **Option A:** BEI advances the VAT amount to BFC (recorded as an intercompany advance on both books). BFC uses the advance to pay BIR. At cutover, settled as part of the overall sweep.
>
> **Option B:** BEI releases a partial sweep of the accumulated `DUE TO BFC` cash specifically to pay BFC's VAT obligation at each 2550Q filing. Effectively, BFC's own money is paying BFC's own VAT, with BEI acting as cash conduit.
>
> Both are clean. Option B is simpler (no new accounts). Which do you prefer?

**Why it matters:** PH BIR does not accept third-party VAT payments — the payment must come from the taxpayer's own bank account or an authorized representative. BFC has no bank account during interim, so we need a workaround. Both options above satisfy BIR mechanically (Option A is an intercompany loan; Option B is BEI acting as BFC's authorized representative for the VAT payment only).

**Recommended default:** **Option B** — simpler, no new accounts, preserves the collection-agent framing.

**Implementation impact:** Option A adds 2 new accounts (`1104300 ADVANCES TO BFC - BEI`, `2104300 DUE TO BEI - BFC`). Option B is zero new accounts. Cleanroom `01_CANONICAL_COA_TEMPLATE.md` Section B reflects Option B as the default.

---

## OQ-3 (MEDIUM — affects cutover trigger definition) — What does "BFC operating bank account" mean?

**Question:**
> Butch — the collection-agent letter auto-terminates when BFC has a "fully opened and tested" operating bank account. What should "tested" mean in practice?
>
> **Option A:** First successful deposit (cash or check).
> **Option B:** First successful online transfer received from a third party.
> **Option C:** Both a successful receive AND a successful outbound payment cycle completed.
>
> Juanna Alcober is checking with BDO and UnionBank on 2026-04-10 per your chat. Would be good to lock this now so we're not ambiguous on cutover day.

**Why it matters:** The cutover date is when BEI stops collecting as agent and franchisees pay BFC directly. If the trigger is too weak (just "account number issued by bank"), BFC might not actually be able to receive funds on day 1. If it's too strong ("30 days of operation"), we delay cutover unnecessarily.

**Recommended default:** **Option C** — full receive-and-pay cycle tested. Safest. Probably adds 3-5 days to the timeline after the bank account is technically open.

**Implementation impact:** Nothing changes in S175 execution. This just defines when S175's Fork 1 interim period ends and a separate Phase 2 sprint begins.

---

## OQ-4 (LOW — optional clarification) — BEI input_vat_goods_account is empty

**Observation (not a question):**
> Butch — Phase A audit found that `BEI Settings.input_vat_goods_account` is empty (no account linked). This is unrelated to S175 but likely affects BEI procurement VAT postings. Want me to add this to a separate config-fix task, or ignore it for now?

**Why raised:** Found incidentally during Phase A audit. Not in S175 scope, but worth flagging before Butch discovers it on his own. The fix is a simple `frappe.db.set_single_value("BEI Settings", "input_vat_goods_account", "INPUT VAT - GOODS - Bebang Enterprise Inc.")` — the account exists, it just isn't linked.

**Not a blocker.** Include for awareness only.

---

## OQ-5 (LOW — new) — JV fee GL routing confirmation

**Question:**
> Butch — the signed Grand Central Gabaldon JV Agreement routes 5% marketing + 5% e-commerce + ₱2M Brand Growth Fee **to BEI**, not BFC. This is permanent (not part of Fork 1). I'm planning to post JV marketing to `4000234 MARKETING FEES - BEI`, JV e-comm to `4000235 E-COMMERCE FEES - BEI`, and JV Brand Growth Fee to legacy `4000005 BRAND GROWTH FEE INCOME - BEI` (kept outside the canonical template). Does that match how you'd want to see it in the P&L, or do you want the JV fees under their own distinct sub-group so they're separable from any future BFC fees that might eventually also land on BEI?

**Why it matters:** BEI's `4000234` and `4000235` will hold JV fees permanently. If BFC ever starts billing BEI for services (the Phase 2 intercompany services agreement), those services aren't franchise fees and shouldn't mix. Customer Group filtering (`JV Partners` vs `BFC Franchisees`) is one way to separate them within the same account. Alternative: a dedicated `4000236 JV FEES - BEI` or `4000105 JV INCOME - BEI` sub-group.

**Recommended default:** Keep JV fees on `4000234`/`4000235` with Customer Group separation for now. Easy to restructure later if needed.

---

## Response format

Attach to the Chat message: the Collection Agent Letter draft PDF (converted from `04_BEI_BFC_Collection_Agent_Letter_DRAFT.md`) + this file as a PDF or a markdown-rendered image.

Tag Butch. Wait for his answers before running Phase 1 execution of S175.

---

## Decision-tree summary

```
Butch answers OQ-1:
├── A (OR booklet exists)          → Fork 1 full-go. Run S175 Phase 1-11.
├── B (OR booklet in 2 weeks)      → Fork 1 partial-go. Run S175 Phase 1-10 now (all GL structure),
│                                     pause Phase 11 closeout. Run first collection when booklet arrives.
└── C (BFC not BIR-ready)          → STOP. Escalate. Need to decide: delay S175 or fall back to Fork 2.

Butch answers OQ-2:
├── Option A (VAT advance)          → Add 2 intercompany advance accounts to Phase 6.
└── Option B (partial sweep)        → Default. No change to plan.

Butch answers OQ-3:
├── Option A/B/C                    → Update letter §5 termination clause. No impact on Phase 1 execution.

Butch answers OQ-4:
├── "fix it"                        → Add 1 line to Phase 7 or separate config-fix task.
└── "later"                         → Skip.

Butch answers OQ-5:
├── "keep on 4000234/5"             → Default. No change.
├── "separate sub-group"            → Add `4000236 JV FEES - BEI` to template.
```

Once OQ-1/OQ-2/OQ-3 are answered, the plan rewrite proceeds to execution. OQ-4 and OQ-5 are parallel.

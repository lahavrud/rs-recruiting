# Admin Redesign — Design Doc

**Status:** Proposal · **Scope:** the whole admin area (Dashboard, Companies, Jobs, Applications, Candidates) · **Driver:** preparing the admin for real users (launch).

This document is the reference to build against over multiple PRs. It is intentionally opinionated. It is the synthesis of a full code-read review of every admin surface; file:line citations point at the current implementation so each claim is checkable.

---

## 1. The problem in one sentence

The admin is organised around the **backend pipeline** (four flat, co-equal lists: Companies, Jobs, Applications, Candidates) instead of the **domain**, which has only two entities that actually own data — **Companies** and **Candidates** — with everything else derived from them.

Symptoms this causes, all found in the current code:

- Records are read-only **dead-ends** that eject you on every interaction (a candidate's only action is *delete*; clicking their application or a match navigates you away — `CandidateRecordPane.tsx:79`, `CandidateApplicationsPanel.tsx:99`, `CandidateMatchesPanel.tsx:44`).
- The same data gets **re-fetched and client-joined** in four places because company name isn't on the payloads (`AdminApplicationsPage.tsx:160`, `useTriageQueue.ts:51`, `CandidateApplicationsPanel.tsx:52`, `AdminJobsPage.tsx:226`).
- **Filtering and search are page-local** (they only narrow already-loaded pages), so results are silently wrong past the first page — in every list.
- The IA is **half-migrated already**: Jobs, Applications, and Candidates moved to a routed master-detail workspace (`SplitPaneLayout` + `RecordPane`); **Companies is the only entity still on legacy tabs+modals**. The migration just never had a destination.

This doc gives it a destination.

---

## 2. First principle: fast action is the point

The primary admin needs to **act on new leads and data fast**. This is the top constraint, and it resolves cleanly against the entity-centric model rather than fighting it:

> **The entity hubs are the backbone. Speed comes from an action layer that sits on top of them.**

| Layer | Purpose | Who it serves |
|---|---|---|
| **Action layer** — Inbox + Review Queue + nav badges | "Here's what's new — act now," without needing to understand the IA underneath | Day-to-day work (the 80%) |
| **Entity hubs** — Company / Candidate records | Go deep: history, context, full relationships | "Who is this, what happened" (the 20%) |

Both reference the same data. The queue is the **fast path** (new thing → decide); the hub is the **deep path** (understand the entity).

### Speed guarantees we design for

1. **The front door is an action queue, not a list.** On login the admin sees real counts — "3 new company leads · 5 applications waiting · 2 jobs to review" — and can act on each **without opening a record**.
2. **One-tap decisions inline.** Approve / invite / reject straight from a queue row. Optimistic with a 5-second undo, so a misclick costs nothing (this ergonomics already exists in triage — `useTriageSession.ts:130-154` — we keep it and generalise it).
3. **Keyboard- and thumb-first.** Desktop: `A`/`R` + auto-advance. Mobile: a fixed bottom action bar so leads can be cleared one-thumbed from a phone (triage already proves this works — `AdminApplicationsTriagePage.tsx:293-317`).
4. **New work is visible from everywhere** — count badges on the nav spine plus a "new since last visit" marker, so nothing waits unseen.

---

## 3. The model: Supply & Demand

```
DEMAND                              SUPPLY
Companies  ──owns──▶ Jobs           Candidates
     │                  │                │
     └──── Applications (Candidate × Job) ┘
                   the edge / the work
```

- **Companies** and **Candidates** are the two primary navigable entities (the two hubs).
- **Jobs** live *under* a Company (a tab on the company record), plus a global "all jobs" cross-company worklist for "everything pending review." Jobs are wholly owned by a company — `company_id` is mandatory, and `CompanyDetailDialog.tsx:28-44` already prototypes the per-company jobs list (today as a client-side hack over the first 100 jobs).
- **Applications stop being a top-level entity.** They are the *edge* between a Candidate and a Job, surfaced from both ends: a company's job shows its applicant pipeline; a candidate shows their applications. The flat Applications list demotes to a **review queue / inbox** (§6), not a primary destination.

### Navigation spine

Reorganise the flat 5-item sidebar (`Sidebar.tsx:23-29`) around the two axes:

```
  Dashboard
  ── DEMAND ──
  Companies            ▸ (badge: N pending)
  ── SUPPLY ──
  Candidates           ▸ (badge: N new)
  ── WORK ──
  Review queue         ▸ (badge: N waiting)
```

Jobs and Applications leave the top level: Jobs become a Company tab + a filter inside the global jobs worklist reached from Companies; Applications become the Review queue + per-entity panels. Count badges (currently only on the dashboard inbox) move onto the spine so work is visible from anywhere.

---

## 4. Records become workspaces, not dead-ends

Each hub record becomes a **tabbed workspace** that aggregates the entity's whole lifecycle and lets you act *in context* (drawers over the pane, not navigation away). Standardise on the existing `SplitPaneLayout` + `RecordPane` primitives — they already exist and three of four entities already use them.

### 4.1 Company record (`/admin/companies/:id` — new)

Companies is the only entity without an addressable record today (no `:id` route — `App.tsx:179`; detail is a transient `?detail=` param that gets stripped — `AdminCompaniesPage.tsx:48-63`). It cannot be deep-linked or opened in a new tab, unlike its siblings. Promote it to the same routed master-detail pattern (`JobRecordPane.tsx:40-51` is the template — fetcher, breadcrumb, not-found, rail-collapse all come free).

Tabs/sections:

- **Overview / profile** — inline-editable (kills the stacked detail→edit modal flow at `CompanyActiveTab.tsx:328-335`).
- **Lifecycle banner** — pending → approved → active, invitation-sent, `agreement_signed_at` / `privacy_accepted_at`, contract PDF link. *None of this is surfaced to admins today* despite existing on the model (`types/auth.ts:52-53`, `companies.py:55`).
- **Jobs** — backed by a new `GET /admin/jobs?company_id=` (replaces the 100-job client-side filter hack at `CompanyDetailDialog.tsx:38-47`), with per-status counts.
- **Applications-to-this-company** — a roll-up across all the company's jobs. The highest-value new view an entity-centric IA unlocks; currently impossible.
- **Contacts** — promote beyond the single contact person (the invite token already carries contact fields — `types/invites.ts:11-14`).
- **Invites & account history** + **Activity timeline** (reuse `components/admin/ActivityTimeline.tsx`, already used by candidates).

### 4.2 Candidate record (`/admin/candidates/:id` — exists, needs depth)

The scaffolding is already the best in the app (`CandidateRecordPane` aggregates applications + matches + activity) but it is a read-only viewer whose only action is delete. Make it a workspace:

- **Identity header** — name, avatar, **lead-vs-registered badge** (the `user_id` discriminator, never surfaced today), **consent/ToS status chip** (the API *returns* `consent_given_at` / `consent_policy_version` / `tos_accepted_at` / `tos_version` but the frontend type drops them — `frontend/src/types/candidates.ts:5` vs `src/schemas/candidates.py:130-133`). Inline actions: Email, Add note, Advance to job, Export data (GDPR), Delete.
- **Inline resume reader** — docked, not a modal-over-modal (`CandidateContactInfo.tsx:35`). Surface `resume_filename` and a "no embedding yet / parsing" state so empty matches are explained.
- **Applications** — status-editable *in place* (drawer over the pane), so the candidate stays the workspace.
- **Matches** — deduped against jobs already applied to (currently *not* deduped — the same job appears in both panels, `src/services/admin/candidates.py:115-123`).
- **Activity** + **Data / GDPR** (export + delete).

### 4.3 Job record (stays, nests under Company)

- Keep `/admin/jobs/:id` and the global worklist, but frame Jobs as children of a Company (breadcrumb: Company › Job). Creating a job from within a company removes the company `<select>` step (`JobCreateDialog.tsx`).
- **Candidate-match section becomes actionable.** Today matches are read-only rows that only navigate away (`JobViewBody.tsx:102`). Add in-place actions (invite to apply / email / shortlist) and surface *why* (shared tags/requirements) instead of a bare cosine ring.
- **Distinguish REJECTED from CLOSED.** Both terminate in `CLOSED` today (`jobs_workflow.py:167`, `AdminJobsPage.tsx:289`), so a rejected submission and a filled job are indistinguishable in the list. Add a distinct state or `closed_reason`.

### 4.4 One detail surface per entity

The same mutation has two+ divergent UIs today — collapse each to the inline record pane plus a single shared `<EntityActions>` component:

- Application status: a modal (`ApplicationStatusDialog`, native `<select>`) **and** an inline `StatusSegmentedControl` (`ApplicationRecordHeader.tsx:177-195`). Retire the modal.
- Jobs: a `JobDialog` modal **and** a record pane; editing stacks the modal over the pane. Approve/reject is re-implemented across **five** surfaces (table kebab, rail kebab, mobile kebab, pane header, dialog footer). Centralise.
- Companies: detail modal that closes to open an edit modal. Inline-edit in the pane instead.

---

## 5. The data layer (precondition — blocks everything)

Every area independently hits the **same three scale bugs**. "Hundreds of records" breaks all of them, so this lands first.

1. **Client-side filtering over lazy-loaded pages.** Filters/search only narrow *already-fetched* pages, so filtering by company shows partial results until the user scrolls enough to load more — silently wrong. Present in applications (`AdminApplicationsPage.tsx:190-207`), jobs (`AdminJobsPage.tsx:157-199`), companies (`CompanyActiveTab.tsx:73-88`), candidates. → **Move filter/search/sort server-side.** Cursor pagination already exists; some endpoints already accept `job_id`/`candidate_id` (`adminApplications.ts:8-9`) — they're just unused by the UI.
2. **`limit:100` lookup maps.** Company names are resolved client-side via `getActiveCompanies({limit:100})` in four places; past 100 companies, names degrade to `#id` and the job-contact `mailto` silently fails with "no email" even when one exists (`AdminJobsPage.tsx:226-246`). → **Embed `company_name` (+ a `company` object) and `application_count` / `match_eligible` on the Job and Application payloads** (`selectinload(Job.company)` at the call site, per the migrations rule). Kills the N+1s, the caps, and several bugs in one move.
3. **Fake counts.** Dashboard KPIs and would-be nav badges are `items.length` of a single capped page, shown as `50+` / `100+` — a ceiling, never a true total; status distributions are sampled from the first 100 rows (`AdminInbox.tsx:49-65`, `AdminStats.tsx:38-53`). → One **`GET /api/admin/overview`** aggregation endpoint with real counts + status distribution.

Also add the missing **`GET /admin/jobs?company_id=`** filter (unblocks the Company → Jobs tab) and a real **count endpoint** for the company pill counts (currently three separate `limit:100` fetches — `AdminCompaniesPage.tsx:87-107`).

---

## 6. What replaces triage

The triage page is a **mode**, and the mode is the problem: a separate `/triage` route, a `fixed inset-0` takeover that forces a bare-AppShell exception (`AppShell.tsx:360-369`), an eager load of up to 500 rows (`useTriageQueue.ts:45-73`), a parallel state machine whose decisions don't reflect into the list without a refetch, bespoke `100vw`/`200vw` transforms (`useTriageSession.ts:212-245`), and a **notes field that silently discards everything typed into it** (`TriageComponents.tsx:263-275` — local state, no save handler; real data-loss bug).

Replace the *mode* with a **review queue inside the normal master-detail shell**:

- Rail = the "needs a decision" queue (filtered to NEW). Record pane = full candidate/application context.
- Keep the good parts: keyboard-first `A`/`R` decide + auto-advance, optimistic update with a 5-second undo. Lose the separate route, the carousel, the eager 500-row load (it rides existing cursor pagination), and the notes bug (there's now only one notes control — the pane's, which persists).
- **Generalise the queue.** The same pattern serves the company-approval queue and the pending-job-review queue. One interaction model, three feeds, all reachable directly from the nav instead of a two-hop drill nobody discovers.

This is the action layer's batch surface; the dashboard inbox is its glanceable summary.

---

## 7. The dashboard

Today it is three near-identical stacked card bands where the "act on this" inbox doesn't read as more urgent than the "FYI" stats (`DashboardPage.tsx:69-80`). Restructure as **Work vs Pulse**:

- A prominent **action queue** (the inbox, with inline "start review" CTAs and one-tap actions) on `card-raised`, visually dominant.
- A subordinated **pulse strip** (KPIs + a restrained copper/gold trend treatment — there is no time dimension today; add "new this week," approval throughput, time-to-approve) on `card`.
- Push the inbox counts **onto the nav items** as badges (§3).
- **Kill QuickActions** — it triples destinations already in the sidebar and inbox (`DashboardPage.tsx:105-190`); keep only its unique "invite."
- Give the admin a **real name** (today it's derived from the email local-part — `DashboardPage.tsx:31-35`).

Minor chrome fixes folded in here: the header logo links to public `/` instead of `/dashboard` (`Header.tsx:28`); a raw untranslated role string renders in the header pill (`Header.tsx:39`).

---

## 8. Mobile (a real requirement, not an afterthought)

Master-detail rail-collapse is **desktop-only** (`SplitPaneLayout.tsx:39-47` is `hidden md:flex`); on mobile the rail stacks above the record and you scroll a long list to reach the pane. Triage is currently the *only* genuinely mobile-first surface — ironic, given it's being removed.

- **True two-level mobile pattern:** list → tap → record with a back affordance, not stacked panes. (Companies gets this for free on moving to `SplitPaneLayout`.)
- **Tabbed/segmented record bodies on mobile** so a hub is navigable without an endless scroll through stacked lazy panels.
- **Persistent bottom action bar** for queue decisions (port triage's one-thumb ergonomics — `AdminApplicationsTriagePage.tsx:293-317`).
- **Resume reader as a full-screen sheet**, not an overlay-over-overlay.
- Consider a header **command/search palette** as the cross-entity jump tool, valuable once nav is entity-nested and records are several taps deep.

---

## 9. Live bugs (folded into the relevant phase, not separate PRs)

These are real defects found during the scan; each is fixed naturally as its area is rebuilt:

| Bug | Location | Fixed in |
|---|---|---|
| Triage notes silently discarded | `TriageComponents.tsx:263` | §6 (one notes control) |
| Job "contact company" flow fully built but never called; UI uses a raw `mailto:` that loses the template + audit and fails past 100 companies | `adminJobs.ts:23` + `jobs_workflow.py:201-233` vs `AdminJobsPage.tsx:243-253` | §4.3 / §5 |
| Candidate consent/ToS data returned but stripped from the type and never shown (GDPR product) | `types/candidates.ts:5` | §4.2 |
| Matches not deduped against existing applications | `candidates.py:115-123` | §4.2 |
| Reject == Close for jobs (indistinguishable states) | `jobs_workflow.py:167` | §4.3 |
| Orphaned dead code: `ApplicationDetailDialog` (imported nowhere) | — | §10 consolidation |
| Hand-rolled header buttons instead of `<Button>` (violates frontend rules) | `AdminCompaniesPage.tsx:125-136` | §4.1 |

---

## 10. Sequencing

Dependency order, not all at once:

1. **Data layer** — server-side filter/search/sort; embed `company_name`/counts on payloads; `/admin/overview`; `?company_id=` job filter. *Unblocks everything; fixes live scale bugs.*
2. **Companies onto master-detail** — `/admin/companies/:id` + `CompanyRecordPane`. *Closes the IA inconsistency; lowest novelty (pattern exists).*
3. **Entity-hub depth** — flesh out Company + Candidate records into tabbed workspaces with in-context actions; surface dropped consent/lifecycle data.
4. **Nav spine + dashboard** — Supply/Demand grouping, nest Jobs under Companies, count badges, Work-vs-Pulse dashboard.
5. **Review queue** — replace triage with the in-shell queue; generalise to companies/jobs.
6. **Consolidation** — one detail surface per entity, shared `<EntityActions>`, retire orphaned code and duplicate modals.

---

## 11. Design-system notes

Everything here is expressible in the existing dark-luxury token system; the design system is *extended*, not replaced.

- **Net-new primitives:** `CompanyRecordPane`; a lifecycle/status badge map; a shared record **tab/segmented-control** primitive (`components/admin/`); the generalised **review queue** shell.
- **Reused as-is:** `SplitPaneLayout`, `RecordPane`, `ActivityTimeline`, `MatchList` (ring gauge), the filter-panel toolkit (`JobsFilterPanel` / `SearchableMultiSelect`), `StatusBadge` + status tokens (`success` / `warning` / `danger` / `info`).
- **No new colors needed.** Consent/lifecycle chips map onto existing status tokens; trend treatments use copper/gold.
- Replace hand-rolled buttons with `<Button>`; keep all copy in the `he` locale namespaces.

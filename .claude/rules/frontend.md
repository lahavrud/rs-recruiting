# Frontend Rules

## Design System

Dark luxury boutique aesthetic. Every color from the token system — **no hardcoded hex values**.

### Color tokens (`index.css` `@theme`)

| Token | Value | Usage |
|---|---|---|
| `card-raised` | `#1E1C1A` | Modals, elevated cards, hover targets |
| `card` | `#1A1816` | Default card/panel surfaces |
| `section` | `#181614` | Landing page dark sections |
| `well` | `#141210` | Form inputs, table headers (sunken) |
| `page` | `#121110` | Main content area |
| `void` | `#0D0B09` | Nav bars, header, auth backgrounds |
| `copper` | `#B87333` | Primary accent, CTAs, active states, eyebrow text |
| `gold` | `#C9A84C` | Hover state for copper elements |
| `copper-dark` | — | Pressed variant |
| `nickel` | — | Neutral metallic text |

Status tokens: `success`, `warning`, `danger`, `info`, `hired`.

### Typography
- Inter (weights 300–600) — weight hierarchy only, no display face
- `font-wordmark` (Cormorant Garamond) — **only** LogoBanner and landing hero. Never on body or UI headings.

### UI primitives — always import, never redefine locally

`components/ui/` holds ~35 primitives (dialogs, empty/error states, search input, skeletons, toasts, …) — **check there before writing any new primitive**; if something close exists, extend it instead. The most rule-laden ones:

- **`<Button variant="primary|ghost|danger|success" size="sm|md|lg">`** — never write button classes inline
- **`<Eyebrow>`** — `text-[10px] font-semibold uppercase tracking-widest text-copper` — never write class string inline
- **`<Field>`** — `id` prop → explicit `htmlFor` mode (public/auth); omit → `<label>`-wrap mode (admin dialogs). Never define locally.
- **`<PageHeader eyebrow subtitle? action?>`** — all page headings. `action` = badges or primary CTAs.
- **`<CompanyName name>`** — `text-copper font-medium`. Never plain text. Email templates: `_company(name)` helper.
- **`<ResumeButton>`** from `ResumeViewer` — never build a custom flow. Portals to `document.body`. iOS uses `navigator.share()` (Safari ignores `download` on blob URLs).
- **`<StatusBadge label colorCls>`** — color maps stay in the calling component
- **`inputCls`, `textareaCls`, `selectCls`** from `@/styles/forms` — never copy inline
- **`formatDate` / `formatDateLong`** from `@/utils/formatDate` — never define locally
- **`EMAIL_RE`, `MOBILE_RE`** (strict Israeli 05XXXXXXXX), **`COMPANY_ID_RE`** from `@/utils/validators`

### Component co-location

ESLint 600-line hard limit. Extract to `pages/<section>/components/`. Parent owns all state/fetching/handlers. Non-React helpers → sibling `*Utils.ts` (never exported from component files — `react-refresh/only-export-components` errors). Cross-page components → `components/ui/` or `components/admin/`.

## Error Handling

Never surface raw backend `detail` strings — may be English. Map to Hebrew `t()` keys:
- `429` → `errors.tooManyAttempts`
- `409` → `errors.emailExists` / `errors.alreadyApplied`
- `404` → `errors.notFound` / `errors.unavailable`
- `403` → `errors.accountInactive`
- default → generic Hebrew error key

## Translations

All strings in `frontend/src/locales/he/<namespace>.json` (namespace = filename: about, admin, auth, candidate, common, company, cookies, dashboard, landing, legal, nav, publicJobs, resume, ui).

- Always pass namespace: `useTranslation('admin')` + `t("admin:key")`
- Multiple namespaces: `useTranslation(['admin', 'common'])` + explicit prefix at every call site
- Never call `useTranslation()` without a namespace argument
- Write production-quality Hebrew — warm, direct phrasing. Not literal translations.

## Linting Pitfalls

- `ruff format` must pass separately from `ruff check` — run `uv run ruff format .` to fix
- `no-unused-expressions` — use `if/else` not ternary side-effects
- `react-hooks/set-state-in-effect` — use lazy `useState` initializer, not sync `setState` in `useEffect`
- `max-lines` — 600-line hard limit; extract to co-located components
- `no-magic-numbers` — extract to named constant (HTTP codes and 0/1/2/3 pre-allowed)
- `react-refresh/only-export-components` — utility exports → sibling `*Utils.ts`

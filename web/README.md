# FORGE — web client

TypeScript, Vite, React and Tailwind. Talks to the Django API in the parent
directory.

## Running it

The API has to be up first:

```bash
# terminal one, from the repository root
python manage.py runserver

# terminal two
cd web
npm install
npm run dev          # http://localhost:5173
```

Vite proxies `/api` and `/media` to `http://127.0.0.1:8000`, so development
matches production — where both are served from one host — and no CORS
configuration is needed to get started.

## Where things are

```
src/
  api/
    schema.d.ts    generated from the API — never edit by hand
    types.ts       the stable aliases the app imports
    client.ts      axios, JWT attachment, refresh queueing, error shape
    queries.ts     every query and mutation hook, and the cache key hierarchy
  components/
    ui/            the primitives: Button, Card, Field, Pill, states
    layout/        AppShell, Sidebar, AuthAside
  features/
    auth/          AuthProvider, useAuth, client-side capabilities
    projects/      the stage tracker, project card, review panel
  pages/           one file per route
  routes.tsx       the router; every page except two is lazy-loaded
```

## Regenerating API types

When the backend changes:

```bash
npm run api:types
```

This runs `manage.py spectacular` and `openapi-typescript`. `schema.d.ts` is
generated output — change the backend serializer, not this file. A rename on
the server then shows up as one compile error in `src/api/types.ts` rather
than fifty across the components.

## Things worth knowing before changing anything

**Capabilities decide what to show, never what is allowed.** `can("moderate")`
hides a button the member cannot use. The server re-checks every one of them,
and a member who forges a role in devtools gets a 403.

**Errors have one shape.** Every endpoint returns
`{"error": {"code", "detail"}}`. `toForgeError()` flattens both the sentence
form and the field-map form into one type, so no component branches on which
it got.

**Routes are code-split.** Most members open FORGE on a phone, on a connection
they pay for by the megabyte. Only sign-in and the dashboard are eager; every
other page loads on demand at 1–5 kB gzipped. Keep it that way.

**Theme tokens, not palette steps.** Components use `bg-card`, `text-strong`,
`border-line`. Those are redefined once for dark mode in `index.css`. Reaching
for `bg-white` or `text-slate-900` directly breaks dark mode in one place and
nobody notices for a month.

**Amber means earned.** `ember-*` is for levels, badges and confirmed work.
Using it as decoration devalues the one signal the platform most needs to keep
meaningful.

## Checks

```bash
npm run build        # typecheck and build
npm run lint
```

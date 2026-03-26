# HalfFull Frontend

Next.js 16 app for the HalfFull assessment flow.

## Source of truth

- App routes live in `frontend/app`
- Shared UI, hooks, data, and utilities live in `frontend/src`
- Shared non-`src` server utility lives in `frontend/lib/medgemma-safety.ts`

There is no longer a parallel `frontend/src/app` route tree. If you are changing pages, update `frontend/app`.

## Current flow

1. `/start`
2. `/consent`
3. `/assessment`
4. `/clarify`
5. `/processing`
6. `/results`

The root route `/` redirects to `/start`.

## Folder map

```text
frontend/
├── app/                 # Next.js App Router pages and API routes
├── src/components/      # Shared React components
├── src/hooks/           # Client hooks
├── src/data/            # Assessment JSON/data files
├── src/lib/             # Client/shared utilities
├── src/lib/server/      # Server-side helpers used by routes
├── lib/                 # Shared top-level utility modules
├── public/              # Static assets
└── package.json
```

## Development

```bash
cd frontend
npm install
npm run dev
```

Other commands:

```bash
npm run lint
npm run build
npm run start
```

## Notes

- The current assessment JSON uses a single active path (`full`).
- Assessment state is stored in session storage with `halffull_assessment_v2`.
- Privacy/retention helpers live in `src/lib/privacy.ts`.
- PDF/image lab extraction runs through `app/api/extract-labs/route.ts`.

## Deployment hygiene

- Make changes locally in this repo first.
- Commit and push the branch you want Vercel to build.
- Avoid editing a second copy of the frontend elsewhere.
- If something looks different between local and deployed, compare the git commit and environment variables before debugging UI behavior.

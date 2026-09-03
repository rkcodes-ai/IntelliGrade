# IntelliGrade Frontend

React 19 + TypeScript + Vite frontend for the IntelliGrade AI Answer Script
Evaluation System.

## Local development

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Runs at `http://localhost:5173`. The Vite dev server proxies `/api/*` to
`http://localhost:8000` (the backend) — see `vite.config.ts`.

## Common commands

| Task                   | Command              |
| ---------------------- | -------------------- |
| Dev server             | `npm run dev`        |
| Type check             | `npm run typecheck`  |
| Lint                   | `npm run lint`       |
| Format                 | `npm run format`     |
| Unit tests (Vitest)    | `npm run test`       |
| Unit tests, watch mode | `npm run test:watch` |
| E2E tests (Playwright) | `npm run test:e2e`   |
| Production build       | `npm run build`      |

## Layout

```
src/
├── main.tsx / App.tsx     # entrypoint + provider composition
├── routes/                 # React Router route tree
├── layouts/                  # AuthLayout, DashboardLayout (structural shells)
├── pages/                      # route-level page components
├── components/
│   ├── ui/                        # shadcn/ui-style primitives (Button, Card, Spinner)
│   ├── layout/                     # Topbar, Sidebar, Footer
│   └── common/                      # ErrorBoundary, LoadingScreen
├── context/                          # ThemeProvider, ToastProvider
├── store/                              # Redux Toolkit store + slices
├── api/                                  # Axios client, React Query client, API modules
├── hooks/                                  # reusable hooks
├── config/                                   # env var validation (Zod)
├── lib/                                        # framework-agnostic helpers (cn, etc.)
├── types/                                        # shared TS types
└── tests/                                          # unit/ (Vitest) + e2e/ (Playwright)
```

No authentication, business pages, or domain state exist yet — this is the
routing/layout/theming/data-fetching foundation only. See the repo root
README for the module roadmap.

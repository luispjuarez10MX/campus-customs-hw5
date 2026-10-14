# Campus Customs – Operations Desk (frontend)

React + Vite + TypeScript dashboard for the Campus Customs agent team. It talks to the FastAPI backend at `http://localhost:8000`; to use a different URL, copy `.env.example` to `.env` and set `VITE_API_BASE`.

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # type-check + production build
```

- `src/App.tsx`: state, polling, and actions (dispatch, approve, reject, reset)
- `src/components/`: masthead, ticket board, agent roster, live activity, run summary, cash, approvals
- `src/agents.tsx`: each agent's color, glyph, and label
- `src/api.ts`: typed client for the backend routes

Design notes are in `../output/design.md`.

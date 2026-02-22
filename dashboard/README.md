# Dashboard (Phase D5)

## Environment
Copy `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

Required values:
- `NEXT_PUBLIC_API_BASE_URL` (default `http://127.0.0.1:8000`)
- `NEXT_PUBLIC_POLL_MS` (default `3000`)

## Run

```bash
# terminal 1 (API)
uvicorn api.app:app --reload --port 8000

# terminal 2 (dashboard)
cd dashboard
npm i
npm run dev
```

## Tests

```bash
cd dashboard
npm test
npm run test:e2e
```

## Auth/CORS requirements
The browser sends HttpOnly auth cookies across origins (`localhost:3000` -> `localhost:8000`) using `credentials: "include"`.
Your FastAPI CORS config must allow credentials and origin `http://127.0.0.1:3000` (or `http://localhost:3000`).

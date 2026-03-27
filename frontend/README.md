# Frontend (Vite + React)

## Environment

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Set:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Run

```bash
npm install
npm run dev
```

## API Wiring Implemented

- `POST /chat`
- `POST /hitl/respond`
- `GET /preferences/{user_id}`
- `PUT /preferences/{user_id}`

The chat view sends `conversation_history` on each turn and updates local state from backend `conversation_history`.

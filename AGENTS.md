# AGENTS.md

## Context
- Project: Intelligent Personal Assistant for scheduling and booking.
- Core architecture: FastAPI API + LangGraph agent loop + MCP calendar tools + React frontend.
- Backend runtime: Python 3.11+.
- Frontend runtime: Node + Vite + React (JS/JSX, no TypeScript).
- Source-of-truth implementation plans:
- `docs/superpowers/plans/2026-03-26-intelligent-pa-v0_1.md`
- `docs/superpowers/plans/2026-03-27-intelligent-pa-conversational-v1.md`
- Deprecated plan: `docs/superpowers/plans/2026-03-26-intelligent-pa-v0.md`.
- Note: root `README.md` is older and partially outdated; follow current code + this file.

## Tech Stack
- Backend: `fastapi`, `pydantic`, `langgraph`, `langchain`, `langchain-groq`, `langchain-community`, `requests`, `dateparser`.
- LLM: Groq via `ChatGroq` (primary), Ollama via `ChatOllama` (fallback).
- Persistence: SQLite (`app.db`) via lightweight repo classes.
- Frontend: `react`, `vite`, `framer-motion`, `lucide-react`, `tailwindcss`.
- Testing: `pytest`, `httpx`, `fastapi.testclient`.

## Directory Map
- `app/main.py`: FastAPI bootstrap and API routes (`/health`, `/chat`, `/hitl/respond`, `/preferences/*`).
- `app/schemas.py`: API request/response Pydantic contracts.
- `app/graph/state.py`: `AgentState` (extends `MessagesState`).
- `app/graph/builder.py`: LangGraph wiring (`agent -> tool_node -> tool_result -> finalizer/hitl`).
- `app/graph/nodes/agent_node.py`: tool-bound LLM call, retry/fallback for `tool_use_failed`.
- `app/graph/nodes/hitl_node.py`: writes pending action + alternatives.
- `app/graph/nodes/finalizer_node.py`: unified response finalizer (single source for normalized response payloads).
- `app/tools/calendar_proxy.py`: proxy `@tool` functions and MCP contract normalization.
- `app/services/calendar/mcp_client.py`: MCP HTTP caller (`/tools/call`).
- `app/services/time_utils.py`: natural-time parsing and date range resolution.
- `app/services/time_formatting.py`: human-friendly calendar datetime formatting for user-visible summaries.
- `app/services/hitl/pending_repo.py`: pending HITL action persistence.
- `app/services/hitl/resolve_action.py`: HITL decision resolver (builds `execution_result`, no user-facing text).
- `app/services/memory/preferences_repo.py`: user preference persistence.
- `frontend/src/App.jsx`: current primary UI (dashboard/chat/preferences).
- `frontend/src/lib/api.js`: frontend API client wrappers.
- `tests/`: backend-focused tests (`api`, `graph`, `llm`, `tools`).

## Environment
- Backend vars:
- `GROQ_API_KEY` required for Groq provider.
- `LLM_PROVIDER` default `groq`, fallback `ollama`.
- `LLM_MODEL` default `llama-3.3-70b-versatile`.
- `LLM_TEMPERATURE` default `0`.
- `LLM_MAX_TOKENS` default `1024`.
- `MCP_SERVER_URL` default `http://127.0.0.1:8080`.
- Frontend vars:
- `VITE_API_BASE_URL` (see `frontend/.env.example`, currently `http://localhost:8001`).

## Execution Commands
- Backend setup:
```powershell
cd AI_PERSONAL_ASSISTANT
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```
- Backend run:
```powershell
cd AI_PERSONAL_ASSISTANT
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8001
```
- Backend tests:
```powershell
cd AI_PERSONAL_ASSISTANT
.\venv\Scripts\Activate.ps1
python -m pytest -q
```
- Frontend setup/run:
```powershell
cd AI_PERSONAL_ASSISTANT\frontend
npm install
npm run dev
```
- Frontend quality/build:
```powershell
cd AI_PERSONAL_ASSISTANT\frontend
npm run lint
npm run build
```
- MCP dependency:
- Start the external Deciduus calendar MCP server separately and set `MCP_SERVER_URL` accordingly before testing chat flows.

## Code Patterns (Observed)
- Python style: snake_case modules/functions, type hints in signatures, small focused modules.
- API contracts: snake_case JSON keys (`user_id`, `conversation_history`, `action_id`).
- Agent state pattern: message-driven LangGraph (`MessagesState`) with `ToolNode`.
- Tooling pattern: LLM never talks to calendar API directly; it calls proxy tools in `calendar_proxy.py`.
- Tool outputs are normalized/stable dicts with `status`, plus structured subfields (`event`, `alternatives`, `events`).
- SQLite repos initialize tables in `__init__`; default DB file is `app.db`.
- Frontend pattern: JS/JSX only, React hooks, `fetch` wrappers in `src/lib/api.js`, no TS types/tsconfig.
- Current UI is mostly concentrated in `frontend/src/App.jsx`; avoid unnecessary file churn unless asked.
- MCP integration note: external `calendar-mcp` FastAPI server does not expose `/tools/call`; use `app/services/calendar/mcp_client.py` compatibility fallback (maps `mcp_google_calendar_*` tool names to direct REST endpoints).

## AI Do / Don't
- Do preserve `MessagesState` + `ToolNode` flow; avoid reintroducing linear regex router/extractor pipelines.
- Do keep Groq tool-calling reliability guards (retry/fallback on `tool_use_failed`) and avoid forcing tool choice on every turn.
- Do keep conversation continuity via `conversation_history` and preserve `[event_id=...]` in assistant history when present.
- Do add/adjust tests for any behavior change; prefer targeted tests near changed module.
- Do keep MCP tool names exactly as currently used (`mcp_google_calendar_*`) unless user explicitly asks to change.
- Don't bypass proxy tools from graph nodes or FastAPI routes for normal booking flows.
- Don't break existing response shape for `ChatResponse` or frontend expectations.
- Don't introduce TypeScript/tsconfig unless user requests a migration.
- Don't commit/push from agent sessions unless explicitly requested by user.

## Preserved Guardrails
- Implement exactly according `v0_1` plan tasks unless user explicitly overrides.
- Keep all new code under `AI_PERSONAL_ASSISTANT/`.
- Do not run git commit/push commands in agent sessions unless explicitly requested.
- Deliver implementation in testable batches and pause for user validation between batches.

## Recent Hotfixes
- Added MCP compatibility fallback in `app/services/calendar/mcp_client.py`:
- If `POST /tools/call` returns 404, fallback to direct `calendar-mcp` REST endpoints (`/calendars/...`, `/freeBusy`).
- Added free/busy normalization to `free_windows` and schedule alternatives generation for HITL.
- Added regression tests: `tests/services/test_mcp_client_compat.py`.

## Recent Conversational V1 Changes
- Added conversation router:
- `app/llm/router.py` with `ConversationMode` (`calendar_action`, `calendar_query`, `general_chat`) using LLM-first routing and heuristic fallback only on router failure.
- Updated agent flow:
- `app/graph/nodes/agent_node.py` now routes general chat turns to non-tool assistant responses and routes calendar intents to tool-calling.
- Added state fields:
- `app/graph/state.py` now includes `response_mode` and `summary`.
- Added tool-result interpreter node:
- `app/graph/nodes/tool_result_node.py` normalizes `ToolMessage` outputs into `execution_result` for query/action summaries.
- Updated graph wiring:
- `app/graph/builder.py` now uses `tool_node -> tool_result -> finalizer/hitl` to avoid repeated tool loops.
- Upgraded finalizer:
- `app/graph/nodes/finalizer_node.py` is mode-aware and prevents generic `"Done."` outputs.
- `app/llm/prompts.py` now includes `render_general_chat_prompt` and `render_finalizer_system_prompt`.
- Updated API response contract:
- `app/schemas.py` `ChatResponse` now includes `response_mode`.
- `app/main.py` now normalizes responses through finalizer payloads and uses safer summary fallback (`I need one more detail...`).
- Frontend chat UX wiring:
- `frontend/src/App.jsx` uses `response_mode` for message phrasing and improved failure response text.
- `frontend/src/lib/api.js` default backend base set to `http://localhost:8001`.
- Added tests:
- `tests/llm/test_router_mode.py`
- `tests/graph/test_tool_result_node.py`
- `tests/graph/test_finalizer_modes.py`
- `tests/api/test_chat_modes.py`
- `tests/e2e/test_pa_conversation_acceptance.py`

## Recent Runtime Loop Fix
- Removed forced tool choice in `app/llm/client.py` (`bind_tools(tools)` instead of `tool_choice="any"`), so the model is not forced to keep emitting tool calls.
- Added `route_after_tool_result` in `app/graph/builder.py` to route successful tool outputs directly to `finalizer` (or `hitl` on conflict).
- Added regression tests:
- `tests/graph/test_builder_routes.py`
- Updated `tests/llm/test_client_tool_binding.py`

## Recent Query Reply UX Fix
- Upgraded `app/graph/nodes/finalizer_node.py` calendar-query path to prefer conversational one-sentence summaries and use deterministic fallback only when needed.
- Added readable time/day normalization for query replies via `app/services/time_formatting.py` (no raw ISO in user-facing fallback text).
- Added an ISO-leak guard in finalizer: if LLM query summary contains ISO-like timestamps, fallback formatting is used automatically.
- Updated calendar query prompt guidance in `app/llm/prompts.py` to enforce natural language style and readable times.
- Removed frontend `"Calendar update: "` prefix in `frontend/src/App.jsx` so backend assistant text is shown directly.
- Added regression coverage in `tests/graph/test_finalizer_modes.py` for natural `"tomorrow"` phrasing and ISO-leak prevention.

## Recent HITL Finalization Unification
- `/hitl/respond` no longer hardcodes user-facing summaries; it resolves action into `execution_result` and runs `finalizer_node` before returning `ChatResponse`.
- Added `app/services/hitl/resolve_action.py` as the deterministic HITL resolver layer.
- `finalizer_node` now emits a normalized `final_response` payload (`status`, `summary`, `response_mode`, event metadata, HITL metadata), and `/chat` + `/hitl/respond` consume that contract.
- Added tests:
- `tests/graph/test_finalizer_hitl_contract.py`
- Updated `tests/api/test_hitl_rebook.py`

## Recent Booking Validation + Error Grounding Fix
- `app/tools/calendar_proxy.py` `book_event` now:
- strictly normalizes/validates datetime input before MCP calls,
- validates attendee emails early (`invalid_attendees` error path),
- removes redundant `mcp_google_calendar_add_attendee` sidecar call after create,
- returns richer structured error payload (`error_code`, `http_status`, `title`, `start_iso`, `attendee_count`).
- `app/graph/nodes/finalizer_node.py` now uses a deterministic error-summary path for `status=error` to avoid hallucinated success confirmations.
- Added regression tests:
- `tests/tools/test_calendar_proxy_coercion.py` (invalid datetime, invalid attendee, no sidecar add_attendee),
- `tests/graph/test_finalizer_modes.py` (grounded error summary for action failures).

## Recent Location + Attendee Parsing Fix
- `app/tools/calendar_proxy.py` `book_event` now accepts optional `location`.
- Attendee handling was refined:
- valid emails are passed as `attendees`,
- malformed email-like tokens (contain `@` but invalid) still hard-fail with `invalid_attendees`,
- non-email tokens no longer fail booking and can be inferred as location when `location` is missing.
- `app/services/calendar/mcp_client.py` create-event fallback now forwards `location` to calendar-mcp REST create endpoint.
- `app/llm/prompts.py` now explicitly instructs:
- use `location` for venue/place text,
- use `attendees` only for email addresses.
- `app/llm/schemas.py` `BookingIntent` now includes optional `location`.
- Added regression tests:
- `tests/tools/test_calendar_proxy_coercion.py` (non-email tokens infer location; explicit location passthrough),
- `tests/services/test_mcp_client_compat.py` (create fallback includes location).

## Recent Duration Query + Tool-Use Failure Resilience
- Added `get_event_duration` proxy tool in `app/tools/calendar_proxy.py`:
- searches events in a date range via MCP `find_events`,
- matches by title hint,
- computes duration from start/end, and returns a query-ready summary payload.
- `app/graph/nodes/agent_node.py` now uses mode-specific tool sets:
- `calendar_query` binds query-focused tools (`find_events`, `check_availability`, `get_event_duration`),
- `calendar_action` binds action-capable tools.
- On `tool_use_failed`, agent fallback now:
- preserves the original route mode (no forced `calendar_action`),
- emits mode-specific clarification text,
- logs Groq `failed_generation` for faster debugging.
- `app/graph/nodes/tool_result_node.py` now normalizes `get_event_duration` output into `execution_result` for finalizer consumption.
- `app/llm/prompts.py` now explicitly instructs duration follow-up questions to use `get_event_duration`.
- Added regression tests:
- `tests/tools/test_event_duration_tool.py`,
- updated `tests/graph/test_agent_tool_use_failure.py`,
- updated `tests/graph/test_tool_result_node.py`.

## Recent Duration-Only Update Support
- Added new action proxy tool `update_event_duration` in `app/tools/calendar_proxy.py`:
- updates only duration while keeping the same `start_iso`,
- requires `event_id` and `current_start_iso`,
- returns normalized `updated` payload with `event_id`, `start_iso`, and `duration_minutes`.
- `book_event` now returns top-level `start_iso` in success payload so follow-up duration edits have stable context.
- `app/graph/nodes/agent_node.py` now includes `update_event_duration` in action tool set.
- `app/graph/nodes/tool_result_node.py` now treats `update_event_duration` as an action tool result.
- `app/llm/prompts.py` now instructs the model to use `update_event_duration` for follow-ups like "make it 45 minutes", using history markers.
- `app/main.py` now appends richer history markers when available:
- `[event_id=... start_iso=...]` (instead of only event ID), preserving context for duration-only updates.
- `app/graph/nodes/finalizer_node.py` now includes `latest_start_iso` in normalized final response metadata.
- Added regression tests:
- `tests/tools/test_update_event_duration_tool.py`,
- updated `tests/api/test_chat_endpoint.py` (history marker includes `start_iso`),
- updated `tests/e2e/test_pa_conversation_acceptance.py` (follow-up state contains `start_iso` marker),
- updated `tests/graph/test_tool_result_node.py` and `tests/graph/test_agent_tool_use_failure.py`.

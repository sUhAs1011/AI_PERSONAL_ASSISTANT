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

## Recent Hallucinated Event-ID Guardrails
- `app/graph/nodes/agent_node.py` now sanitizes tool-call arguments before `ToolNode` execution:
- forces authoritative `user_id` and `timezone` from graph state (does not trust LLM for these),
- extracts latest history marker `[event_id=... start_iso=...]`,
- hydrates `update_event_duration` arguments from marker context,
- blocks suspicious title-like `event_id` calls when marker context is missing, returning a targeted clarification.
- Added tool-use failure diagnostics in logs (`failed_generation` capture remains + sanitized-call logs).
- `app/tools/calendar_proxy.py` `update_event_duration` now has retry resolution:
- if first update fails and `event_id` looks title-like, it searches nearby events and retries with resolved real ID.
- if resolution fails, returns `error_code=event_not_found` (instead of opaque generic failure).
- `app/graph/nodes/finalizer_node.py` now maps `event_not_found` / `missing_event_context` to specific user guidance.
- Added regression tests:
- `tests/graph/test_agent_tool_use_failure.py` (sanitization + missing-marker clarification),
- `tests/tools/test_update_event_duration_tool.py` (retry with resolved ID + not-found path),
- `tests/graph/test_finalizer_modes.py` (specific event-not-found summary).

## Recent Location Follow-up Update Fix
- Added new action proxy tool `update_event_location` in `app/tools/calendar_proxy.py`:
  - updates only `location` on an existing event,
  - requires `event_id` + `current_start_iso` context,
  - includes title-hint fallback resolution (same pattern as `update_event_duration`) and structured error payloads.
- `app/graph/nodes/agent_node.py` now includes `update_event_location` in action tools and sanitization:
  - hydrates marker context (`[event_id=... start_iso=...]`) into location-update calls,
  - rewrites mistaken follow-up `book_event` tool calls into `update_event_location` for location-only edits,
  - keeps clarification path when required location/context is missing.
- `app/services/calendar/mcp_client.py` update-event fallback now supports partial patch updates (e.g., `location`) and preserves existing start/duration patch behavior.
- `app/graph/nodes/tool_result_node.py` now normalizes `update_event_location` as a calendar action result.
- `app/llm/prompts.py` now explicitly instructs location follow-up edits to use `update_event_location` and avoid new bookings.
- Added regression tests:
  - `tests/tools/test_update_event_location_tool.py`,
  - `tests/graph/test_agent_tool_use_failure.py` (rewrite guard for location follow-ups),
  - `tests/graph/test_tool_result_node.py` (location-update action normalization),
  - `tests/services/test_mcp_client_compat.py` (location-only update fallback patch).

## Recent Cache-First Query + Location Query Fixes
- Added backend in-memory cache service `app/services/calendar/event_cache.py`:
  - primes and stores normalized events for `today` + `tomorrow` per user/timezone,
  - provides deterministic `canonical_event_id` generation,
  - supports fast query answers (`location`, `duration`, day event list) from cache,
  - supports robust alias-based event-id resolution.
- Added new API contracts and endpoint for cache priming:
  - `app/schemas.py`: `CalendarCachePrimeRequest`, `CalendarCachePrimeResponse`,
  - `app/main.py`: `POST /calendar/cache/prime`.
- Added cache refresh on successful calendar actions (`created`/`updated`/`cancelled`):
  - `app/main.py` now refreshes cache after `/chat` and `/hitl/respond` action completions.
- Added query fast-path in `app/graph/nodes/agent_node.py`:
  - for `calendar_query`, cache is consulted first for today/tomorrow turns,
  - on cache hit, agent returns normalized `execution_result` without tool call.
- Added new query tool `get_event_location` in `app/tools/calendar_proxy.py`:
  - cache-aware first, MCP `find_events` fallback,
  - structured location payload for finalizer consumption.
- Updated tool/result/prompt handling for location queries:
  - `app/graph/nodes/tool_result_node.py` normalizes `get_event_location`,
  - `app/graph/nodes/finalizer_node.py` includes location context and deterministic location fallback summaries,
  - `app/llm/prompts.py` now explicitly steers location questions to `get_event_location`.
- Fixed sanitizer regression in `app/graph/nodes/agent_node.py`:
  - `update_event_location` no longer blocks title-like `event_id` when required context (`current_start_iso`, `location`) exists.
- Frontend cache priming integration:
  - `frontend/src/lib/api.js`: `primeCalendarCache` API wrapper,
  - `frontend/src/App.jsx`: primes cache on login/session restore (non-blocking).
- Added regression tests:
  - `tests/services/test_event_cache.py`,
  - `tests/api/test_event_cache_prime.py`,
  - `tests/tools/test_event_location_tool.py`,
  - updated `tests/graph/test_agent_tool_use_failure.py`,
  - updated `tests/graph/test_tool_result_node.py`,
  - updated `tests/graph/test_finalizer_modes.py`,
  - updated `tests/api/test_hitl_rebook.py`.

## Recent Deterministic Booking Conflict Guard
- `app/tools/calendar_proxy.py` `book_event` now performs deterministic overlap checks before create:
  - resolves requested start/end window,
  - queries existing events in requested slot,
  - blocks creation on overlap with `status=conflict` and `error_code=time_conflict`.
- On conflict, `book_event` now returns structured conflict metadata:
  - `conflicting_event` (id/title/start/end),
  - `alternatives` generated from free/busy windows for the day,
  - grounded summary text.
- Existing graph conflict routing (`status=conflict` -> `hitl`) now applies to direct `book_event` conflicts as well.
- Prompt guidance in `app/llm/prompts.py` now reinforces conflict-aware behavior for specific-time booking requests.
- Added regression tests:
  - `tests/tools/test_calendar_proxy_coercion.py` (conflict path blocks create + returns alternatives),
  - `tests/graph/test_tool_result_node.py` (book_event conflict alternatives preserved for HITL).

## Recent Cancel Event Reliability Fix
- `app/tools/calendar_proxy.py` `cancel_event` now resolves concrete event ids before delete using:
  - cached event metadata id,
  - `event_cache.resolve_event_id` alias lookup,
  - fallback title-hint search (`find_events` + best-match) when initial delete fails with hint-like ids.
- `cancel_event` retry path now preserves grounded metadata (`title`, `start_iso`, `location`) from resolved event when cancellation succeeds.
- `_looks_like_title_hint` now treats underscore/time-suffixed references (e.g. `vet_appointment_6pm`) as hint-like for safe retry resolution.
- Added regression test:
  - `tests/tools/test_cancel_event_tool.py::test_cancel_event_retries_with_resolved_id_after_hint_delete_failure`.

## Recent Reschedule Event Reliability Fix
- `app/tools/calendar_proxy.py` `reschedule_event` now resolves concrete event ids before update using:
  - cached event metadata id,
  - `event_cache.resolve_event_id` alias lookup,
  - fallback title-hint search (`find_events` + best-match) when initial update fails with hint-like ids.
- `reschedule_event` now returns normalized structured payloads on success (`event`, `event_id`, `start_iso`, `duration_minutes`) for finalizer consistency.
- When hint resolution fails, `reschedule_event` now returns structured `event_not_found` errors instead of generic raw exceptions.
- Added regression tests:
  - `tests/tools/test_reschedule_event_tool.py`.

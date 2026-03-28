# HITL Finalizer Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `finalizer_node` the single user-message generator for graph-driven chat/HITL responses, with consistent `ChatResponse` output across `/chat` and `/hitl/respond`.

**Architecture:** Keep the current LangGraph node set and simplify terminal behavior by routing all response-producing paths to `finalizer`. Keep `hitl_node` state/persistence-focused, and keep API routes consuming a single normalized final-response contract.

**Tech Stack:** FastAPI, LangGraph, LangChain, Pydantic, SQLite, pytest

---

### Task 1: Route HITL through Finalizer in LangGraph

**Files:**
- Modify: `app/graph/builder.py`
- Test: `tests/graph/test_builder_routes.py`

- [ ] Update graph edge so `hitl -> finalizer` instead of `hitl -> END`.
- [ ] Keep `finalizer -> END` as the only terminal response edge.
- [ ] Run/adjust routing tests to validate conflict/HITL paths now terminate at finalizer.

### Task 2: Keep HITL Node as State + Persistence Layer

**Files:**
- Modify: `app/graph/nodes/hitl_node.py`
- Modify (if needed): `app/services/hitl/pending_repo.py`
- Test: `tests/graph/test_hitl_node.py`

- [ ] Ensure `hitl_node` only persists pending-action state and returns machine-state fields (`needs_hitl`, `hitl_action_id`, `alternatives`, status).
- [ ] Replace hardcoded pending payload defaults with real booking context where available, to support accurate HITL rebook execution.
- [ ] Verify/update HITL node tests for payload persistence and returned state.

### Task 3: Enforce Finalizer as Single Message Generator

**Files:**
- Verify/Modify: `app/graph/nodes/finalizer_node.py`
- Verify/Modify: `app/main.py` (`_normalized_final_response`, `/chat` response shaping)
- Test: `tests/graph/test_finalizer_hitl_contract.py`
- Test: `tests/graph/test_finalizer_modes.py`
- Test: `tests/api/test_chat_modes.py`

- [ ] Ensure HITL-init path (status `needs_hitl`) gets its user-facing `summary` from `finalizer_node` output.
- [ ] Keep `final_response` contract stable (`status`, `summary`, `response_mode`, `hitl_action_id`, `alternatives`, event metadata).
- [ ] Ensure `/chat` always prefers `final_response` values when present.

### Task 4: Preserve `/hitl/respond` Contract Parity

**Files:**
- Verify/Modify: `app/main.py` (`/hitl/respond`)
- Verify/Modify: `app/services/hitl/resolve_action.py`
- Test: `tests/api/test_hitl_rebook.py`

- [ ] Keep `/hitl/respond` flow as: resolve pending action -> finalizer -> normalized `ChatResponse`.
- [ ] Ensure response field parity with `/chat` (status/summary/response_mode/hitl metadata/event metadata).

### Task 5: Regression Verification (Targeted then Full)

**Files/Commands:**
- Run targeted tests:
  - `tests/graph/test_builder_routes.py`
  - `tests/graph/test_hitl_node.py`
  - `tests/graph/test_finalizer_hitl_contract.py`
  - `tests/graph/test_finalizer_modes.py`
  - `tests/api/test_chat_modes.py`
  - `tests/api/test_hitl_rebook.py`
- Run full backend suite: `python -m pytest -q`

- [ ] Confirm all targeted tests pass.
- [ ] Confirm no `ChatResponse` shape regressions in full suite.
- [ ] Confirm no path returns fallback-only generic summary when finalizer data is available.

### Optional Task 6 (Time Permitting): Pending-Action Cleanup

**Files:**
- Modify: `app/services/hitl/pending_repo.py`
- Modify: `app/main.py` (`/hitl/respond` cleanup call)
- Test: `tests/api/test_hitl_rebook.py` or new focused API test

- [ ] Add cleanup/resolution handling for consumed pending actions.
- [ ] Keep behavior backward compatible for existing action IDs during v1 demo.

---

## Done Criteria

- All graph response-producing paths for `/chat` end in `finalizer`.
- `finalizer_node` is the single source of user-facing summary generation for graph-driven responses.
- `/chat` and `/hitl/respond` return contract-consistent `ChatResponse` payloads.
- Existing behavior for general chat, calendar query, calendar action, and HITL decision flows remains functional.

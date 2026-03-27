# Deciduus Tool Contracts

- `mcp_google_calendar_find_events` -> normalized to `{"events": [{"id": "evt_1", "start_iso": "2026-03-27T15:00:00+05:30"}]}`.
- `mcp_google_calendar_create_event` -> normalized to `{"event": {"id", "meet_link", "invite_status"}}`.
- `mcp_google_calendar_update_event` -> normalized to `{"status": "updated", "event": {"id": "evt_1"}}`.
- `mcp_google_calendar_delete_event` -> normalized to `{"status": "cancelled", "event_id": "evt_1"}`.
- `mcp_google_calendar_query_free_busy` -> normalized free/busy status.
- `mcp_google_calendar_schedule_mutual` -> normalized alternatives list.


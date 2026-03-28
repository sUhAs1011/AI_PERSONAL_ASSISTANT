from datetime import datetime, timedelta
import logging

import requests

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, base_url: str, timeout_sec: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        logger.info(
            "mcp.call_tool.start tool=%s base_url=%s arg_keys=%s",
            tool_name,
            self.base_url,
            list(arguments.keys()),
        )
        try:
            response = requests.post(
                f"{self.base_url}/tools/call",
                json={"name": tool_name, "arguments": arguments},
                timeout=self.timeout_sec,
            )
            if response.status_code != 404:
                response.raise_for_status()
                payload = response.json()
                logger.info("mcp.call_tool.ok tool=%s status_code=%s", tool_name, response.status_code)
                return payload
            logger.warning("mcp.call_tool.404_fallback tool=%s base_url=%s", tool_name, self.base_url)
            return self._call_rest_fallback(tool_name=tool_name, arguments=arguments)
        except requests.RequestException:
            logger.exception("mcp.call_tool.error tool=%s base_url=%s", tool_name, self.base_url)
            raise

    def _call_rest_fallback(self, tool_name: str, arguments: dict) -> dict:
        logger.info("mcp.rest_fallback.start tool=%s", tool_name)
        calendar_id = arguments.get("calendar_id", "primary")
        if tool_name == "mcp_google_calendar_find_events":
            resp = requests.get(
                f"{self.base_url}/calendars/{calendar_id}/events",
                params={
                    "time_min": arguments.get("start_iso"),
                    "time_max": arguments.get("end_iso"),
                },
                timeout=self.timeout_sec,
            )
            resp.raise_for_status()
            payload = resp.json()
            logger.info(
                "mcp.rest_fallback.find_events.ok status_code=%s items=%s",
                resp.status_code,
                len(payload.get("items", [])),
            )
            return {"events": payload.get("items", [])}

        if tool_name == "mcp_google_calendar_create_event":
            start_iso = arguments["start_iso"]
            duration = int(arguments.get("duration_minutes", 30))
            end_iso = self._compute_end_iso(start_iso=start_iso, duration_minutes=duration)
            body = {
                "summary": arguments.get("title", "meeting"),
                "start": {"dateTime": start_iso},
                "end": {"dateTime": end_iso},
                "attendees": arguments.get("attendees", []),
            }
            location = arguments.get("location")
            if isinstance(location, str) and location.strip():
                body["location"] = location.strip()
            resp = requests.post(
                f"{self.base_url}/calendars/{calendar_id}/events",
                params={"send_notifications": bool(arguments.get("send_invites", True))},
                json=body,
                timeout=self.timeout_sec,
            )
            resp.raise_for_status()
            logger.info("mcp.rest_fallback.create_event.ok status_code=%s", resp.status_code)
            return resp.json()

        if tool_name == "mcp_google_calendar_add_attendee":
            resp = requests.post(
                f"{self.base_url}/calendars/{calendar_id}/events/{arguments['event_id']}/attendees",
                params={"send_notifications": bool(arguments.get("send_updates", True))},
                json={"attendee_emails": arguments.get("attendees", [])},
                timeout=self.timeout_sec,
            )
            resp.raise_for_status()
            logger.info("mcp.rest_fallback.add_attendee.ok status_code=%s", resp.status_code)
            return resp.json()

        if tool_name == "mcp_google_calendar_delete_event":
            resp = requests.delete(
                f"{self.base_url}/calendars/{calendar_id}/events/{arguments['event_id']}",
                timeout=self.timeout_sec,
            )
            resp.raise_for_status()
            logger.info("mcp.rest_fallback.delete_event.ok status_code=%s", resp.status_code)
            return {"status": "cancelled", "event_id": arguments["event_id"]}

        if tool_name == "mcp_google_calendar_update_event":
            patch_body: dict = {}
            if "start_iso" in arguments:
                new_start_iso = arguments["start_iso"]
                duration = int(arguments.get("duration_minutes", 30))
                end_iso = self._compute_end_iso(start_iso=new_start_iso, duration_minutes=duration)
                patch_body["start"] = {"dateTime": new_start_iso}
                patch_body["end"] = {"dateTime": end_iso}

            location = arguments.get("location")
            if isinstance(location, str) and location.strip():
                patch_body["location"] = location.strip()

            summary = arguments.get("title")
            if isinstance(summary, str) and summary.strip():
                patch_body["summary"] = summary.strip()

            description = arguments.get("description")
            if isinstance(description, str) and description.strip():
                patch_body["description"] = description.strip()

            if not patch_body:
                raise ValueError("mcp_google_calendar_update_event fallback requires at least one update field")

            resp = requests.patch(
                f"{self.base_url}/calendars/{calendar_id}/events/{arguments['event_id']}",
                json=patch_body,
                timeout=self.timeout_sec,
            )
            resp.raise_for_status()
            logger.info("mcp.rest_fallback.update_event.ok status_code=%s", resp.status_code)
            return resp.json()

        if tool_name == "mcp_google_calendar_query_free_busy":
            payload = self._call_free_busy(arguments=arguments)
            logger.info("mcp.rest_fallback.query_free_busy.ok")
            return {
                "free_windows": self._compute_free_windows(
                    start_iso=arguments["start_iso"],
                    end_iso=arguments["end_iso"],
                    free_busy_payload=payload,
                )
            }

        if tool_name == "mcp_google_calendar_schedule_mutual":
            payload = self._call_free_busy(arguments=arguments)
            windows = self._compute_free_windows(
                start_iso=arguments["start_iso"],
                end_iso=arguments["end_iso"],
                free_busy_payload=payload,
            )
            alternatives = self._windows_to_alternatives(
                windows=windows,
                duration_minutes=int(arguments.get("duration_minutes", 30)),
            )
            logger.info("mcp.rest_fallback.schedule_mutual.ok alternatives=%s", len(alternatives))
            return {"alternatives": alternatives}

        raise ValueError(f"Unsupported tool name for fallback mode: {tool_name}")

    def _call_free_busy(self, arguments: dict) -> dict:
        attendee_ids = list(arguments.get("attendees", []))
        if "primary" not in attendee_ids:
            attendee_ids.insert(0, "primary")
        resp = requests.post(
            f"{self.base_url}/freeBusy",
            json={
                "time_min": arguments["start_iso"],
                "time_max": arguments["end_iso"],
                "items": [{"id": cal_id} for cal_id in attendee_ids],
            },
            timeout=self.timeout_sec,
        )
        resp.raise_for_status()
        logger.info("mcp.free_busy.ok status_code=%s", resp.status_code)
        return resp.json()

    def _compute_free_windows(self, start_iso: str, end_iso: str, free_busy_payload: dict) -> list[dict]:
        window_start = self._parse_iso(start_iso)
        window_end = self._parse_iso(end_iso)
        busy_intervals: list[tuple[datetime, datetime]] = []
        for cal_data in free_busy_payload.get("calendars", {}).values():
            for entry in cal_data.get("busy", []):
                start = entry.get("start")
                end = entry.get("end")
                if not start or not end:
                    continue
                busy_intervals.append((self._parse_iso(start), self._parse_iso(end)))

        busy_intervals.sort(key=lambda it: it[0])
        merged: list[tuple[datetime, datetime]] = []
        for current in busy_intervals:
            if not merged or current[0] > merged[-1][1]:
                merged.append(current)
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], current[1]))

        free_windows: list[dict] = []
        cursor = window_start
        for start, end in merged:
            if start > cursor:
                free_windows.append(
                    {"start_iso": cursor.isoformat(), "end_iso": min(start, window_end).isoformat()}
                )
            cursor = max(cursor, end)
            if cursor >= window_end:
                break
        if cursor < window_end:
            free_windows.append({"start_iso": cursor.isoformat(), "end_iso": window_end.isoformat()})
        return free_windows

    def _windows_to_alternatives(self, windows: list[dict], duration_minutes: int) -> list[dict]:
        alternatives: list[dict] = []
        duration = timedelta(minutes=duration_minutes)
        for window in windows:
            start = self._parse_iso(window["start_iso"])
            end = self._parse_iso(window["end_iso"])
            if start + duration <= end:
                slot_end = start + duration
                alternatives.append(
                    {
                        "start_iso": start.isoformat(),
                        "end_iso": slot_end.isoformat(),
                        "label": f"{start.strftime('%a %I:%M %p')} - {slot_end.strftime('%I:%M %p')}",
                    }
                )
            if len(alternatives) >= 5:
                break
        return alternatives

    def _compute_end_iso(self, start_iso: str, duration_minutes: int) -> str:
        start = self._parse_iso(start_iso)
        return (start + timedelta(minutes=duration_minutes)).isoformat()

    def _parse_iso(self, value: str) -> datetime:
        iso = value.strip()
        if iso.endswith("Z"):
            iso = iso[:-1] + "+00:00"
        return datetime.fromisoformat(iso)

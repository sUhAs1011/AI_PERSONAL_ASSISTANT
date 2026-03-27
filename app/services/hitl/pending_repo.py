import json
import sqlite3
import uuid


class PendingActionRepo:
    def __init__(self, db_path: str = "app.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_actions (
                    action_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    payload_json TEXT,
                    alternatives_json TEXT,
                    timezone TEXT
                )
                """
            )

    def save(
        self,
        user_id: str,
        payload: dict,
        alternatives: list[dict] | None = None,
        timezone: str = "Asia/Kolkata",
    ) -> str:
        action_id = str(uuid.uuid4())
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO pending_actions(action_id, user_id, payload_json, alternatives_json, timezone) VALUES (?, ?, ?, ?, ?)",
            (action_id, user_id, json.dumps(payload), json.dumps(alternatives or []), timezone),
        )
        conn.commit()
        conn.close()
        return action_id

    def get(self, action_id: str) -> dict | None:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT user_id, payload_json, alternatives_json, timezone FROM pending_actions WHERE action_id = ?",
            (action_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "user_id": row[0],
            "payload": json.loads(row[1]),
            "alternatives": json.loads(row[2] or "[]"),
            "timezone": row[3],
        }


pending_repo = PendingActionRepo()


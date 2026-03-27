import json
import sqlite3


class PreferencesRepo:
    def __init__(self, db_path: str = "app.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    prefs_json TEXT
                )
                """
            )

    def get_preferences(self, user_id: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT prefs_json FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        conn.close()
        if not row:
            return {"no_meetings_before_hour": 9}
        return json.loads(row[0])

    def upsert_preferences(self, user_id: str, prefs: dict) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO user_preferences(user_id, prefs_json)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET prefs_json = excluded.prefs_json
            """,
            (user_id, json.dumps(prefs)),
        )
        conn.commit()
        conn.close()


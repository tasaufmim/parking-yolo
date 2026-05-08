import sqlite3
import os
from datetime import datetime
from typing import Optional

MAX_CAMERAS = 6
DB_PATH = "cameras.db"


def _get_connection():
    return sqlite3.connect(DB_PATH)


def _init_db():
    if not os.path.exists(DB_PATH):
        open(DB_PATH, "w").close()
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cameras (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            rtsp_url TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


_init_db()


def _generate_id(conn) -> str:
    cursor = conn.execute("SELECT id FROM cameras ORDER BY id")
    rows = cursor.fetchall()
    existing = set(r[0] for r in rows)
    for i in range(1, MAX_CAMERAS + 1):
        cam_id = f"CAM{i:03d}"
        if cam_id not in existing:
            return cam_id
    return None


def add_camera(name: str, rtsp_url: str) -> dict:
    conn = _get_connection()
    count = conn.execute("SELECT COUNT(*) FROM cameras").fetchone()[0]
    if count >= MAX_CAMERAS:
        conn.close()
        raise ValueError(f"Maximum of {MAX_CAMERAS} cameras reached")

    cam_id = _generate_id(conn)
    if not cam_id:
        conn.close()
        raise ValueError("No available camera slot")

    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO cameras (id, name, rtsp_url, enabled, created_at) VALUES (?, ?, ?, 1, ?)",
        (cam_id, name, rtsp_url, now),
    )
    conn.commit()
    conn.close()
    return get_camera(cam_id)


def get_cameras() -> list[dict]:
    conn = _get_connection()
    cursor = conn.execute(
        "SELECT id, name, rtsp_url, enabled, created_at FROM cameras ORDER BY id"
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "rtsp_url": r[2],
            "enabled": bool(r[3]),
            "created_at": r[4],
        }
        for r in rows
    ]


def get_camera(cam_id: str) -> Optional[dict]:
    conn = _get_connection()
    cursor = conn.execute(
        "SELECT id, name, rtsp_url, enabled, created_at FROM cameras WHERE id = ?",
        (cam_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "rtsp_url": row[2],
        "enabled": bool(row[3]),
        "created_at": row[4],
    }


def update_camera(cam_id: str, name: str, rtsp_url: str) -> Optional[dict]:
    conn = _get_connection()
    conn.execute(
        "UPDATE cameras SET name = ?, rtsp_url = ? WHERE id = ?",
        (name, rtsp_url, cam_id),
    )
    if conn.total_changes == 0:
        conn.close()
        return None
    conn.commit()
    conn.close()
    return get_camera(cam_id)


def delete_camera(cam_id: str) -> bool:
    conn = _get_connection()
    conn.execute("DELETE FROM cameras WHERE id = ?", (cam_id,))
    deleted = conn.total_changes > 0
    conn.commit()
    conn.close()
    return deleted


def toggle_enabled(cam_id: str, enabled: bool) -> Optional[dict]:
    conn = _get_connection()
    conn.execute("UPDATE cameras SET enabled = ? WHERE id = ?", (1 if enabled else 0, cam_id))
    if conn.total_changes == 0:
        conn.close()
        return None
    conn.commit()
    conn.close()
    return get_camera(cam_id)


def get_enabled_cameras() -> list[dict]:
    conn = _get_connection()
    cursor = conn.execute(
        "SELECT id, name, rtsp_url, enabled, created_at FROM cameras WHERE enabled = 1 ORDER BY id"
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "rtsp_url": r[2],
            "enabled": bool(r[3]),
            "created_at": r[4],
        }
        for r in rows
    ]


def is_full() -> bool:
    conn = _get_connection()
    count = conn.execute("SELECT COUNT(*) FROM cameras").fetchone()[0]
    conn.close()
    return count >= MAX_CAMERAS


def count() -> int:
    conn = _get_connection()
    count = conn.execute("SELECT COUNT(*) FROM cameras").fetchone()[0]
    conn.close()
    return count
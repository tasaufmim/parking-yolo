import sqlite3
import os
import cv2
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import json
import numpy as np


VEHICLE_TYPE_MAP = {
    ("white", "black"): "Private",
    ("yellow", "black"): "Commercial",
    ("green", "white"): "Private Electric",
    ("green", "yellow"): "Commercial Electric",
    ("black", "yellow"): "Self-drive Rental",
    ("red", "white"): "Temporary/Dealer",
    ("blue", "white"): "Diplomatic",
}

SNAPSHOT_DIR = "snapshots"
os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def derive_vehicle_type(plate_color: str, text_color: str) -> str:
    if not plate_color or not text_color:
        return "Unknown"
    key = (plate_color.lower(), text_color.lower())
    return VEHICLE_TYPE_MAP.get(key, "Unknown")


def calculate_duration(time_parked: str, time_left: str) -> Optional[int]:
    if not time_parked or not time_left:
        return None
    try:
        dt1 = datetime.fromisoformat(time_parked)
        dt2 = datetime.fromisoformat(time_left)
        return int((dt2 - dt1).total_seconds() / 60)
    except:
        return None


class HistoryManager:
    def __init__(self, db_path: str = "parking_history.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='parking_history'"
        )
        if not cursor.fetchone():
            conn.execute("""
                CREATE TABLE parking_history (
                    sl INTEGER PRIMARY KEY AUTOINCREMENT,
                    slot_id TEXT NOT NULL,
                    car_id TEXT NOT NULL,
                    plate_number TEXT,
                    plate_color TEXT,
                    text_color TEXT,
                    vehicle_type TEXT,
                    ocr_source TEXT,
                    car_photo_path TEXT,
                    time_parked TEXT NOT NULL,
                    time_left TEXT,
                    duration_minutes INTEGER,
                    status TEXT DEFAULT 'active',
                    retry_status TEXT DEFAULT 'none',
                    retry_count INTEGER DEFAULT 0,
                    retry_last_attempt TEXT,
                    retry_locked_until TEXT,
                    UNIQUE(slot_id, car_id, time_parked)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON parking_history(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_retry ON parking_history(retry_status)")
            conn.commit()
        
        conn.close()
    
    def _get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def start_parking(self, slot_id: str, car_id: str, 
                      frame_path: str = None, ocr_result: dict = None) -> dict:
        conn = self._get_connection()
        now = datetime.now().isoformat()
        
        plate_number = None
        plate_color = None
        text_color = None
        ocr_source = None
        vehicle_type = "Unknown"
        
        if ocr_result:
            plate_number = ocr_result.get("plate_text")
            plate_color = ocr_result.get("plate_color")
            text_color = ocr_result.get("text_color")
            ocr_source = ocr_result.get("source")
            if plate_color and text_color:
                vehicle_type = derive_vehicle_type(plate_color, text_color)
        
        values = (slot_id, car_id, now, vehicle_type, frame_path, 
                plate_number, plate_color, text_color, ocr_source)
        
        conn.execute("""
            INSERT INTO parking_history 
            (slot_id, car_id, time_parked, vehicle_type, car_photo_path,
             plate_number, plate_color, text_color, ocr_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, values)
        conn.commit()
        
        cursor = conn.execute("SELECT last_insert_rowid()")
        sl = cursor.fetchone()[0]
        conn.close()
        
        return {
            "sl": sl,
            "slot_id": slot_id,
            "car_id": car_id,
            "time_parked": now,
            "status": "active"
        }
    
    def end_parking(self, slot_id: str, car_id: str) -> dict:
        conn = self._get_connection()
        now = datetime.now().isoformat()
        
        cursor = conn.execute("""
            SELECT sl, time_parked FROM parking_history
            WHERE slot_id = ? AND car_id = ? AND status = 'active'
            ORDER BY time_parked DESC LIMIT 1
        """, (slot_id, car_id))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        sl, time_parked = row
        duration = calculate_duration(time_parked, now)
        
        conn.execute("""
            UPDATE parking_history SET
            time_left = ?,
            duration_minutes = ?,
            status = 'completed'
            WHERE sl = ?
        """, (now, duration, sl))
        conn.commit()
        conn.close()
        
        return {
            "sl": sl,
            "slot_id": slot_id,
            "car_id": car_id,
            "time_left": now,
            "duration_minutes": duration,
            "status": "completed"
        }
    
    def get_active_sessions(self) -> list:
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT sl, slot_id, car_id, time_parked 
            FROM parking_history WHERE status = 'active'
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {"sl": r[0], "slot_id": r[1], "car_id": r[2], "time_parked": r[3]}
            for r in rows
        ]
    
    def get_history(self, page: int = 1, per_page: int = 100,
                   status: str = None) -> dict:
        conn = self._get_connection()
        
        where = "WHERE 1=1"
        params = []
        if status:
            where += " AND status = ?"
            params.append(status)
        
        count_sql = f"SELECT COUNT(*) FROM parking_history {where}"
        cursor = conn.execute(count_sql, params)
        total = cursor.fetchone()[0]
        
        offset = (page - 1) * per_page
        sql = f"""
            SELECT sl, slot_id, car_id, plate_number, plate_color, 
                   text_color, vehicle_type, ocr_source, car_photo_path,
                   time_parked, time_left, duration_minutes, status,
                   retry_status, retry_count
            FROM parking_history {where}
            ORDER BY sl DESC LIMIT ? OFFSET ?
        """
        params.extend([per_page, offset])
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        entries = []
        for r in rows:
            entries.append({
                "sl": r[0],
                "slot_id": r[1],
                "car_id": r[2],
                "plate_number": r[3],
                "plate_color": r[4],
                "text_color": r[5],
                "vehicle_type": r[6],
                "ocr_source": r[7],
                "car_photo_path": r[8],
                "time_parked": r[9],
                "time_left": r[10],
                "duration_minutes": r[11],
                "status": r[12],
                "retry_status": r[13],
                "retry_count": r[14]
            })
        
        total_pages = (total + per_page - 1) // per_page
        
        return {
            "entries": entries,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }
    
    def get_by_sl(self, sl: int) -> dict:
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT sl, slot_id, car_id, plate_number, plate_color,
                   text_color, vehicle_type, ocr_source, car_photo_path,
                   time_parked, time_left, duration_minutes, status,
                   retry_status, retry_count, retry_last_attempt, retry_locked_until
            FROM parking_history WHERE sl = ?
        """, (sl,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "sl": row[0],
            "slot_id": row[1],
            "car_id": row[2],
            "plate_number": row[3],
            "plate_color": row[4],
            "text_color": row[5],
            "vehicle_type": row[6],
            "ocr_source": row[7],
            "car_photo_path": row[8],
            "time_parked": row[9],
            "time_left": row[10],
            "duration_minutes": row[11],
            "status": row[12],
            "retry_status": row[13],
            "retry_count": row[14],
            "retry_last_attempt": row[15],
            "retry_locked_until": row[16]
        }
    
    def get_by_car_id_slot(self, car_id: str, slot_id: str) -> dict:
        """Check if active history entry exists for car_id and slot_id."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT sl FROM parking_history 
            WHERE car_id = ? AND slot_id = ? AND status = 'active'
            LIMIT 1
        """, (car_id, slot_id))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self.get_by_sl(row[0])
        return None
        
        if not row:
            return None
        
        return {
            "sl": row[0],
            "slot_id": row[1],
            "car_id": row[2],
            "plate_number": row[3],
            "plate_color": row[4],
            "text_color": row[5],
            "vehicle_type": row[6],
            "ocr_source": row[7],
            "car_photo_path": row[8],
            "time_parked": row[9],
            "time_left": row[10],
            "duration_minutes": row[11],
            "status": row[12],
            "retry_status": row[13],
            "retry_count": row[14],
            "retry_last_attempt": row[15],
            "retry_locked_until": row[16]
        }
    
    def update_ocr_result(self, sl: int, ocr_result: dict) -> dict:
        conn = self._get_connection()
        
        plate_number = ocr_result.get("plate_text")
        plate_color = ocr_result.get("plate_color")
        text_color = ocr_result.get("text_color")
        ocr_source = ocr_result.get("source")
        
        if plate_color and text_color:
            vehicle_type = derive_vehicle_type(plate_color, text_color)
        else:
            vehicle_type = None
        
        conn.execute("""
            UPDATE parking_history SET
            plate_number = COALESCE(?, plate_number),
            plate_color = COALESCE(?, plate_color),
            text_color = COALESCE(?, text_color),
            vehicle_type = COALESCE(?, vehicle_type),
            ocr_source = ?
            WHERE sl = ?
        """, (plate_number, plate_color, text_color, vehicle_type,
              ocr_source, sl))
        conn.commit()
        conn.close()
        
        return self.get_by_sl(sl)
    
    def can_retry(self, sl: int) -> bool:
        entry = self.get_by_sl(sl)
        if not entry:
            return False
        
        # Can't retry while still parking
        if entry.get("status") == "active":
            return False
        
        if not entry.get("car_photo_path"):
            return False
        
        now = datetime.now()
        locked_until = entry.get("retry_locked_until")
        if locked_until:
            try:
                lock_time = datetime.fromisoformat(locked_until)
                if now < lock_time:
                    return False
            except:
                pass
        
        retry_status = entry.get("retry_status")
        
        if retry_status == "pending":
            return False
        
        if entry.get("plate_color") in [None, "N/A", ""] or \
           entry.get("plate_number") in [None, "N/A", ""] or \
           entry.get("text_color") in [None, "N/A", ""]:
            return True
        
        return False
    
    def update_retry_status(self, sl: int, status: str, 
                          increment_count: bool = False) -> dict:
        conn = self._get_connection()
        
        if increment_count:
            now = datetime.now().isoformat()
            if status == "failed":
                retry_count = conn.execute(
                    "SELECT retry_count FROM parking_history WHERE sl = ?", (sl,)
                ).fetchone()[0] or 0
                
                new_count = retry_count + 1
                locked_until = None
                
                if new_count >= 3:
                    lock_time = datetime.now() + timedelta(hours=24)
                    locked_until = lock_time.isoformat()
                
                conn.execute("""
                    UPDATE parking_history SET 
                    retry_status = ?, retry_count = ?, 
                    retry_last_attempt = ?, retry_locked_until = ?
                    WHERE sl = ?
                """, (status, new_count, now, locked_until, sl))
            else:
                conn.execute("""
                    UPDATE parking_history SET 
                    retry_status = ?, retry_count = retry_count + 1,
                    retry_last_attempt = ?, retry_locked_until = NULL
                    WHERE sl = ?
                """, (status, now, sl))
        else:
            conn.execute("""
                UPDATE parking_history SET retry_status = ? WHERE sl = ?
            """, (status, sl))
        
        conn.commit()
        conn.close()
        
        return self.get_by_sl(sl)
    
    def get_car_photo(self, sl: int) -> Optional[np.ndarray]:
        entry = self.get_by_sl(sl)
        if not entry or not entry.get("car_photo_path"):
            return None
        
        path = entry["car_photo_path"]
        if os.path.exists(path):
            return cv2.imread(path)
        return None
    
    def save_car_photo(self, sl: int, frame: np.ndarray, 
                    slot_id: str, car_id: str) -> str:
        filename = f"{car_id}_{slot_id}.jpg"
        filepath = os.path.join(SNAPSHOT_DIR, filename)
        
        h, w = frame.shape[:2]
        max_dim = 300
        if h > w:
            new_h, new_w = max_dim, int(w * max_dim / h)
        else:
            new_h, new_w = int(h * max_dim / w), max_dim
        
        thumbnail = cv2.resize(frame, (new_w, new_h))
        cv2.imwrite(filepath, thumbnail)
        
        conn = self._get_connection()
        conn.execute("""
            UPDATE parking_history SET car_photo_path = ? WHERE sl = ?
        """, (filepath, sl))
        conn.commit()
        conn.close()
        
        return filepath
    
    def export_csv(self, filepath: str) -> str:
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT sl, slot_id, car_id, plate_number, plate_color,
                   text_color, vehicle_type, ocr_source, time_parked,
                   time_left, duration_minutes, status
            FROM parking_history ORDER BY sl DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        import csv
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "SL", "Slot ID", "Car ID", "License Plate", "Plate Color",
                "Text Color", "Vehicle Type", "OCR Source", "Time Parked",
                "Time Left", "Duration (min)", "Status"
            ])
            for r in rows:
                writer.writerow(r)
        
        return filepath
    
    def clear_history(self):
        conn = self._get_connection()
        conn.execute("DELETE FROM parking_history")
        conn.commit()
        conn.close()
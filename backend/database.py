import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Optional

import config


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS campaigns (
                campaign_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS turn_results (
                turn_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                result TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_turn_campaign ON turn_results(campaign_id);
        """)
        conn.commit()
    finally:
        conn.close()


def save_campaign(campaign: dict) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO campaigns (campaign_id, data, updated_at) VALUES (?, ?, ?)",
            (campaign["campaignId"], json.dumps(campaign), datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_campaign(campaign_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT data FROM campaigns WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["data"])
    finally:
        conn.close()


def save_turn_result(turn_id: str, campaign_id: str, status: str = "running", result: Optional[dict] = None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO turn_results (turn_id, campaign_id, status, result, created_at) VALUES (?, ?, ?, ?, ?)",
            (turn_id, campaign_id, status, json.dumps(result) if result else None, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_turn_result(turn_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status, result FROM turn_results WHERE turn_id = ?", (turn_id,)
        ).fetchone()
        if row is None:
            return {"status": "not_found"}
        result = dict(row)
        if result["result"]:
            result["result"] = json.loads(result["result"])
        return result
    finally:
        conn.close()

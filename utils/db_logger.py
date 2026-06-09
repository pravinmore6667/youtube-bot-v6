"""
utils/db_logger.py
───────────────────
Logger that writes to both console and DB simultaneously.
Feeds the dashboard live log stream via SSE.
"""
import threading
from utils.logger import get_logger as _base_get_logger, BotLogger

_current_job_id: str = ""
_job_lock = threading.Lock()


def set_job(job_id: str):
    global _current_job_id
    with _job_lock:
        _current_job_id = job_id


def clear_job():
    global _current_job_id
    with _job_lock:
        _current_job_id = ""


class DBLogger(BotLogger):
    """Logger that mirrors all writes to the DB agent_logs table."""

    def _emit(self, level: int, msg: str, *args):
        super()._emit(level, msg, *args)
        try:
            import logging
            level_name = {10: "DEBUG", 20: "INFO", 30: "WARNING",
                          40: "ERROR", 50: "CRITICAL"}.get(level, "INFO")
            from database import db
            with _job_lock:
                jid = _current_job_id
            db.add_log(jid, self._name, level_name, str(msg))
            # Also push to SSE broadcaster if dashboard is running
            try:
                from dashboard.app import broadcast_log
                broadcast_log({
                    "ts":      "",   # will be filled by JS
                    "level":   level_name,
                    "agent":   self._name,
                    "message": str(msg),
                    "job_id":  jid,
                })
            except Exception:
                pass
        except Exception:
            pass   # never crash because of logging


def get_logger(name: str) -> DBLogger:
    return DBLogger(name)

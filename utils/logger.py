"""
utils/logger.py
────────────────
Clean structured logging with:
- 4 levels: ERROR, WARNING, INFO, DEBUG
- Rotating log files (5MB × 3 backups)
- Colour terminal output
- Library noise suppression
- Verbose mode via LOG_LEVEL=DEBUG env var
- Thread-safe DB integration
"""
import logging, logging.handlers, os, sys, threading
from datetime import datetime
from pathlib import Path

# ── ANSI colours ──────────────────────────────────────────────
_RESET  = "\033[0m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_GREY   = "\033[90m"
_BOLD   = "\033[1m"

_LEVEL_COLOUR = {
    "DEBUG":   _GREY,
    "INFO":    _CYAN,
    "WARNING": _YELLOW,
    "ERROR":   _RED,
    "SUCCESS": _GREEN,
}

_LOG_DIR = os.getenv("LOG_DIR", "logs")
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ── Suppress noisy libraries ──────────────────────────────────
_SILENT_LIBS = [
    "httpx", "httpcore", "urllib3", "urllib3.connectionpool",
    "groq", "google", "google.auth", "google.genai",
    "google.api_core", "anthropic", "openai", "cerebras",
    "apscheduler", "apscheduler.scheduler",
    "asyncio", "filelock", "PIL", "moviepy",
    "faster_whisper", "ctranslate2",
]
for lib in _SILENT_LIBS:
    logging.getLogger(lib).setLevel(logging.ERROR)


class _ColourFormatter(logging.Formatter):
    """Terminal formatter with colour and optional agent prefix."""
    USE_COLOUR = sys.stdout.isatty() or os.getenv("FORCE_COLOUR")

    def format(self, record):
        ts    = datetime.now().strftime("%H:%M:%S")
        level = record.levelname
        agent = getattr(record, "agent", record.name)
        msg   = record.getMessage()

        if self.USE_COLOUR:
            col = _LEVEL_COLOUR.get(level, "")
            lbl = f"{col}{level:<7}{_RESET}"
            out = f"{_GREY}{ts}{_RESET} {lbl} {_BOLD}{agent:<16}{_RESET} {msg}"
        else:
            out = f"{ts} {level:<7} {agent:<16} {msg}"

        if record.exc_info:
            out += "\n" + self.formatException(record.exc_info)
        return out


class _FileFormatter(logging.Formatter):
    def format(self, record):
        ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        agent = getattr(record, "agent", record.name)
        msg   = record.getMessage()
        out   = f"{ts} | {level:<7} | {agent:<20} | {msg}"
        if record.exc_info:
            out += "\n" + self.formatException(record.exc_info)
        return out


# ── Global root handler setup (runs once) ─────────────────────
_setup_done = False
_setup_lock = threading.Lock()


def _setup_root():
    global _setup_done
    if _setup_done:
        return
    with _setup_lock:
        if _setup_done:
            return

        root = logging.getLogger()
        root.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))
        root.handlers.clear()

        # Console
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(_ColourFormatter())
        ch.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))
        root.addHandler(ch)

        # Rotating file
        try:
            Path(_LOG_DIR).mkdir(parents=True, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                os.path.join(_LOG_DIR, "bot.log"),
                maxBytes=5 * 1024 * 1024,   # 5 MB
                backupCount=3,
                encoding="utf-8",
            )
            fh.setFormatter(_FileFormatter())
            fh.setLevel(logging.DEBUG)   # always DEBUG in file
            root.addHandler(fh)
        except Exception:
            pass  # non-fatal

        _setup_done = True


# ── Logger wrapper ────────────────────────────────────────────
class BotLogger:
    """Logger that adds 'agent' extra and provides .success() method."""

    def __init__(self, name: str):
        _setup_root()
        self._log = logging.getLogger(name)
        self._name = name

    def _emit(self, level: int, msg: str, *args):
        record_args = args if args else ()
        self._log.log(level, msg, *record_args,
                      extra={"agent": self._name},
                      stacklevel=2)

    def debug(self,   msg, *a): self._emit(logging.DEBUG,   msg, *a)
    def info(self,    msg, *a): self._emit(logging.INFO,    msg, *a)
    def warning(self, msg, *a): self._emit(logging.WARNING, msg, *a)
    def error(self,   msg, *a): self._emit(logging.ERROR,   msg, *a)

    def success(self, msg, *a):
        """Green INFO-level success message."""
        if sys.stdout.isatty() or os.getenv("FORCE_COLOUR"):
            formatted = f"{_GREEN}✔ {msg}{_RESET}"
        else:
            formatted = f"✔ {msg}"
        self._emit(logging.INFO, formatted, *a)


def get_logger(name: str) -> BotLogger:
    return BotLogger(name)

import json, os, time, threading
from dataclasses import dataclass, asdict
from utils.logger import get_logger

log = get_logger("HealthMonitor")

METRICS_FILE = "logs/provider_metrics.log"
HEALTH_FILE = "provider_status.json"

@dataclass
class ProviderHealthData:
    healthy: bool = True
    latency: float = 0.0
    success_rate: float = 100.0
    failures: int = 0
    total_calls: int = 0
    total_success: int = 0
    last_failure_time: float = 0.0
    cooldown_until: float = 0.0

class HealthMonitor:
    def __init__(self):
        self._lock = threading.Lock()
        self.health_data: dict[str, ProviderHealthData] = {}
        os.makedirs("logs", exist_ok=True)
        self._load()

    def _load(self):
        if os.path.exists(HEALTH_FILE):
            try:
                with open(HEALTH_FILE, "r") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        # We might need to transform string status to boolean and back if needed
                        if isinstance(v, str):
                            self.health_data[k] = ProviderHealthData(healthy=(v == "healthy"))
                        elif isinstance(v, dict):
                            # Backward compat if reading full dataclass dict
                            self.health_data[k] = ProviderHealthData(**v)
            except Exception:
                pass

    def _save(self):
        with self._lock:
            # We want to maintain provider_status.json like: {"gemini": "healthy", ...}
            # But we also want to persist some stats. Let's save a simpler dict as requested:
            output = {}
            for k, v in self.health_data.items():
                if v.cooldown_until > time.time():
                    status = "degraded"
                else:
                    status = "healthy" if v.healthy else "degraded"
                output[k] = status

            try:
                with open(HEALTH_FILE, "w") as f:
                    json.dump(output, f, indent=2)
            except Exception:
                pass

    def init_provider(self, name: str):
        with self._lock:
            if name not in self.health_data:
                self.health_data[name] = ProviderHealthData()
        self._save()

    def record_success(self, name: str, latency: float):
        with self._lock:
            p = self.health_data.get(name)
            if not p:
                p = ProviderHealthData()
                self.health_data[name] = p
            p.total_calls += 1
            p.total_success += 1
            p.success_rate = (p.total_success / p.total_calls) * 100.0
            p.latency = (p.latency * 0.8) + (latency * 0.2) if p.total_calls > 1 else latency
            p.failures = 0
            p.healthy = True
            p.cooldown_until = 0.0
        self._log_metric(name, latency, True, "")
        self._save()

    def record_failure(self, name: str, error: str, is_rate_limit: bool = False):
        with self._lock:
            p = self.health_data.get(name)
            if not p:
                p = ProviderHealthData()
                self.health_data[name] = p
            p.total_calls += 1
            p.success_rate = (p.total_success / p.total_calls) * 100.0
            p.failures += 1
            p.last_failure_time = time.time()

            # Circuit breaker: 5 consecutive failures = 15 min cooldown
            if is_rate_limit:
                p.cooldown_until = time.time() + 60.0
            elif p.failures >= 5:
                p.cooldown_until = time.time() + (15 * 60) # 15 minutes
                log.warning(f"Circuit Breaker OPEN for {name}. 15 min cooldown.")
            else:
                p.cooldown_until = time.time() + min(300, (2 ** p.failures))

            p.healthy = False
        self._log_metric(name, 0.0, False, error)
        self._save()

    def _log_metric(self, name: str, latency: float, success: bool, error: str):
        try:
            with open(METRICS_FILE, "a") as f:
                ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                status = "SUCCESS" if success else "FAILURE"
                err_str = error.replace("\n", " ")[:200]
                f.write(f"[{ts}] provider={name} latency={latency:.2f}s status={status} error={err_str}\n")
        except Exception:
            pass

    def get_health(self, name: str) -> ProviderHealthData:
        with self._lock:
            if name not in self.health_data:
                self.health_data[name] = ProviderHealthData()

            # Half-open logic: if cooldown has passed, allow testing
            if not self.health_data[name].healthy and self.health_data[name].cooldown_until < time.time():
                # We do not mark it healthy yet, but it's available for one request
                pass

        return self.health_data[name]

monitor = HealthMonitor()

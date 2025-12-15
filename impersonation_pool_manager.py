import json
import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple


_DEFAULT_POOL: List[str] = [
    # Chrome (latest and recent)
    "chrome120", "chrome119", "chrome118", "chrome117", "chrome116", "chrome115", "chrome114", "chrome113", "chrome112", "chrome111", "chrome110",
    "chrome109", "chrome108", "chrome107", "chrome106", "chrome105", "chrome104", "chrome103", "chrome102", "chrome101", "chrome100",
    # Firefox (latest and recent)
    "firefox119", "firefox118", "firefox117", "firefox116", "firefox115", "firefox114", "firefox113", "firefox112", "firefox111", "firefox110",
    "firefox109", "firefox108", "firefox107", "firefox106", "firefox105", "firefox104", "firefox103", "firefox102", "firefox101", "firefox100",
    # Safari (latest and recent)
    "safari17_0", "safari16_6", "safari16_3", "safari16_0", "safari15_6_1", "safari15_3", "safari15_1", "safari14_1",
    # Edge (latest and recent)
    "edge119", "edge118", "edge117", "edge116", "edge115", "edge114", "edge113", "edge112", "edge111", "edge110",
    # Opera (latest and recent)
    "opera102", "opera101", "opera100", "opera99", "opera98", "opera97", "opera96", "opera95",
]


def _safe_read_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _atomic_write_json(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


@dataclass
class ImpersonationDecision:
    fingerprint: str


class ImpersonationPoolManager:
    """Manages curl_cffi impersonation fingerprints across runs.

    Goals:
    - Keep the active pool in a separate file.
    - Persistently demote "bad" fingerprints into a never-success list.
    - Track failure streaks across runs to auto-drop continuously failing fingerprints.

    This class is thread-safe.
    """

    def __init__(
        self,
        impersonate_pool_path: str,
        never_success_tls_path: str,
        health_path: str,
        disable_after_consecutive_failures: int = 8,
        min_failures_before_disable: int = 8,
    ) -> None:
        self.impersonate_pool_path = impersonate_pool_path
        self.never_success_tls_path = never_success_tls_path
        self.health_path = health_path
        self.disable_after_consecutive_failures = int(disable_after_consecutive_failures)
        self.min_failures_before_disable = int(min_failures_before_disable)

        self._lock = threading.Lock()
        self._pool: List[str] = []
        self._never_success: Set[str] = set()
        self._health: Dict[str, dict] = {}
        self._last_flush_ts = 0.0
        self._dirty = False

        self.reload()

    def reload(self) -> None:
        with self._lock:
            pool_obj = _safe_read_json(self.impersonate_pool_path) or {}
            pool = pool_obj.get("impersonate_pool")
            if not isinstance(pool, list) or not pool:
                pool = list(_DEFAULT_POOL)

            never_obj = _safe_read_json(self.never_success_tls_path) or {}
            never = never_obj.get("never_success_tls")
            if not isinstance(never, list):
                never = []

            health_obj = _safe_read_json(self.health_path) or {}
            health = health_obj.get("health")
            if not isinstance(health, dict):
                health = {}

            self._never_success = set(str(x) for x in never)
            # Keep pool order stable-ish, but remove disabled entries
            self._pool = [str(x) for x in pool if str(x) not in self._never_success]
            self._health = health
            self._dirty = False

    def get_active_pool(self) -> List[str]:
        with self._lock:
            return list(self._pool)

    def choose(self) -> ImpersonationDecision:
        with self._lock:
            if not self._pool:
                raise RuntimeError("No valid impersonation fingerprints remaining")
            return ImpersonationDecision(fingerprint=random.choice(self._pool))

    def report_success(self, fp: str) -> None:
        fp = (fp or "").strip()
        if not fp:
            return
        with self._lock:
            h = self._health.setdefault(fp, {})
            h["success"] = int(h.get("success", 0)) + 1
            h["fail"] = int(h.get("fail", 0))
            h["consecutive_failures"] = 0
            h["last_success_ts"] = time.time()
            self._dirty = True
            self._maybe_flush_locked()

    def report_failure(self, fp: str, *, reason: str) -> None:
        fp = (fp or "").strip()
        if not fp:
            return
        with self._lock:
            h = self._health.setdefault(fp, {})
            h["fail"] = int(h.get("fail", 0)) + 1
            h["success"] = int(h.get("success", 0))
            h["consecutive_failures"] = int(h.get("consecutive_failures", 0)) + 1
            h["last_failure_reason"] = reason
            h["last_failure_ts"] = time.time()
            self._dirty = True

            if reason == "not_supported":
                self._disable_locked(fp, reason=reason)
                return

            # Only auto-disable if it has never succeeded and has a streak.
            if (
                int(h.get("success", 0)) == 0
                and int(h.get("fail", 0)) >= self.min_failures_before_disable
                and int(h.get("consecutive_failures", 0)) >= self.disable_after_consecutive_failures
            ):
                self._disable_locked(fp, reason=f"auto_disable:{reason}")
                return

            self._maybe_flush_locked()

    def disable(self, fp: str, *, reason: str) -> None:
        fp = (fp or "").strip()
        if not fp:
            return
        with self._lock:
            self._disable_locked(fp, reason=reason)

    def _disable_locked(self, fp: str, *, reason: str) -> None:
        if fp in self._never_success:
            return
        self._never_success.add(fp)
        self._pool = [x for x in self._pool if x != fp]

        h = self._health.setdefault(fp, {})
        h["disabled"] = True
        h["disabled_reason"] = reason
        h["disabled_ts"] = time.time()
        self._dirty = True

        self._flush_locked()

    def _maybe_flush_locked(self) -> None:
        # Avoid excessive writes under heavy concurrency.
        now = time.time()
        if not self._dirty:
            return
        if now - self._last_flush_ts < 15:
            return
        self._flush_locked()

    def _flush_locked(self) -> None:
        # Persist never-success list and active pool.
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        _atomic_write_json(
            self.never_success_tls_path,
            {"never_success_tls": sorted(self._never_success), "timestamp": timestamp},
        )
        _atomic_write_json(
            self.impersonate_pool_path,
            {"impersonate_pool": list(self._pool), "timestamp": timestamp},
        )
        _atomic_write_json(
            self.health_path,
            {"health": self._health, "timestamp": timestamp},
        )
        self._last_flush_ts = time.time()
        self._dirty = False


def default_manager(repo_root: str) -> ImpersonationPoolManager:
    base_data_dir = os.path.join(repo_root, "base-data")
    return ImpersonationPoolManager(
        impersonate_pool_path=os.path.join(base_data_dir, "impersonate_pool.json"),
        never_success_tls_path=os.path.join(base_data_dir, "never_success_tls.json"),
        health_path=os.path.join(base_data_dir, "impersonate_health.json"),
    )

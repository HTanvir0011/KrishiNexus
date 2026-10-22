"""In-process store of judge-injected live-demo anomalies.

``POST /mcp/simulate-anomaly`` writes here; the coldchain telemetry and haor flood
tools read from here, so an injected cold-chamber power cut or Sunamganj flash
flood immediately changes what the agents observe through MCP.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, Literal

from config import now_bdt

AnomalyType = Literal["cold_chamber_power_cut", "haor_flash_flood"]


@dataclass(frozen=True, slots=True)
class ActiveAnomaly:
    anomaly_id: str
    anomaly_type: AnomalyType
    target: str
    params: Mapping[str, Any]
    activated_at: datetime
    expires_at: datetime

    def is_active(self, at: datetime) -> bool:
        return self.activated_at <= at < self.expires_at

    def minutes_since_activation(self, at: datetime) -> float:
        return max(0.0, (at - self.activated_at).total_seconds() / 60.0)


class AnomalyStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, ActiveAnomaly] = {}

    def inject(
        self,
        anomaly_type: AnomalyType,
        target: str,
        params: Mapping[str, Any],
        duration_minutes: int,
    ) -> ActiveAnomaly:
        activated = now_bdt()
        anomaly = ActiveAnomaly(
            anomaly_id=f"ANM-{uuid.uuid4().hex[:10].upper()}",
            anomaly_type=anomaly_type,
            target=target,
            params=MappingProxyType(dict(params)),
            activated_at=activated,
            expires_at=activated + timedelta(minutes=duration_minutes),
        )
        with self._lock:
            self._items[anomaly.anomaly_id] = anomaly
        return anomaly

    def active(self) -> list[ActiveAnomaly]:
        at = now_bdt()
        with self._lock:
            for anomaly_id in [k for k, v in self._items.items() if v.expires_at <= at]:
                del self._items[anomaly_id]
            return sorted(self._items.values(), key=lambda a: a.activated_at)

    def latest(self, anomaly_type: AnomalyType, predicate: Callable[[ActiveAnomaly], bool]) -> ActiveAnomaly | None:
        matches = [a for a in self.active() if a.anomaly_type == anomaly_type and predicate(a)]
        return matches[-1] if matches else None

    def clear(self, anomaly_id: str) -> bool:
        with self._lock:
            return self._items.pop(anomaly_id, None) is not None

    def clear_all(self) -> int:
        with self._lock:
            count = len(self._items)
            self._items.clear()
            return count


ANOMALIES = AnomalyStore()

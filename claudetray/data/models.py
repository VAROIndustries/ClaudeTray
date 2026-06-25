from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class UsageSnapshot:
    timestamp: datetime
    five_hour_pct: float
    seven_day_pct: float
    context_pct: float
    five_hour_resets_at: Optional[int] = None
    seven_day_resets_at: Optional[int] = None


@dataclass
class SessionInfo:
    session_id: str
    project_dir: str
    model: str
    start_time: datetime
    last_seen: datetime
    total_cost: float
    tokens_in: int
    tokens_out: int


@dataclass
class AppState:
    five_hour_pct: float = 0.0
    seven_day_pct: float = 0.0
    context_pct: float = 0.0
    five_hour_resets_at: Optional[int] = None
    seven_day_resets_at: Optional[int] = None
    session_id: Optional[str] = None
    project_dir: Optional[str] = None
    model: Optional[str] = None
    total_cost: float = 0.0
    total_duration_ms: int = 0
    session_active: bool = False
    last_update: Optional[datetime] = None

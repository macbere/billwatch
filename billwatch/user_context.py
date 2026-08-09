"""
UserContext -- the user's own stated belief, concern, or accusation
(e.g. "I know the hospital overcharged me").

CRITICAL (Phase 3.2/3.2A Gate 2): THIS IS NOT EVIDENCE.

UserContext is a deliberately separate type from Source/Evidence, with no
shared base class and no fields in common with the evidence hierarchy. It
exists only so the user's framing can be stored and displayed back to them
("your stated concern") -- it must never be accepted anywhere an Evidence
object is required. See EvidenceLedger.add_source() in evidence.py for the
runtime guard that enforces this structurally, not just by convention.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass(frozen=True)
class UserContext:
    investigation_id: str
    stated_concern_text: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

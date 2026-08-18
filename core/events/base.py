from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from django.utils import timezone


@dataclass
class DomainEvent:
    """
    Base class for all domain events in SchoolOS.
    """
    event_id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    occurred_at: datetime = field(default_factory=timezone.now)
    school_id: Optional[UUID] = None
    actor_id: Optional[UUID] = None          # who triggered the event
    aggregate_id: Optional[UUID] = None      # the main entity (student, invoice, etc.)
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    aggregate_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "organization_id": str(self.school_id) if self.school_id else None,
            "actor_id": str(self.actor_id) if self.actor_id else None,
            "aggregate_id": str(self.aggregate_id) if self.aggregate_id else None,
            "aggregate_type": self.aggregate_type,
            "payload": self.payload,
            "metadata": self.metadata,
        }
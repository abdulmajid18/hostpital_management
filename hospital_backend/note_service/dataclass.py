
from typing import List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime



@dataclass(frozen=True)
class DoctorNote:
    doctor_id: str
    patient_id: str
    content: str
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert the DoctorNote instance to a dictionary with ISO formatted timestamps."""
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class ChecklistItem:
    """Represents an immediate, one-time task without a scheduled time."""
    description: str
    priority: str = "normal"


@dataclass(frozen=True)
class PlanItem:
    """Represents a scheduled task that occurs over time."""
    description: str
    duration: int
    frequency: str = "daily"
    start_date: Optional[datetime] = None


@dataclass(frozen=True)
class ActionableStepsInput:
    note_id: str
    checklist: List[ChecklistItem]
    plan: List[PlanItem]

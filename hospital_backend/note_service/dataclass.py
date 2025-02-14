from enum import Enum
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


class Priority(Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class FrequencyType(Enum):
    FIXED_TIME = "fixed_time"
    INTERVAL_BASED = "interval_based"
    FREQUENCY_BASED = "frequency_based"


@dataclass
class ChecklistItem:
    description: str
    priority: Priority


@dataclass
class PlanItem:
    description: str
    patient_id: str  # Added patient_id field
    start_date: Optional[datetime]
    duration: int  # Duration in days
    frequency: FrequencyType
    specific_times: Optional[List[str]] = None  # Used for "fixed_time"
    interval_hours: Optional[int] = None  # Used for "interval_based"
    times_per_day: Optional[int] = None  # Used for "frequency_based"

    def validate(self) -> None:
        """Validate plan item configuration based on frequency type."""
        if self.frequency == FrequencyType.FIXED_TIME and not self.specific_times:
            raise ValueError("specific_times required for fixed_time frequency")
        if self.frequency == FrequencyType.INTERVAL_BASED and not self.interval_hours:
            raise ValueError("interval_hours required for interval_based frequency")
        if self.frequency == FrequencyType.FREQUENCY_BASED and not self.times_per_day:
            raise ValueError("times_per_day required for frequency_based frequency")


@dataclass
class ActionableStepsInput:
    note_id: str
    checklist: List[ChecklistItem]
    plan: List[PlanItem]

import logging
import os
import json
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from openai import OpenAI, Stream
from dotenv import load_dotenv
from openai.types.chat import ChatCompletion

from note_service.dataclass import ChecklistItem, PlanItem
from note_service.rabbitmq_manager import RabbitMQManager
from note_service.mongo_manager import MongoDBManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class Priority(Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class FrequencyType(Enum):
    FIXED_TIME = "fixed_time"
    INTERVAL_BASED = "interval_based"
    FREQUENCY_BASED = "frequency_based"


@dataclass
class NoteInput:
    note_content: str
    note_id: str
    patient_id: str

    def to_dict(self):
        return asdict(self)


@dataclass
class ActionableSteps:
    note_id: str
    checklist: List[ChecklistItem]
    plan: List[PlanItem]

    def to_dict(self):
        return asdict(self)


class LLMProcessor:
    SYSTEM_PROMPT = """
    You are a medical assistant that extracts actionable steps from a doctor's note. 
    Return a JSON object with a 'checklist' (list of tasks) and a 'plan' (list of scheduled tasks).

    Checklist tasks should have:
    - 'description': A brief description of the task.
    - 'priority': Priority level (High, Medium, Low).

    Plan tasks should include:
    - 'description': A brief description of the task (e.g., "Take blood pressure medication").
    - 'patient_id': The ID of the patient.
    - 'start_date': Start date in YYYY-MM-DD format.
    - 'duration': Duration in days (e.g., 7 for 7 days).
    - 'frequency': Frequency type (fixed_time, interval_based, frequency_based).
    - 'specific_times': Specific times for 'fixed_time' frequency (e.g., ["09:00", "21:00"]).
    - 'interval_hours': Interval in hours for 'interval_based' frequency (e.g., 4 for every 4 hours).
    - 'times_per_day': Number of times per day for 'frequency_based' frequency (e.g., 3 for 3 times a day).

    For medication-related tasks:
    - Ensure the description includes the drug name and dosage (e.g., "Take 500mg of Paracetamol").
    - Specify the exact times for 'fixed_time' frequency (e.g., ["08:00", "20:00"] for morning and evening doses).
    - For 'interval_based' tasks, specify the interval in hours (e.g., "Check temperature every 4 hours").
    - For 'frequency_based' tasks, specify the number of times per day (e.g., "Do breathing exercises 3 times a day").

    Example JSON output:
    {
        "checklist": [
            {
                "description": "Monitor blood pressure daily",
                "priority": "High"
            }
        ],
        "plan": [
            {
                "description": "Take 500mg of Paracetamol",
                "patient_id": "patient123",
                "start_date": "2025-02-14",
                "duration": 7,
                "frequency": "fixed_time",
                "specific_times": ["08:00", "20:00"]
            },
            {
                "description": "Check temperature",
                "patient_id": "patient123",
                "start_date": "2025-02-14",
                "duration": 3,
                "frequency": "interval_based",
                "interval_hours": 4
            },
            {
                "description": "Do breathing exercises",
                "patient_id": "patient123",
                "start_date": "2025-02-14",
                "duration": 5,
                "frequency": "frequency_based",
                "times_per_day": 3
            }
        ]
    }

    Make sure the output strictly follows this structure and includes all required fields.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialize()
            self._initialized = True

    def _initialize(self):
        # Initialization logic for LLMProcessor
        """Initialize LLMProcessor with required connections and configurations."""
        self.rabbitmq = RabbitMQManager()
        self.mongo = MongoDBManager()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(
            api_key=self.openai_api_key
        )
        print("LLMProcessor initialized")

    def process_note(self, note_input: NoteInput) -> ActionableSteps:
        """
        Process a doctor's note and generate structured actionable steps using ChatGPT.

        Args:
            note_input: NoteInput dataclass containing note content and metadata

        Returns:
            ActionableSteps: Structured representation of extracted tasks

        Raises:
            ValueError: If note content is empty or invalid
            openai.error.OpenAIError: If API call fails
            json.JSONDecodeError: If response parsing fails
        """
        if not note_input.note_content or not note_input.note_content.strip():
            raise ValueError("Note content cannot be empty")

        logger.info(f"Processing note {note_input.note_id} for patient {note_input.patient_id}")

        try:
            response = self._get_llm_response(note_input.note_content)
            return self._parse_llm_response(response, note_input.note_id, note_input.patient_id)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response for note {note_input.note_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to process note {note_input.note_id}: {str(e)}")
            raise

    def _get_llm_response(self, note_content: str) -> ChatCompletion:
        """
        Make API call to OpenAI and get response.

        Args:
            note_content: The doctor's note content to process

        Returns:
            ChatCompletion: The response from OpenAI

        Raises:
            openai.error.OpenAIError: If the API call fails
        """
        logger.debug(f"Sending request to OpenAI API (content length: {len(note_content)})")
        try:
            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract actionable steps from this doctor's note:\n{note_content}"}
                ],
                temperature=0.3,  # Added for more consistent structured output
                response_format={"type": "json_object"}  # Ensure JSON response
            )
            return completion
        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise

    def _parse_llm_response(self, response: ChatCompletion, note_id: str, patient_id: str) -> ActionableSteps:
        """
        Parse LLM response and convert to structured format.

        Args:
            response: The ChatCompletion response from OpenAI
            note_id: The ID of the note being processed
            patient_id: The ID of the patient

        Returns:
            ActionableSteps: Structured representation of the tasks

        Raises:
            json.JSONDecodeError: If JSON parsing fails
            KeyError: If required fields are missing from the response
        """
        try:
            llm_output = response.choices[0].message.content
            actionable_steps = json.loads(llm_output)

            # Validate required fields
            if not isinstance(actionable_steps, dict):
                raise ValueError("LLM response is not a dictionary")
            if "checklist" not in actionable_steps or "plan" not in actionable_steps:
                raise ValueError("Missing required fields in LLM response")

            # Convert to structured objects
            checklist_items = [
                ChecklistItem(
                    description=item["description"],
                    priority=Priority(item["priority"])
                )
                for item in actionable_steps.get("checklist", [])
            ]

            plan_items = [
                PlanItem(
                    description=item["description"],
                    patient_id=patient_id,
                    start_date=datetime.strptime(item.get("start_date", datetime.today().strftime("%Y-%m-%d")),
                                                 "%Y-%m-%d"),
                    duration=item["duration"],
                    frequency=FrequencyType(item["frequency"]),
                    specific_times=item.get("specific_times", [])
                )
                for item in actionable_steps.get("plan", [])
            ]

            return ActionableSteps(
                note_id=note_id,
                checklist=checklist_items,
                plan=plan_items
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {str(e)}")
            raise
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Mapping

from django.contrib.auth import get_user_model
from pymongo import MongoClient, collection
from pymongo.errors import PyMongoError, ConnectionFailure
from pymongo.synchronous.collection import Collection

from .dataclass import DoctorNote, ActionableStepsInput, ChecklistItem, PlanItem, FrequencyType

from dotenv import load_dotenv

from task_processing_service.schedular import StateScheduler

from .encryption import EncryptionUtils

User = get_user_model()
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from contextlib import contextmanager


class MongoDBManagerError(Exception):
    """Custom exception for MongoDB manager errors"""
    pass


class MongoDBManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._initialize()
            self._initialized = True

    def _initialize(self):
        try:
            mongo_conn = os.getenv("MONGO_CONN", "mongodb://localhost:27017/")
            if not mongo_conn:
                raise MongoDBManagerError("MongoDB connection string not found in environment variables")

            self.client = MongoClient(mongo_conn, serverSelectionTimeoutMS=5000)
            db_name = os.getenv("MONGO_DB_NAME", "hospital_db")

            self.client.server_info()
            self.db = self.client[db_name]
            logger.info(f"Successfully connected to MongoDB database: {db_name}")

        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise MongoDBManagerError(f"Could not connect to MongoDB: {e}")

        except Exception as e:
            logger.error(f"Error initializing MongoDB connection: {e}")
            raise MongoDBManagerError(f"Error initializing MongoDB: {e}")

    def get_collection(self, collection_name: str) -> collection.Collection:
        """Return a MongoDB collection instance with validation"""
        if not collection_name:
            raise ValueError("Collection name cannot be empty")
        return self.db[collection_name]

    @contextmanager
    def ensure_connection(self):
        """Ensure MongoDB connection is active before executing any operation."""
        try:
            logger.info("Checking MongoDB connection --- it's up")
            yield
        except PyMongoError as e:
            logger.error(f"MongoDB error: {e}")
            raise
        finally:
            self.close_connection()  # Ensuring connection is closed when done

    def _convert_note_to_dict(self, note: DoctorNote) -> Dict[str, Any]:
        """Convert DoctorNote to dictionary with validation"""
        if not note.doctor_id or not note.patient_id:
            raise ValueError("Doctor ID and Patient ID are required")

        return {
            "doctor_id":str( note.doctor_id),
            "patient_id": str(note.patient_id),
            "content": note.content,
            "created_at": note.created_at or datetime.utcnow(),
            "updated_at": note.updated_at or datetime.utcnow()
        }

    def create_note(self, note: DoctorNote) -> str:
        """Create a new doctor note with enhanced error handling"""
        try:
            notes_collection = self.get_collection("notes")
            note_data = self._convert_note_to_dict(note)
            patient_id = note_data.get("patient_id")
            content = note_data.get("content")
            patient = User.objects.get(id=patient_id)
            encrypted_note = EncryptionUtils.encrypt_note(content, patient.public_key)
            note_data["content"] = encrypted_note
            result = notes_collection.insert_one(note_data)
            logger.info(f"Successfully created note with ID: {result.inserted_id}")
            return str(result.inserted_id)

        except PyMongoError as e:
            logger.error(f"MongoDB error creating note: {e}")
            raise MongoDBManagerError(f"Failed to create note: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating note: {e}")
            raise MongoDBManagerError(f"Unexpected error creating note: {e}")

    def get_note_by_patient(self, patient_id: str) -> Mapping[str, Any] | None:
        """Retrieve a single note for a given patient ID"""
        if not patient_id:
            raise ValueError("Patient ID cannot be empty")

        try:
            notes_collection = self.get_collection("notes")
            note = notes_collection.find_one({"patient_id": patient_id})

            if note:
                note["note_id"] = str(note["_id"])
                logger.info(f"Retrieved note for patient {patient_id}")
                return note
            else:
                logger.info(f"No note found for patient {patient_id}")
                return None

        except PyMongoError as e:
            logger.error(f"MongoDB error retrieving note for patient {patient_id}: {e}")
            raise MongoDBManagerError(f"Failed to retrieve note for patient {patient_id}: {e}")

        except Exception as e:
            logger.error(f"Unexpected error retrieving note for patient {patient_id}: {e}")
            raise MongoDBManagerError(f"Unexpected error retrieving note for patient {patient_id}: {e}")

    def close_connection(self) -> None:
        """Safely close MongoDB connection"""
        try:
            if hasattr(self, 'client'):
                self.client.close()
                logger.info("MongoDB connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")

    def __enter__(self) -> 'MongoDBManager':
        """Support for context manager protocol"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Ensure connection is closed when exiting context"""
        self.close_connection()

    def __del__(self) -> None:
        """Ensure connection is closed when object is destroyed"""
        self.close_connection()


class ActionableStepsProcessor:
    def __init__(self, db_manager: Any, scheduler: StateScheduler, logger: logging.Logger):
        self.db_manager = db_manager
        self.scheduler = scheduler
        self.logger = logger

    def get_collection(self) -> Collection:
        """Get MongoDB collection for actionable steps."""
        return self.db_manager.get_collection("actionable_steps")

    def _create_checklist_step(self, note_id: str, item: 'ChecklistItem', current_time: datetime) -> Dict[str, Any]:
        """Create a document for a checklist item."""
        return {
            "note_id": note_id,
            "type": "Checklist",
            "description": item.description,
            "priority": item.priority.value,
            "created_at": current_time,
            "updated_at": current_time,
            "status": "pending"
        }

    def _create_plan_step(self, note_id: str, item: 'PlanItem', current_time: datetime) -> Dict[str, Any]:
        """Create a document for a plan item and set up its schedule."""
        item.validate()
        start_date = item.start_date or current_time

        schedule_data = {
            "start_date": start_date,
            "duration": item.duration,
            "end_date": start_date + timedelta(days=item.duration),
            "type": item.frequency.value
        }

        # Add frequency-specific fields
        if item.frequency == FrequencyType.FIXED_TIME:
            schedule_data["specific_times"] = item.specific_times if item.specific_times is not None else []
        elif item.frequency == FrequencyType.INTERVAL_BASED:
            schedule_data["interval_hours"] = item.interval_hours if item.interval_hours is not None else 0
        elif item.frequency == FrequencyType.FREQUENCY_BASED:
            schedule_data["times_per_day"] = item.times_per_day if item.times_per_day is not None else 0

        step_data = {
            "note_id": note_id,
            "type": "Plan",
            "description": item.description,
            "schedule": schedule_data,
            "created_at": current_time,
            "updated_at": current_time,
            "status": "scheduled"
        }
        return step_data

    def create_actionable_steps(self, steps_input: 'ActionableStepsInput') -> List[str]:
        """Process and create actionable steps from doctor's notes."""
        collections = self.get_collection()
        current_time = datetime.utcnow()
        steps_to_insert = []

        try:
            # Cancel existing schedules for this note
            self.scheduler.cancel_note_schedules(steps_input.note_id)

            # Remove existing steps for this note
            collections.delete_many({"note_id": steps_input.note_id})

            # Process immediate tasks (Checklist)
            steps_to_insert.extend(
                self._create_checklist_step(steps_input.note_id, task, current_time)
                for task in steps_input.checklist
            )

            # Process scheduled tasks (Plan)
            for plan_item in steps_input.plan:
                step_data = self._create_plan_step(steps_input.note_id, plan_item, current_time)
                steps_to_insert.append(step_data)
                # Store schedule state for plan items
                self.scheduler.store_schedule_state(
                    note_id=steps_input.note_id,
                    patient_id=plan_item.patient_id,  # Added patient_id to PlanItem
                    description=plan_item.description,
                    schedule=step_data['schedule']
                )

            if not steps_to_insert:
                self.logger.info("No actionable steps to insert")
                return []

            result = collections.insert_many(steps_to_insert)
            inserted_ids = [str(id_) for id_ in result.inserted_ids]
            self.logger.info(f"Successfully created {len(inserted_ids)} actionable steps")
            return inserted_ids

        except PyMongoError as e:
            self.logger.error(f"MongoDB error creating actionable steps: {e}")
            raise MongoDBManagerError(f"Failed to create actionable steps: {e}")
        except ValueError as e:
            self.logger.error(f"Validation error creating actionable steps: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error creating actionable steps: {e}")
            raise MongoDBManagerError(f"Unexpected error creating actionable steps: {e}")

    def get_actionable_steps_by_note_id(self, note_id: str) -> List[Dict[str, Any]]:
        """Retrieve all actionable steps linked to a given note ID."""
        if not note_id:
            raise ValueError("Note ID cannot be empty")

        try:
            collection = self.get_collection()
            steps = list(collection.find({"note_id": note_id}, {"_id": 0}))  # Exclude MongoDB _id

            if not steps:
                self.logger.info(f"No actionable steps found for note ID {note_id}")
                return []

            self.logger.info(f"Retrieved {len(steps)} actionable steps for note ID {note_id}")
            return steps

        except PyMongoError as e:
            self.logger.error(f"MongoDB error retrieving actionable steps for note {note_id}: {e}")
            raise MongoDBManagerError(f"Failed to retrieve actionable steps: {e}")

        except Exception as e:
            self.logger.error(f"Unexpected error retrieving actionable steps for note {note_id}: {e}")
            raise MongoDBManagerError(f"Unexpected error retrieving actionable steps: {e}")

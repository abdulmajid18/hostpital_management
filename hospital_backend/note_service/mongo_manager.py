import logging
import os
from datetime import datetime, timedelta
from typing import List
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from .dataclass import DoctorNote, ActionableStepsInput

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from contextlib import contextmanager


class MongoDBManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        mongo_conn = os.getenv("MONGO_CONN", "mongodb://localhost:27017/")
        self.client = MongoClient(mongo_conn)
        self.db = self.client[os.getenv("MONGO_DB_NAME", "hospital_db")]

    def get_collection(self, collection_name: str):
        """Return a MongoDB collection instance."""
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

    def create_note(self, note: DoctorNote) -> str:
        """Create a new doctor note in the database."""
        notes_collection = self.get_collection("notes")
        note_data = {
            "doctor_id": note.doctor_id,
            "patient_id": note.patient_id,
            "content": note.content,
            "created_at": note.created_at,
            "updated_at": note.updated_at
        }
        with self.ensure_connection():
            try:
                result = notes_collection.insert_one(note_data)
                return str(result.inserted_id)
            except PyMongoError as e:
                logger.error(f"Error creating note: {e}")
                raise

    def create_actionable_steps(self, steps_input: ActionableStepsInput) -> List[str]:
        """Process and create actionable steps from doctor's notes."""
        actionable_steps_collection = self.get_collection("actionable_steps")

        with self.ensure_connection():
            try:
                # Remove existing steps for this note
                actionable_steps_collection.delete_many({"note_id": steps_input.note_id})

                steps_to_insert = []
                current_time = datetime.utcnow()

                # Process immediate tasks (Checklist)
                for task in steps_input.checklist:
                    steps_to_insert.append({
                        "note_id": steps_input.note_id,
                        "type": "Checklist",
                        "description": task.description,
                        "priority": task.priority,
                        "due_date": current_time + timedelta(hours=24),  # Default 24-hour deadline
                        "is_completed": False,
                        "created_at": current_time
                    })

                # Process scheduled tasks (Plan)
                for plan_item in steps_input.plan:
                    start_date = plan_item.start_date or current_time
                    due_date = start_date + timedelta(days=plan_item.duration)

                    steps_to_insert.append({
                        "note_id": steps_input.note_id,
                        "type": "Plan",
                        "description": plan_item.description,
                        "frequency": plan_item.frequency,
                        "start_date": start_date,
                        "due_date": due_date,
                        "is_completed": False,
                        "created_at": current_time
                    })

                # Insert actionable steps into the collection
                if steps_to_insert:
                    result = actionable_steps_collection.insert_many(steps_to_insert)
                    return [str(_id) for _id in result.inserted_ids]
                return []
            except PyMongoError as e:
                logger.error(f"Error creating actionable steps: {e}")
                raise

    def close_connection(self):
        """Close the MongoDB connection."""
        self.client.close()

    def __del__(self):
        """Ensure connection is closed when object is destroyed."""
        self.close_connection()

# Example usage
# if __name__ == "__main__":
#     mongo = MongoDB()
#
#     # Create a test note
#     note = DoctorNote(
#         doctor_id="doctor123",
#         patient_id="patient456",
#         content="Patient needs to take medication."
#     )
#     note_id = mongo.create_note(note)
#
#     # Create test actionable steps
#     steps = ActionableStepsInput(
#         note_id=note_id,
#         checklist=[
#             ChecklistItem(
#                 description="Pick up prescription from pharmacy",
#                 priority="high"
#             )
#         ],
#         plan=[
#             PlanItem(
#                 description="Take medication with food",
#                 duration=7,
#                 frequency="twice_daily"
#             )
#         ]
#     )

# step_ids = mongo.create_actionable_steps(steps)
# print(f"Created Actionable Steps: {step_ids}")
#
# mongo.close_connection()

import json
import logging


from note_service.mongo_manager import MongoDBManager, ActionableStepsProcessor
from note_service.rabbitmq_manager import RabbitMQManager
from task_processing_service.llm_generator import LLMProcessor, NoteInput
from task_processing_service.schedular import StateScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Task:
    def __init__(self):
        """Initialize Task with RabbitMQ connection and model."""
        self.rabbitmq = RabbitMQManager()
        self.mongo = MongoDBManager()
        self.llm_processor = LLMProcessor()
        self.schedular = StateScheduler(self.mongo, logger)
        self.actionable_steps_processor = ActionableStepsProcessor(self.mongo, self.schedular, logger)

    def train_on_llm(self, data: NoteInput):
        """
        Train the model on LLM-generated data.

        Args:
            data: Content of the doctor's note

        Raises:
            ValueError: If training data is empty
        """
        if not data:
            raise ValueError("Training data cannot be empty")

        try:
            logger.info(f"Starting training on note content: ...")  # Log truncated content
            logger.info("Training completed successfully")
            return self.llm_processor.process_note(data)
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise

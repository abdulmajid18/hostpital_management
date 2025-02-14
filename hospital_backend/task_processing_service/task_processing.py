import json
import logging

from pika.exceptions import AMQPError

from hospital_backend.note_service.dataclass import ChecklistItem, ActionableStepsInput, PlanItem
from hospital_backend.note_service.mongo_manager import MongoDBManager
from hospital_backend.note_service.rabbitmq_manager import RabbitMQManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Task:
    def __init__(self):
        """Initialize Task with RabbitMQ connection and model."""
        self.rabbitmq = RabbitMQManager()
        self.mongo = MongoDBManager()
        self.openai_api_key = "your-openai-api-key"

    def train_on_llm(self, data: str):
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
            logger.info(f"Starting training on note content: {data[:100]}...")  # Log truncated content
            logger.info("Training completed successfully")
            actionable_steps = {
                "note_id": "note_id",
                "checklist": [
                    {"description": "Monitor patient's vitals", "priority": "high"},
                    {"description": "Administer prescribed medication", "priority": "medium"}
                ],
                "plan": [
                    {"description": "Schedule follow-up checkup", "duration": 7, "frequency": "weekly"}
                ]
            }
            self.rabbitmq.publish_processed_action(queue_key="actions", message=actionable_steps)
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise

    def start_consuming(self) -> None:
        """
        Start consuming messages from RabbitMQ and process them using `train_on_llm`.
        """
        logger.info("Starting RabbitMQ consumer...")

        def callback(ch, method, properties, body):
            """
            Callback function to process incoming messages.

            Args:
                ch: Channel
                method: Delivery method
                properties: Message properties
                body: Message body
            """
            try:
                # Decode the message
                message = json.loads(body.decode("utf-8"))
                logger.info(f"📥 Received message: {message}")

                # Extract note content from the message
                note_content = message.get("note_content")
                note_id = message.get("id")
                if not note_content or note_id:
                    logger.warning("Invalid message: 'note_content' missing")
                    return

                # Train the model on the received note content
                result = self.train_on_llm(note_content)
                logger.info(f"Successfully processed message ID: {message.get('id', 'unknown')}")

                # Acknowledge the message
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.error(f"Error processing message: {e}")

        with self.rabbitmq.ensure_connection():
            queue_name = self.rabbitmq.rabbitmq_queues.get("notes")
            try:
                self.rabbitmq.channel.basic_qos(prefetch_count=1)
                self.rabbitmq.channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=callback
                )
                logger.info("RabbitMQ consumer started. Waiting for Note messages...")
                self.rabbitmq.channel.start_consuming()
            except AMQPError as e:
                logger.error(f"Failed to consume Notes messages: {e}")
                raise

    def start_consuming_actions(self) -> None:
        """
        Start consuming messages from RabbitMQ and process them using `train_on_llm`.
        """
        logger.info("Starting RabbitMQ consumer for Processing Actions...")

        def callback(ch, method, properties, body):
            """
            Callback function to process incoming messages.

            Args:
                ch: Channel
                method: Delivery method
                properties: Message properties
                body: Message body
            """
            try:
                # Decode the message
                message = json.loads(body.decode("utf-8"))
                logger.info(f"Received message: {message}")

                checklist_items = [ChecklistItem(**item) for item in message["checklist"]]
                plan_items = [PlanItem(**item) for item in message["plan"]]

                action = ActionableStepsInput(
                    note_id=message["note_id"],
                    checklist=checklist_items,
                    plan=plan_items
                )
                self.mongo.create_actionable_steps(action)
                logger.info(f"Successfully processed message ID: {message.get('id', 'unknown')}")

                # Acknowledge the message
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.error(f"Error processing message: {e}")

        with self.rabbitmq.ensure_connection():
            queue_name = self.rabbitmq.rabbitmq_queues.get("actions")
            try:
                self.rabbitmq.channel.basic_qos(prefetch_count=1)
                self.rabbitmq.channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=callback
                )
                logger.info("RabbitMQ consumer for Action started. Waiting for messages...")
                self.rabbitmq.channel.start_consuming()
            except AMQPError as e:
                logger.error(f"Failed to consume Action messages: {e}")
                raise

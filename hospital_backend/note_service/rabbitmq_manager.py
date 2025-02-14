import os
import json
import logging
from typing import Callable, Dict, Optional
import pika
from pika.exceptions import AMQPConnectionError, AMQPError
from contextlib import contextmanager

from dotenv import load_dotenv

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RabbitMQManager:
    _instance: Optional['RabbitMQManager'] = None

    def __new__(cls) -> 'RabbitMQManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize RabbitMQ connection settings."""
        self.rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
        self.rabbitmq_queues = {
            "notes": os.getenv("NOTES_QUEUE", "notes_queue"),
            "actions": os.getenv("ACTIONS_QUEUE", "actions_queue")
        }
        self.connection = None
        self.channel = None
        self._connect()

    def _connect(self) -> None:
        """Establish connection to RabbitMQ and set up channel."""
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.rabbitmq_host,
                    heartbeat=600,  # Add heartbeat to prevent connection timeout
                    blocked_connection_timeout=300
                )
            )
            self.channel = self.connection.channel()
            for queue in self.rabbitmq_queues.values():
                self.channel.queue_declare(
                    queue=queue,
                    durable=True,
                    arguments={'x-message-ttl': 86400000}  # 24-hour TTL
                )
                print(f"Queue declared: {queue}")
            logger.info("Successfully connected to RabbitMQ")
        except AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
        except AMQPError as e:
            logger.error(f"RabbitMQ error: {e}")
            raise

    @contextmanager
    def ensure_connection(self):
        try:
            if not self.connection or self.connection.is_closed:
                self._connect()
            yield
        except (AMQPConnectionError, AMQPError) as e:
            logger.error(f"Connection error: {e}")
            self._connect()
            yield

    def publish_note_for_training(self, queue_key: str, message: Dict) -> None:
        """
        Publish a message to RabbitMQ with retry logic.

        Args:
            message: Dictionary containing message data
            :param message:
            :param queue_key:
        """

        queue_name = self.rabbitmq_queues.get(queue_key)
        if not queue_name:
            raise ValueError(f"Queue key '{queue_key}' is not defined!")

        with self.ensure_connection():
            try:
                self.channel.basic_publish(
                    exchange="",
                    routing_key=queue_name,
                    body=json.dumps(message).encode("utf-8"),
                    properties=pika.BasicProperties(
                        delivery_mode=pika.DeliveryMode.Persistent,
                        content_type='application/json'
                    )
                )
                logger.info(f"Published message to {queue_name}: {message}")
            except AMQPError as e:
                logger.error(f"Failed to publish message: {e}")
                raise

    def publish_processed_action(self, queue_key: str, message: Dict) -> None:
        """
        Publish a message to RabbitMQ with retry logic.

        Args:
            message: Dictionary containing message data
            :param message:
            :param queue_key:
        """
        queue_name = self.rabbitmq_queues.get(queue_key)
        if not queue_name:
            raise ValueError(f"Queue key '{queue_key}' is not defined!")

        with self.ensure_connection():
            try:
                self.channel.basic_publish(
                    exchange="",
                    routing_key=queue_name,
                    body=json.dumps(message).encode("utf-8"),
                    properties=pika.BasicProperties(
                        delivery_mode=pika.DeliveryMode.Persistent,
                        content_type='application/json'
                    )
                )
                logger.info(f"Published message to {queue_name}: {message}")
            except AMQPError as e:
                logger.error(f"Failed to publish message: {e}")
                raise

    def close_connection(self) -> None:
        """Safely close the RabbitMQ connection."""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("RabbitMQ connection closed")
        except AMQPError as e:
            logger.error(f"Failed to close RabbitMQ connection: {e}")
            raise

    def __del__(self) -> None:
        """Ensure connection is closed when object is destroyed."""
        self.close_connection()

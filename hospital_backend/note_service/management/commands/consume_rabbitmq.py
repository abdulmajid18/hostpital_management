import pika
import json
from django.core.management.base import BaseCommand
from django.conf import settings

import logging

from note_service.dataclass import ActionableStepsInput
from task_processing_service.llm_generator import NoteInput
from task_processing_service.task_processing import Task

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs RabbitMQ consumer"

    def handle(self, *args, **kwargs):
        task = Task()

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
                note_id = message.get("note_id")
                if not note_content or not note_id:
                    logger.warning("Invalid message: 'note_content' missing")
                    return
                patient_id = message.get("patient_id")
                note_input = NoteInput(note_content=note_content, note_id=note_id, patient_id=patient_id)
                action = task.train_on_llm(note_input)
                print("*************", action)
                action_input = ActionableStepsInput(
                    note_id=action.note_id,
                    checklist=action.checklist,
                    plan=action.plan
                )
                task.actionable_steps_processor.create_actionable_steps(action_input)
                logger.info(f"Successfully Saved Actions and Plans from llm")
                logger.info(f"Successfully processed message by LLM Queue")

                # Acknowledge the message
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.error(f"Error processing message: {e}")

        connection_params = pika.ConnectionParameters(
            host=settings.RABBITMQ["HOST"],
            port=settings.RABBITMQ["PORT"],
            credentials=pika.PlainCredentials(
                settings.RABBITMQ["USER"], settings.RABBITMQ["PASSWORD"]
            ),
        )

        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()
        channel.queue_declare(queue=settings.RABBITMQ["QUEUE_NAME"], durable=True,
                              arguments={'x-message-ttl': 86400000})
        channel.basic_consume(queue=settings.RABBITMQ["QUEUE_NAME"], on_message_callback=callback)

        print("Waiting for messages. To exit, press CTRL+C")
        channel.start_consuming()

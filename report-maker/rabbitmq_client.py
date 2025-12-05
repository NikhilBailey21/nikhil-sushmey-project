"""
RabbitMQ client utilities for worker to consume jobs from the queue.
"""
import os
import json
import logging
import pika
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Default queue name for report generation jobs
DEFAULT_QUEUE_NAME = "report_generation_queue"


def get_rabbitmq_connection() -> Optional[pika.BlockingConnection]:
    """
    Create and return a RabbitMQ connection.
    
    Reads connection parameters from environment variables:
    - RABBITMQ_HOST: RabbitMQ server host (default: localhost)
    - RABBITMQ_PORT: RabbitMQ server port (default: 5672)
    - RABBITMQ_USER: RabbitMQ username (default: admin)
    - RABBITMQ_PASS: RabbitMQ password (default: admin)
    - RABBITMQ_VHOST: RabbitMQ virtual host (default: /)
    
    Returns:
        pika.BlockingConnection or None if connection fails
    """
    try:
        host = os.environ.get("RABBITMQ_HOST", "localhost")
        port = int(os.environ.get("RABBITMQ_PORT", "5672"))
        username = os.environ.get("RABBITMQ_USER", "admin")
        password = os.environ.get("RABBITMQ_PASS", "admin")
        vhost = os.environ.get("RABBITMQ_VHOST", "/")
        
        credentials = pika.PlainCredentials(username, password)
        parameters = pika.ConnectionParameters(
            host=host,
            port=port,
            virtual_host=vhost,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        
        connection = pika.BlockingConnection(parameters)
        logger.info(f"Successfully connected to RabbitMQ at {host}:{port}")
        return connection
        
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
        return None


def consume_jobs(queue_name: str, callback: Callable, auto_ack: bool = False):
    """
    Start consuming jobs from the RabbitMQ queue.
    
    Args:
        queue_name: Name of the queue to consume from
        callback: Function to call for each message
                  Should accept (channel, method, properties, body) parameters
        auto_ack: If True, automatically acknowledge messages (not recommended for reliability)
    """
    connection = get_rabbitmq_connection()
    if not connection:
        logger.error("Cannot consume jobs: RabbitMQ connection failed")
        return
    
    try:
        channel = connection.channel()
        
        # Declare queue with durability and priority support
        channel.queue_declare(
            queue=queue_name,
            durable=True,  # Queue survives broker restart
            arguments={'x-max-priority': 255}  # Support priority queue
        )
        
        # Set QoS to process one message at a time
        channel.basic_qos(prefetch_count=1)
        
        # Set up consumer
        channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=auto_ack
        )
        
        logger.info(f"Starting to consume jobs from queue '{queue_name}'...")
        channel.start_consuming()
        
    except KeyboardInterrupt:
        logger.info("Stopping consumer...")
        if connection:
            connection.close()
    except Exception as e:
        logger.error(f"Error consuming jobs: {str(e)}")
        if connection:
            connection.close()


def acknowledge_message(channel: pika.channel.Channel, method: pika.spec.Basic.Deliver):
    """
    Acknowledge a message after successful processing.
    
    Args:
        channel: The channel the message was received on
        method: The method frame from the message
    """
    channel.basic_ack(delivery_tag=method.delivery_tag)


def reject_message(channel: pika.channel.Channel, method: pika.spec.Basic.Deliver, requeue: bool = True):
    """
    Reject a message (e.g., if processing failed).
    
    Args:
        channel: The channel the message was received on
        method: The method frame from the message
        requeue: If True, message will be requeued; if False, it will be discarded
    """
    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=requeue)


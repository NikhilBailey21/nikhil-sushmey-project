"""
RabbitMQ client utilities for connecting to and interacting with RabbitMQ.
Used by both server (flask-app) and worker (report-maker).
"""
import os
import json
import logging
import signal
import pika
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger(__name__)

# Default queue name for report generation jobs
DEFAULT_QUEUE_NAME = "report_generation_queue"


def get_rabbitmq_connection(require_all_env_vars: bool = False) -> Optional[pika.BlockingConnection]:
    """
    Create and return a RabbitMQ connection.
    
    Reads connection parameters from environment variables:
    - RABBITMQ_HOST: RabbitMQ server host
    - RABBITMQ_PORT: RabbitMQ server port
    - RABBITMQ_USER: RabbitMQ username
    - RABBITMQ_PASS: RabbitMQ password
    - RABBITMQ_VHOST: RabbitMQ virtual host
    
    Args:
        require_all_env_vars: If True, raises RuntimeError if any env var is missing.
                             If False, uses defaults (localhost, admin, etc.)
    
    Raises:
        RuntimeError: If require_all_env_vars=True and any required environment variables are not set
    
    Returns:
        pika.BlockingConnection or None if connection fails
    """
    try:
        if require_all_env_vars:
            # Strict validation (used by server)
            required_vars = {
                "RABBITMQ_HOST": os.environ.get("RABBITMQ_HOST"),
                "RABBITMQ_PORT": os.environ.get("RABBITMQ_PORT"),
                "RABBITMQ_USER": os.environ.get("RABBITMQ_USER"),
                "RABBITMQ_PASS": os.environ.get("RABBITMQ_PASS"),
                "RABBITMQ_VHOST": os.environ.get("RABBITMQ_VHOST")
            }
            
            missing_vars = [var for var, value in required_vars.items() if not value]
            if missing_vars:
                raise RuntimeError(
                    f"RabbitMQ not configured. Missing required environment variables: {', '.join(missing_vars)}"
                )
            
            host = required_vars["RABBITMQ_HOST"]
            port = int(required_vars["RABBITMQ_PORT"])
            username = required_vars["RABBITMQ_USER"]
            password = required_vars["RABBITMQ_PASS"]
            vhost = required_vars["RABBITMQ_VHOST"]
        else:
            # Use defaults (used by worker)
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


def publish_job(queue_name: str, job_data: Dict[str, Any], priority: int = 0) -> bool:
    """
    Publish a job to the RabbitMQ queue.
    
    Args:
        queue_name: Name of the queue to publish to
        job_data: Dictionary containing job data (will be JSON serialized)
        priority: Job priority (0-255, higher = more priority)
        
    Returns:
        True if job was published successfully, False otherwise
    """
    connection = get_rabbitmq_connection(require_all_env_vars=True)
    if not connection:
        logger.error("Cannot publish job: RabbitMQ connection failed")
        return False
    
    try:
        channel = connection.channel()
        
        # Declare queue with durability and priority support
        channel.queue_declare(
            queue=queue_name,
            durable=True,  # Queue survives broker restart
            arguments={'x-max-priority': 255}  # Support priority queue
        )
        
        # Publish message
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(job_data),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                priority=priority
            )
        )
        
        logger.info(f"Published job to queue '{queue_name}': {job_data}")
        connection.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to publish job: {str(e)}")
        if connection:
            connection.close()
        return False


def get_queue_info(queue_name: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a queue (message count, consumer count, etc.).
    
    Uses RabbitMQ Management API if available, otherwise falls back to channel method.
    
    Args:
        queue_name: Name of the queue to inspect
        
    Returns:
        Dictionary with queue information or None if failed
    """
    connection = get_rabbitmq_connection(require_all_env_vars=True)
    if not connection:
        return None
    
    try:
        channel = connection.channel()
        
        # Declare queue to ensure it exists
        method = channel.queue_declare(queue=queue_name, durable=True, passive=True)
        
        queue_info = {
            'queue_name': queue_name,
            'message_count': method.method.message_count,
            'consumer_count': method.method.consumer_count
        }
        
        connection.close()
        return queue_info
        
    except Exception as e:
        logger.error(f"Failed to get queue info: {str(e)}")
        if connection:
            connection.close()
        return None


def get_queue_messages(queue_name: str, count: int = 10) -> list:
    """
    Peek at messages in the queue without consuming them.
    
    Note: This uses RabbitMQ Management API. For a simpler approach,
    you can use the Management UI at http://host:15672
    
    Args:
        queue_name: Name of the queue
        count: Maximum number of messages to peek at
        
    Returns:
        List of message previews (limited info without consuming)
    """
    # This is a simplified version - full implementation would use Management API
    # For now, return queue info
    info = get_queue_info(queue_name)
    if info:
        return [{
            'queue_name': queue_name,
            'total_messages': info['message_count'],
            'note': 'Use RabbitMQ Management UI (http://host:15672) to view message details'
        }]
    return []


def consume_jobs(queue_name: str, callback: Callable, auto_ack: bool = False):
    """
    Start consuming jobs from the RabbitMQ queue.
    
    Args:
        queue_name: Name of the queue to consume from
        callback: Function to call for each message
                  Should accept (channel, method, properties, body) parameters
        auto_ack: If True, automatically acknowledge messages (not recommended for reliability)
    """
    connection = get_rabbitmq_connection(require_all_env_vars=False)
    if not connection:
        logger.error("Cannot consume jobs: RabbitMQ connection failed")
        return
    
    channel = None
    
    def signal_handler(signum, frame):
        """Handle SIGTERM by gracefully stopping the consumer."""
        logger.info("Received termination signal, stopping consumer...")
        if channel and not channel.is_closed:
            channel.stop_consuming()
    
    signal.signal(signal.SIGTERM, signal_handler)
    
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
    finally:
        if connection and connection.is_open:
            connection.close()
            logger.info("RabbitMQ connection closed")


def acknowledge_message(channel: pika.channel.Channel, method: pika.spec.Basic.Deliver):
    """
    Acknowledge a message after successful processing.
    
    Args:
        channel: The channel the message was received on
        method: The method frame from the message
    
    Raises:
        Exception: If acknowledgment fails (e.g., channel closed, connection lost)
    """
    try:
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Failed to acknowledge message (delivery_tag={method.delivery_tag}): {str(e)}")
        raise


def reject_message(channel: pika.channel.Channel, method: pika.spec.Basic.Deliver, requeue: bool = True):
    """
    Reject a message (e.g., if processing failed).
    
    Args:
        channel: The channel the message was received on
        method: The method frame from the message
        requeue: If True, message will be requeued; if False, it will be discarded
    
    Raises:
        Exception: If rejection fails (e.g., channel closed, connection lost)
    """
    try:
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=requeue)
    except Exception as e:
        logger.error(f"Failed to reject message (delivery_tag={method.delivery_tag}, requeue={requeue}): {str(e)}")
        raise


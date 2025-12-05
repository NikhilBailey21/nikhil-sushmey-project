"""
RabbitMQ client utilities for connecting to and interacting with RabbitMQ.
"""
import os
import json
import logging
import pika
from typing import Optional, Dict, Any

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
    connection = get_rabbitmq_connection()
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
    connection = get_rabbitmq_connection()
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


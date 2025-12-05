#!/usr/bin/env python3
"""RabbitMQ job consumer worker."""

import json
import logging
import pika
from shared.db import get_db
from ReportMaker import ReportMaker
from shared.rabbitmq_client import consume_jobs, acknowledge_message, reject_message, DEFAULT_QUEUE_NAME

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_job(channel: pika.channel.Channel, method: pika.spec.Basic.Deliver, 
                properties: pika.spec.BasicProperties, body: bytes):
    """
    Process a job from the RabbitMQ queue.
    
    Args:
        channel: The channel the message was received on
        method: The method frame from the message
        properties: Message properties
        body: The message body (JSON string)
    """
    try:
        # Parse the job data
        job_data = json.loads(body.decode('utf-8'))
        
        logger.info("=" * 60)
        logger.info("Received job from queue")
        logger.info(f"Job data: {json.dumps(job_data, indent=2)}")
        logger.info(f"CSV ID: {job_data.get('csv_id')}")
        logger.info(f"Filename: {job_data.get('filename')}")
        logger.info(f"Row count: {job_data.get('row_count')}")
        logger.info(f"User ID: {job_data.get('user_id')}")
        logger.info("=" * 60)
        
        csv_id = job_data.get('csv_id')
        user_id = job_data.get('user_id')
        
        if not csv_id:
            raise ValueError("Missing required field: csv_id")
        if not user_id:
            raise ValueError("Missing required field: user_id")

        # Create ReportMaker VertexAI Object
        try:
            rm = ReportMaker()
            rm.make_report(csv_id=csv_id, user_id=user_id)
        except Exception as e:
            logger.error(f"Failed to create VertexAI object: {e}")
            raise
        
        # Acknowledge the message to remove it from the queue
        try:
            acknowledge_message(channel, method)
            logger.info(f"Job processed and acknowledged for CSV ID: {job_data.get('csv_id')}")
        except Exception as ack_error:
            logger.error(f"Failed to acknowledge message for CSV ID {job_data.get('csv_id')}: {str(ack_error)}", exc_info=True)
            raise  # Re-raise to trigger requeue logic
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse job data as JSON: {str(e)}")
        logger.error(f"Raw body: {body}")
        # Reject the message and don't requeue (malformed message)
        try:
            reject_message(channel, method, requeue=False)
            logger.info("Malformed message rejected and discarded")
        except Exception as reject_error:
            logger.error(f"Failed to reject malformed message: {str(reject_error)}", exc_info=True)
        
    except Exception as e:
        logger.error(f"Error processing job: {str(e)}", exc_info=True)
        # Reject the message and requeue it (temporary failure)
        try:
            reject_message(channel, method, requeue=True)
            logger.info("Job rejected and requeued for retry")
        except Exception as reject_error:
            logger.error(f"Failed to reject/requeue message: {str(reject_error)}", exc_info=True)


if __name__ == "__main__":
    logger.info("Starting RabbitMQ job consumer...")
    logger.info(f"Consuming from queue: {DEFAULT_QUEUE_NAME}")
    logger.info("Waiting for jobs. Press Ctrl+C to stop.")
    
    try:
        consume_jobs(DEFAULT_QUEUE_NAME, callback=process_job, auto_ack=False)
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user")
    except Exception as e:
        logger.error(f"Consumer error: {str(e)}", exc_info=True)


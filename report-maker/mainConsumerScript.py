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
    # Get retry count from message headers, default to 0
    retry_count = 0
    if properties and properties.headers and 'x-retry-count' in properties.headers:
        try:
            retry_count = int(properties.headers['x-retry-count'])
        except (ValueError, TypeError):
            logger.warning(f"Invalid retry count in headers: {properties.headers.get('x-retry-count')}, defaulting to 0")
            retry_count = 0
    
    max_retries = 3
    
    try:
        # Parse the job data
        job_data = json.loads(body.decode('utf-8'))
        
        logger.info("=" * 60)
        logger.info("Received job from queue")
        logger.info(f"Retry count: {retry_count}/{max_retries}")
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
        except RuntimeError as e:
            # Model configuration/permission errors - don't requeue
            logger.error(f"VertexAI configuration error: {e}")
            reject_message(channel, method, requeue=False)
            logger.info("Job rejected and discarded due to configuration error")
            return
        except Exception as e:
            logger.error(f"Failed to create VertexAI object or process report: {e}")
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
        
        # Try to extract CSV ID for logging (might not be available if JSON parsing failed)
        csv_id_for_logging = "unknown"
        try:
            if 'job_data' in locals():
                csv_id_for_logging = job_data.get('csv_id', 'unknown')
            else:
                # Try to parse body to get CSV ID
                temp_data = json.loads(body.decode('utf-8'))
                csv_id_for_logging = temp_data.get('csv_id', 'unknown')
        except Exception:
            pass  # Ignore errors when trying to extract CSV ID
        
        # Check if we've exceeded max retries
        if retry_count >= max_retries:
            logger.error(
                f"Job has failed {retry_count + 1} times (exceeded max retries of {max_retries}). "
                f"Dropping job. CSV ID: {csv_id_for_logging}"
            )
            try:
                reject_message(channel, method, requeue=False)
                logger.info("Job dropped after exceeding max retries")
            except Exception as reject_error:
                logger.error(f"Failed to reject/drop message: {str(reject_error)}", exc_info=True)
        else:
            # Increment retry count and requeue
            new_retry_count = retry_count + 1
            logger.warning(
                f"Job failed (attempt {new_retry_count}/{max_retries}). "
                f"Requeuing with retry count: {new_retry_count}. CSV ID: {csv_id_for_logging}"
            )
            
            # Update message headers with new retry count and republish
            # This ensures the retry count is preserved
            updated_properties = pika.BasicProperties(
                delivery_mode=properties.delivery_mode if properties else 2,
                priority=properties.priority if properties else 0,
                headers=dict(properties.headers) if properties and properties.headers else {}
            )
            updated_properties.headers['x-retry-count'] = new_retry_count
            
            # Republish with updated retry count, then acknowledge original
            # This is atomic: if republish fails, we don't ack, so message stays in queue
            try:
                channel.basic_publish(
                    exchange='',
                    routing_key=method.routing_key,
                    body=body,
                    properties=updated_properties
                )
                # Only acknowledge after successful republish
                acknowledge_message(channel, method)
                logger.info(f"Job republished with retry count {new_retry_count}")
            except Exception as republish_error:
                logger.error(
                    f"Failed to republish message with retry count: {str(republish_error)}. "
                    f"Message will be requeued by RabbitMQ with original retry count.",
                    exc_info=True
                )
                # Reject with requeue - message will come back with original retry count
                # This means the retry count won't increment, but at least the message won't be lost
                try:
                    reject_message(channel, method, requeue=True)
                    logger.warning(
                        "Job rejected and requeued (retry count not incremented due to republish failure). "
                        "This may cause the job to retry more than intended."
                    )
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


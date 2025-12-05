import csv
import logging
import os
from io import StringIO
from flask import Blueprint, render_template, request, jsonify, g
from werkzeug.utils import secure_filename
from shared.db import insert_csv, get_db
from flaskr.auth import login_required
from flask import g
from shared.rabbitmq_client import get_queue_info, publish_job, DEFAULT_QUEUE_NAME
import markdown


bp = Blueprint("transactionAnalyzer", __name__, url_prefix="/analyzer")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@bp.route("/")
@login_required
def index():
    """Transaction Analyzer page - requires login."""
    return render_template("transactionAnalyzer/index.html")


@bp.route("/reports")
@login_required
def reports():
    """Reports page - requires login."""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Query reports for the current user, ordered by most recent first
        cursor.execute(
            'SELECT id, name, report, generatedat FROM reports WHERE userid = %s ORDER BY generatedat DESC',
            (g.user['id'],)
        )
        reports_data = cursor.fetchall()
        cursor.close()
        
        # Convert tuples to dictionaries and render markdown to HTML
        # Tuple: (id, name, report, generatedat)
        reports = []
        for row in reports_data:
            # Render markdown to HTML
            report_html = markdown.markdown(row[2], extensions=['fenced_code', 'tables', 'nl2br'])
            reports.append({
                'id': row[0],
                'name': row[1],
                'report_html': report_html,
                'generatedat': row[3]
            })
        
        return render_template("transactionAnalyzer/reports.html", reports=reports)
    except Exception as e:
        logger.error(f"Error fetching reports: {str(e)}")
        return render_template("transactionAnalyzer/reports.html", reports=[], error=str(e))


@bp.route("/queue/status")
@login_required
def queue_status():
    """Get status of the report generation queue."""
    try:
        queue_info = get_queue_info(DEFAULT_QUEUE_NAME)
        if queue_info:
            return jsonify({
                "success": True,
                "queue": queue_info
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "Failed to connect to RabbitMQ or queue does not exist"
            }), 503
    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/upload", methods=["POST"])
@login_required
def upload_csv():
    if "file" not in request.files:
        logger.error("No file provided.")
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        logger.error("Empty filename.")
        return jsonify({"error": "Empty filename"}), 400

    # Check if the file is a CSV
    if not file.filename.lower().endswith(".csv"):
        logger.error("Invalid file type. Must be CSV.")
        return jsonify({"error": "File must be a CSV"}), 400

    filename = secure_filename(file.filename)

    logger.info(f"Filename uploaded is {filename}")
    try:
        # Read the file content
        csv_text = file.read().decode("utf-8")
        # logger.info(f"csv_text in the file is {csv_text}")
        # Parse the CSV data
        try:
            csv_reader = csv.reader(StringIO(csv_text))
        except Exception as e:
            logger.error(f"Error reading CSV: {str(e)}")
        rows = [row for row in csv_reader]

        if len(rows) == 0:
            logger.error("Empty CSV file.")
            return jsonify({"error": "CSV file is empty"}), 400
        try:
            row_id = insert_csv(filename=filename, csv_content=rows)

            if not row_id or row_id == -1:
                raise ValueError("Error uploading the CSV")

        except Exception as e:
            logger.error(f"CSV upload failed: {e}")
            return jsonify({"error": "Failed to upload CSV"}), 500

        logger.info(f"CSV uploaded and stored with primary key: {row_id}")

        # Fetch user_id
        user_id = -1
        if g.user:
            logger.info(f"User {g.user['username']} id: {g.user['id']} has uploaded a csv")
            user_id = g.user['id']
        else:
            logger.info(f"User not found")
        
        # Create a job in RabbitMQ to process this CSV
        job_data = {
            "csv_id": row_id,
            "filename": filename,
            "row_count": len(rows),
            "user_id": user_id
        }
        
        try:
            job_published = publish_job(DEFAULT_QUEUE_NAME, job_data)
            if job_published:
                logger.info(f"Report generation job added to queue for CSV ID: {row_id}")
            else:
                logger.warning(f"Failed to add job to queue for CSV ID: {row_id}")
        except Exception as e:
            logger.error(f"Error adding job to queue: {str(e)}")
            # Don't fail the upload if queue is unavailable, but log the error
            job_published = False
        
        return jsonify({
            "success": True,
            "id": row_id,
            "rows": len(rows),
            "job_queued": job_published if 'job_published' in locals() else False
        }), 200

    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        return jsonify({"error": "Error processing CSV file."}), 500
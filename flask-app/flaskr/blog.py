import csv
import logging
from flask import Blueprint
from flask import render_template, request, jsonify
from werkzeug.utils import secure_filename
from flaskr.db_functions import insert_csv

import os
import csv
import logging
import pg8000
from dotenv import load_dotenv
from io import StringIO
from flask import Flask, request, jsonify
from sqlalchemy import create_engine, text
from werkzeug.utils import secure_filename
from google.cloud.sql.connector import Connector


bp = Blueprint("blog", __name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@bp.route("/")
def index():
    """Hello World page."""
    return render_template("blog/index.html")


@bp.route("/upload", methods=["POST"])
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
        row_id = insert_csv(filename=filename, csv_content=rows)
        logger.info(f"CSV uploaded and stored with primary key:{row_id}")
        return jsonify({"success": True, "id": row_id, "rows": len(rows)}), 200

    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        return jsonify({"error": "Error processing CSV file."}), 500
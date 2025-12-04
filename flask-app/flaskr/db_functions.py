# db_functions.py
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
import pg8000
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path='../.env')

logger = logging.getLogger(__name__)

# Global engine instance (created once)
_engine = None

from google.cloud.sql.connector import Connector
import pg8000
from sqlalchemy import create_engine
import os

# Global singleton(s)
_engine = None
_connector = None

def get_engine():
    global _engine, _connector

    if _engine is None:
        # Create the Cloud SQL connector
        _connector = Connector()

        def getconn():
            return _connector.connect(
                instance_connection_string=os.getenv("CLOUD_SQL_CONNECTION_NAME"),
                driver="pg8000",
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASS"),
                db=os.getenv("DB_NAME"),
            )

        _engine = create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
        )

        print("✓ Cloud SQL engine created")

    return _engine


def insert_csv(filename: str, csv_content: str) -> int:
    """
    Insert CSV data into the database.
    
    Args:
        filename: Name of the CSV file
        csv_content: Raw CSV text content (as string)
    
    Returns:
        Row ID if successful, -1 if failed
    """
    engine = get_engine()
    
    try:
        with engine.begin() as connection:  # Auto-commits on success
            result = connection.execute(
                text("""
                    INSERT INTO uploaded_csvs (filename, csv_content)
                    VALUES (:filename, :content)
                    RETURNING id
                """),
                {"filename": filename, "content": csv_content}
            )
            row_id = result.scalar()
            
        logger.info(f"✓ CSV inserted with ID: {row_id}")
        return row_id
        
    except Exception as e:
        logger.error(f"✗ Error inserting CSV: {e}")
        return -1


# def get_csv_by_id(csv_id: int) -> dict:
#     """
#     Retrieve a CSV record by ID.
    
#     Returns:
#         Dict with csv data or None if not found
#     """
#     engine = get_engine()
    
#     try:
#         with engine.connect() as connection:
#             result = connection.execute(
#                 text("""
#                     SELECT id, filename, csv_content, uploaded_at
#                     FROM uploaded_csvs
#                     WHERE id = :id
#                 """),
#                 {"id": csv_id}
#             )
#             row = result.fetchone()
            
#             if row:
#                 return {
#                     "id": row[0],
#                     "filename": row[1],
#                     "csv_content": row[2],
#                     "uploaded_at": row[3]
#                 }
#             return None
            
#     except Exception as e:
#         logger.error(f"✗ Error fetching CSV: {e}")
#         return None


# def get_all_csvs() -> list:
#     """
#     Get all CSV records (metadata only, not full content).
    
#     Returns:
#         List of dicts with CSV metadata
#     """
#     engine = get_engine()
    
#     try:
#         with engine.connect() as connection:
#             result = connection.execute(
#                 text("""
#                     SELECT id, filename, uploaded_at
#                     FROM uploaded_csvs
#                     ORDER BY uploaded_at DESC
#                 """)
#             )
#             rows = result.fetchall()
            
#             return [
#                 {
#                     "id": row[0],
#                     "filename": row[1],
#                     "uploaded_at": row[2]
#                 }
#                 for row in rows
#             ]
            
#     except Exception as e:
#         logger.error(f"✗ Error fetching CSVs: {e}")
#         return []


# def delete_csv(csv_id: int) -> bool:
#     """
#     Delete a CSV record by ID.
    
#     Returns:
#         True if successful, False otherwise
#     """
#     engine = get_engine()
    
#     try:
#         with engine.begin() as connection:
#             result = connection.execute(
#                 text("""
#                     DELETE FROM uploaded_csvs
#                     WHERE id = :id
#                 """),
#                 {"id": csv_id}
#             )
            
#         deleted = result.rowcount > 0
#         if deleted:
#             logger.info(f"✓ CSV {csv_id} deleted")
#         else:
#             logger.warning(f"CSV {csv_id} not found")
            
#         return deleted
        
#     except Exception as e:
#         logger.error(f"✗ Error deleting CSV: {e}")
#         return False


# def execute_query(query: str, params: dict = None) -> list:
#     """
#     Execute a custom SELECT query.
    
#     Args:
#         query: SQL query string
#         params: Optional dict of parameters
    
#     Returns:
#         List of result rows
#     """
#     engine = get_engine()
    
#     try:
#         with engine.connect() as connection:
#             result = connection.execute(text(query), params or {})
#             return result.fetchall()
            
#     except Exception as e:
#         logger.error(f"✗ Error executing query: {e}")
#         return []


def close_engine():
    """
    Close the database engine and all connections.
    Call this when shutting down the application.
    """
    global _engine
    if _engine:
        _engine.dispose()
        _engine = None
        logger.info("✓ Database engine closed")
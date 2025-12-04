import os

from flask import g


def get_db():
    """Connect to the application's configured database. The connection
    is unique for each request and will be reused if this is called
    again.
    
    Uses PostgreSQL via pg8000 and Cloud SQL Python Connector.
    Returns raw database connection - use tuples for row access.
    """
    if "db" not in g:
        # Check for Cloud SQL connection
        cloud_sql_connection_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")
        
        if not cloud_sql_connection_name:
            raise RuntimeError(
                "Database not configured. Set CLOUD_SQL_CONNECTION_NAME environment variable."
            )
        
        # Use Cloud SQL Python Connector with pg8000
        from google.cloud.sql.connector import Connector
        import pg8000
        
        # Initialize connector (reuse across requests for better performance)
        if "connector" not in g:
            g.connector = Connector()
        
        connector = g.connector
        
        # Build connection parameters from environment variables
        db_user = os.environ.get("DB_USER")
        db_pass = os.environ.get("DB_PASS")
        db_name = os.environ.get("DB_NAME")
        
        # Validate all required database configuration variables are set
        missing_vars = []
        if not db_user:
            missing_vars.append("DB_USER")
        if not db_pass:
            missing_vars.append("DB_PASS")
        if not db_name:
            missing_vars.append("DB_NAME")
        
        if missing_vars:
            raise RuntimeError(
                f"Database not fully configured. Missing required environment variables: {', '.join(missing_vars)}"
            )
        
        def getconn():
            conn = connector.connect(
                cloud_sql_connection_name,
                "pg8000",
                user=db_user,
                password=db_pass,
                db=db_name,
            )
            return conn
        
        g.db = getconn()

    return g.db


def close_db(e=None):
    """If this request connected to the database, close the
    connection.
    """
    db = g.pop("db", None)

    if db is not None:
        db.close()
    
    # Clean up connector if it exists
    connector = g.pop("connector", None)
    if connector is not None:
        connector.close()


def init_app(app):
    """Register database functions with the Flask app. This is called by
    the application factory.
    """
    app.teardown_appcontext(close_db)

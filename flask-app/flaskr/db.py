import os

import click
from flask import current_app
from flask import g
from flask.cli import with_appcontext


def get_db():
    """Connect to the application's configured database. The connection
    is unique for each request and will be reused if this is called
    again.
    
    Uses PostgreSQL via pg8000 and Cloud SQL Python Connector.
    Returns raw database connection - use tuples for row access.
    """
    if "db" not in g:
        # Check for Cloud SQL connection
        database_url = os.environ.get("DATABASE_URL")
        cloud_sql_connection_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")
        
        if database_url:
            # Direct connection string using pg8000 (for local testing with Cloud SQL proxy)
            import pg8000
            # Parse DATABASE_URL format: postgresql://user:password@host:port/dbname
            from urllib.parse import urlparse
            parsed = urlparse(database_url)
            g.db = pg8000.connect(
                user=parsed.username or "postgres",
                password=parsed.password or "",
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                database=parsed.path.lstrip("/") or "flaskr"
            )
        elif cloud_sql_connection_name:
            # Use Cloud SQL Python Connector with pg8000
            from google.cloud.sql.connector import Connector
            import pg8000
            
            # Initialize connector (reuse across requests for better performance)
            if "connector" not in g:
                g.connector = Connector()
            
            connector = g.connector
            
            # Build connection parameters from environment variables
            db_user = os.environ.get("DB_USER", "postgres")
            db_pass = os.environ.get("DB_PASS")
            db_name = os.environ.get("DB_NAME", "flaskr")
            
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
        else:
            raise RuntimeError(
                "Database not configured. Set either DATABASE_URL or CLOUD_SQL_CONNECTION_NAME environment variable."
            )

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


def init_db(drop_existing=False):
    """Create new tables. If drop_existing is True, drop existing tables first.
    
    Args:
        drop_existing: If True, drop existing tables before creating. 
                      Default False for production safety.
    """
    db = get_db()
    cursor = db.cursor()
    
    if drop_existing:
        try:
            cursor.execute('DROP TABLE IF EXISTS "user" CASCADE')
            print("Dropped existing 'user' table (if it existed)")
        except Exception as error:
            print(f"Error dropping table: {error}")
            print(f"Full error details: {repr(error)}")
            raise
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "user" (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE,
                google_id VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255),
                picture TEXT,
                created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("Created 'user' table (if it didn't exist)")
    except Exception as error:
        print(f"Error creating table: {error}")
        print(f"Full error details: {repr(error)}")
        raise
    
    db.commit()
    cursor.close()


@click.command("init-db")
@click.option("--drop-existing", is_flag=True, default=False,
              help="Drop existing tables before creating new ones (use with caution!)")
@with_appcontext
def init_db_command(drop_existing):
    """Create database tables. Safe for production - only creates if they don't exist.
    
    Use --drop-existing flag to drop tables first (development/testing only).
    """
    init_db(drop_existing=drop_existing)
    if drop_existing:
        click.echo("Dropped and recreated database tables.")
    else:
        click.echo("Initialized the database (tables created if they didn't exist).")


def init_app(app):
    """Register database functions with the Flask app. This is called by
    the application factory.
    """
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

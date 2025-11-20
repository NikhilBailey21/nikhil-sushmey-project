import os
import sqlite3

import click
from flask import current_app
from flask import g
from flask.cli import with_appcontext


def get_db():
    """Connect to the application's configured database. The connection
    is unique for each request and will be reused if this is called
    again.
    
    Supports both SQLite (local development) and PostgreSQL (Cloud SQL).
    """
    if "db" not in g:
        # Check if we should use Cloud SQL (PostgreSQL)
        database_url = os.environ.get("DATABASE_URL")
        cloud_sql_connection_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")
        
        if database_url or cloud_sql_connection_name:
            # Use PostgreSQL (Cloud SQL)
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            if database_url:
                # Direct connection string (for local testing with Cloud SQL proxy)
                g.db = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
            else:
                # Use Cloud SQL Python Connector with psycopg2
                from google.cloud.sql.connector import Connector
                
                # Initialize connector (reuse across requests for better performance)
                if "connector" not in g:
                    g.connector = Connector()
                
                connector = g.connector
                
                # Build connection parameters from environment variables
                db_user = os.environ.get("DB_USER", "postgres")
                db_pass = os.environ.get("DB_PASS")
                db_name = os.environ.get("DB_NAME", "flaskr")
                
                def getconn():
                    # Use the connector to get a connection
                    # The connector.connect() method returns a psycopg2 connection
                    conn = connector.connect(
                        cloud_sql_connection_name,
                        "psycopg2",
                        user=db_user,
                        password=db_pass,
                        db=db_name,
                    )
                    return conn
                
                g.db = getconn()
        else:
            # Use SQLite for local development
            g.db = sqlite3.connect(
                current_app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
            )
            g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    """If this request connected to the database, close the
    connection.
    """
    db = g.pop("db", None)

    if db is not None:
        db.close()
    
    # Note: We don't close the connector here as it can be reused
    # The connector will be cleaned up when the app context is torn down


def is_postgres(db):
    """Check if database connection is PostgreSQL."""
    return hasattr(db, 'cursor') and not isinstance(db, sqlite3.Connection)


def execute_query(db, query, params=None):
    """Execute a query that works with both SQLite and PostgreSQL.
    
    Returns a cursor-like object that has fetchone() and fetchall() methods.
    For PostgreSQL, converts ? placeholders to %s.
    """
    if is_postgres(db):
        # PostgreSQL - use %s placeholders
        if params:
            # Convert ? to %s in query
            query = query.replace('?', '%s')
        # Use RealDictCursor for PostgreSQL to get dict-like rows
        from psycopg2.extras import RealDictCursor
        cursor = db.cursor(cursor_factory=RealDictCursor)
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor
    else:
        # SQLite - use ? placeholders
        if params:
            return db.execute(query, params)
        else:
            return db.execute(query)


def init_db():
    """Clear existing data and create new tables."""
    db = get_db()
    
    # Check if using PostgreSQL
    is_postgres_db = is_postgres(db)
    
    with current_app.open_resource("schema.sql") as f:
        schema = f.read().decode("utf8")
        
        if is_postgres_db:
            # PostgreSQL - execute statements one by one
            # Replace SERIAL with appropriate syntax for PostgreSQL
            cursor = db.cursor()
            statements = [s.strip() for s in schema.split(';') if s.strip() and not s.strip().startswith('--')]
            for statement in statements:
                if statement:
                    cursor.execute(statement)
            db.commit()
            cursor.close()
        else:
            # SQLite - use executescript
            # Replace SERIAL with INTEGER for SQLite
            schema = schema.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
            db.executescript(schema)


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")


def init_app(app):
    """Register database functions with the Flask app. This is called by
    the application factory.
    """
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

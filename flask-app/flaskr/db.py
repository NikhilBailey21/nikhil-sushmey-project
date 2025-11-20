import os
import re
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
                # Use Cloud SQL Python Connector with pg8000 (Google's recommended driver)
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
                    # Use the connector to get a connection with pg8000
                    # pg8000 returns dict-like rows by default, compatible with our code
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


def is_pg8000(db):
    """Check if database connection is pg8000."""
    # Check by module name or by checking for pg8000-specific attributes
    db_type = type(db)
    return (hasattr(db_type, '__module__') and 'pg8000' in str(db_type.__module__)) or \
           hasattr(db, 'run')  # pg8000 has a 'run' method


class Pg8000DictCursor:
    """Wrapper to make pg8000 cursor return dict-like rows."""
    def __init__(self, cursor):
        self._cursor = cursor
        self._columns = None
    
    def execute(self, query, params=None):
        # pg8000 doesn't accept None as params - use empty tuple or no second arg
        if params is None:
            result = self._cursor.execute(query)
        else:
            result = self._cursor.execute(query, params)
        # Get column names from cursor description
        if self._cursor.description:
            self._columns = [desc[0] for desc in self._cursor.description]
        return result
    
    def fetchone(self):
        row = self._cursor.fetchone()
        if row and self._columns:
            return dict(zip(self._columns, row))
        return row
    
    def fetchall(self):
        rows = self._cursor.fetchall()
        if rows and self._columns:
            return [dict(zip(self._columns, row)) for row in rows]
        return rows
    
    def close(self):
        return self._cursor.close()
    
    @property
    def lastrowid(self):
        return getattr(self._cursor, 'lastrowid', None)


def execute_query(db, query, params=None):
    """Execute a query that works with both SQLite and PostgreSQL.
    
    Returns a cursor-like object that has fetchone() and fetchall() methods.
    For PostgreSQL, converts ? placeholders to %s and quotes reserved keywords.
    """
    if is_postgres(db):
        # PostgreSQL - use %s placeholders and quote reserved keywords
        # Quote 'user' table name (reserved keyword in PostgreSQL)
        # Replace 'user' table name with quoted version, but only when it's a table reference
        # Match: FROM user, INTO user, UPDATE user, REFERENCES user, JOIN user
        query = re.sub(r'\bFROM\s+user\b', 'FROM "user"', query, flags=re.IGNORECASE)
        query = re.sub(r'\bINTO\s+user\b', 'INTO "user"', query, flags=re.IGNORECASE)
        query = re.sub(r'\bUPDATE\s+user\b', 'UPDATE "user"', query, flags=re.IGNORECASE)
        query = re.sub(r'\bREFERENCES\s+user\b', 'REFERENCES "user"', query, flags=re.IGNORECASE)
        query = re.sub(r'\bJOIN\s+user\b', 'JOIN "user"', query, flags=re.IGNORECASE)
        
        if params:
            # Convert ? to %s in query
            query = query.replace('?', '%s')
        
        # Check if using pg8000 (Cloud SQL) or psycopg2 (direct connection)
        if is_pg8000(db):
            # pg8000 connection - wrap cursor to return dict-like rows
            cursor = db.cursor()
            wrapped_cursor = Pg8000DictCursor(cursor)
        else:
            # psycopg2 connection (for DATABASE_URL direct connections)
            from psycopg2.extras import RealDictCursor
            wrapped_cursor = db.cursor(cursor_factory=RealDictCursor)
        
        if params:
            wrapped_cursor.execute(query, params)
        else:
            wrapped_cursor.execute(query)
        return wrapped_cursor
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
            # Quote reserved keywords like 'user' for PostgreSQL
            schema = schema.replace('CREATE TABLE user', 'CREATE TABLE "user"')
            schema = schema.replace('DROP TABLE IF EXISTS user', 'DROP TABLE IF EXISTS "user"')
            schema = schema.replace('REFERENCES user (', 'REFERENCES "user" (')
            schema = schema.replace('FROM user WHERE', 'FROM "user" WHERE')
            schema = schema.replace('INTO user (', 'INTO "user" (')
            schema = schema.replace('UPDATE user SET', 'UPDATE "user" SET')
            
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

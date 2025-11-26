#!/usr/bin/env python3
"""Verify database tables exist after initialization."""
import os
from flaskr import create_app
from flaskr.db import get_db

app = create_app()
with app.app_context():
    db = get_db()
    cursor = db.cursor()
    
    # Get current database name
    cursor.execute("SELECT current_database()")
    current_db = cursor.fetchone()[0]
    print(f"Connected to database: {current_db}")
    
    # List all tables in the public schema
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    
    if tables:
        print(f"Found {len(tables)} table(s):")
        for table in tables:
            print(f"  - {table[0]}")
    else:
        print("WARNING: No tables found in the public schema!")
        exit(1)
    
    cursor.close()


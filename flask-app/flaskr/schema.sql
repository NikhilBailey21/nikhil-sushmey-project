-- Initialize the database.
-- Drop any existing data and create empty tables.
-- This schema works for both SQLite (local) and PostgreSQL (Cloud SQL)
-- The application code will convert SERIAL to INTEGER PRIMARY KEY AUTOINCREMENT for SQLite

DROP TABLE IF EXISTS post;
DROP TABLE IF EXISTS user;

CREATE TABLE user (
  id SERIAL PRIMARY KEY,
  username VARCHAR(255) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE,
  google_id VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255),
  picture TEXT,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE post (
  id SERIAL PRIMARY KEY,
  author_id INTEGER NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  title VARCHAR(255) NOT NULL,
  body TEXT NOT NULL,
  FOREIGN KEY (author_id) REFERENCES user (id)
);

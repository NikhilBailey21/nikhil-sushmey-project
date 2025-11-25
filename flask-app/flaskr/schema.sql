-- Initialize the database.
-- Drop any existing data and create empty tables.
-- PostgreSQL schema for Cloud SQL

DROP TABLE IF EXISTS "user";

CREATE TABLE IF NOT EXISTS "user" (
  id SERIAL PRIMARY KEY,
  username VARCHAR(255) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE,
  google_id VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255),
  picture TEXT,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

Flask Transaction Analyzer Application
======================================

A Flask web application with Google OAuth authentication and Cloud SQL (PostgreSQL) database integration.

Features
--------

- **Google OAuth Authentication**: Secure user authentication using Google Sign-In
- **Cloud SQL Integration**: PostgreSQL database hosted on Google Cloud SQL
- **User Management**: User profiles stored in the database with Google account information
- **Transaction Analyzer Functionality**: CSV upload and transaction analysis interface

Installation
------------

**Prerequisites:**

- Python 3.8+
- Google Cloud account with Cloud SQL instance
- Google OAuth 2.0 Client ID

**Setup:**

1. Clone the repository::

    $ git clone <repository-url>
    $ cd nikhil-sushmey-project

2. Navigate to the Flask application::

    $ cd flask-app

3. Create a virtual environment::

    $ python3 -m venv venv
    $ source venv/bin/activate  # On Windows: venv\Scripts\activate

4. Install dependencies::

    $ pip install -r requirements.txt

5. Set up environment variables::

    $ cp .example.env .env
    $ # Edit .env with your actual values

Configuration
-------------

Create a ``.env`` file in the ``flask-app`` directory with the following variables:

**Flask Configuration:**
- ``FLASK_APP=flaskr``
- ``FLASK_ENV=development``
- ``SECRET_KEY=<your-secret-key>`` (generate with: ``python -c "import secrets; print(secrets.token_hex(32))"``)

**Google OAuth:**
- ``GOOGLE_CLIENT_ID=<your-google-client-id>.apps.googleusercontent.com``

  To get a Google OAuth Client ID:
  1. Go to https://console.cloud.google.com/apis/credentials
  2. Create a new OAuth 2.0 Client ID
  3. Set application type to "Web application"
  4. Add authorized JavaScript origins: ``http://localhost:5000``
  5. Add authorized redirect URIs: ``http://localhost:5000/auth/google-callback``

**Database Configuration:**
- ``CLOUD_SQL_CONNECTION_NAME=project:region:instance``
- ``DB_USER=postgres``
- ``DB_PASS=<your-database-password>``
- ``DB_NAME=flaskr``

Running Locally
---------------

**1. Authenticate with Google Cloud:**

The Cloud SQL Python Connector requires Google Cloud credentials. Authenticate using::

    $ gcloud auth application-default login

**2. Ensure database is set up:**

The database and tables must be manually created in Cloud SQL with proper access permissions. The application expects the following table structure:

- ``user`` table with columns: id, username, email, google_id, name, picture, created

**3. Run the application:**

    $ flask run

Or using Python directly::

    $ python -m flask run

The application will be available at http://localhost:5000

**Note:** Ensure your Google Cloud project has:
- Cloud SQL Admin API enabled
- Your user account has permissions to connect to the Cloud SQL instance

Testing
-------

Run the test suite::

    $ cd flask-app
    $ pytest tests/ -v

The tests use the same Cloud SQL database configured in your ``.env`` file.

Run with coverage report::

    $ cd flask-app
    $ coverage run -m pytest tests/
    $ coverage report
    $ coverage html  # open htmlcov/index.html in a browser

Project Structure
-----------------

::

    flask-app/
    ├── flaskr/              # Application package
    │   ├── __init__.py     # Application factory
    │   ├── auth.py         # Authentication blueprint (Google OAuth)
    │   ├── transactionAnalyzer.py         # Transaction Analyzer blueprint
    │   ├── db.py           # Database connection and initialization
    │   └── templates/      # Jinja2 templates
    ├── tests/              # Test suite
    ├── requirements.txt    # Python dependencies
    └── .env               # Environment variables (create from .example.env)

Database Schema
---------------

The application uses a PostgreSQL database with the following table:

**user** table:
- ``id`` - Primary key (SERIAL)
- ``username`` - Unique username
- ``email`` - User email address (unique)
- ``google_id`` - Google account ID (unique, required)
- ``name`` - User's display name
- ``picture`` - Profile picture URL
- ``created`` - Account creation timestamp

License
-------

See LICENSE.rst for details.

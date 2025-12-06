# Transaction Analyzer Application

A cloud-native Flask application for analyzing credit card transactions with AI-powered insights. Upload CSV files, track spending patterns, and generate detailed financial reports.

**Live Application**: https://flaskr-app-707268319983.us-central1.run.app

## Architecture Overview

The application consists of three main components:

1. **Web Server** (Flask App) - Handles user authentication, file uploads, and serves the web interface
2. **Worker** (Report Maker) - Processes transaction data and generates AI-powered reports
3. **Message Queue** (RabbitMQ) - Manages asynchronous job processing between server and worker

## Cloud Technologies

This application is built entirely on **Google Cloud Platform (GCP)** using the following services:

**Compute & Serverless**
  - **Cloud Run** - Serverless container platform hosting the Flask web application
    - Auto-scales from 0 to 10 instances based on traffic
    - Handles HTTPS, load balancing, and request routing automatically
    - Configured with Cloud SQL connection for database access

  - **Compute Engine** - Virtual machines for stateful services
    - RabbitMQ VM: Message queue broker with static IP address
    - Worker VM: Long-running container for report generation jobs

**Database**
  - **Cloud SQL (PostgreSQL)** - Fully managed relational database
    - Stores user accounts, uploaded CSV files, and generated reports
    - Connected to Cloud Run via Cloud SQL Proxy
    - Automatic backups and high availability

**AI/ML**
  - **Vertex AI** - Google's unified ML platform
    - Uses Gemini 2.5 Flash model for transaction analysis
    - Converts raw transaction data into structured JSON
    - Generates markdown reports with spending insights and recommendations

**Container & Build Services**
  - **Artifact Registry** - Private Docker container registry
    - Stores built container images for server and worker
    - Images tagged with Git commit SHA for versioning

  - **Cloud Build** - Fully managed build service
    - Builds Docker containers from source code
    - Runs asynchronously to avoid permission issues
    - Integrates with GitHub Actions workflows

**Networking**
  - **VPC Connector** (Optional) - Serverless VPC access
    - Enables Cloud Run to access private resources (RabbitMQ VM)
    - Routes traffic through private network instead of public internet

**Monitoring & Logging**
  - **Cloud Logging** - Centralized log management
    - All container logs automatically forwarded to Cloud Logging
    - Searchable logs with structured metadata

**CI/CD**
  - **GitHub Actions** - Continuous integration and deployment
    - Automated testing, building, and deployment pipelines
    - Separate workflows for server and worker components
    - Deploys on push to `main` or `master` branch

## CI/CD Pipeline

The project uses GitHub Actions for automated deployment. There are two separate workflows that trigger based on file changes:

**Server Deployment Workflow** (`.github/workflows/deploy-server.yml`)
  Triggers on changes to:
    - `flask-app/**` files
    - `.github/workflows/deploy-server.yml`

  Deployment Steps:
    1. **Authentication** - Authenticates to GCP using service account credentials
    2. **Testing** - Runs pytest test suite to verify code quality
    3. **Database Verification** - Confirms Cloud SQL connection and table structure
    4. **Build** - Submits container build to Cloud Build (asynchronous)
    5. **VPC Setup** - Creates or verifies VPC connector if configured
    6. **Deploy** - Deploys container to Cloud Run with:
       - Environment variables from GitHub secrets
       - Cloud SQL connection configuration
       - VPC connector for private networking (if configured)
       - Auto-scaling configuration (0-10 instances)

**Worker Deployment Workflow** (`.github/workflows/deploy-worker.yml`)
  Triggers on changes to:
    - `report-maker/**` files
    - `.github/workflows/deploy-worker.yml`

  Deployment Steps:
    1. **Authentication** - Authenticates to GCP using service account credentials
    2. **Syntax Check** - Validates Python script syntax
    3. **Build** - Builds worker container image via Cloud Build
    4. **VM Management** - Creates or updates Compute Engine VM instance
    5. **Deploy** - Deploys container to VM with:
       - Environment variables for RabbitMQ and database connections
       - Cloud Logging driver for log aggregation
       - Auto-restart policy (`unless-stopped`)
    6. **Graceful Shutdown** - Old worker containers are stopped gracefully
       - SIGTERM signal handling closes RabbitMQ connections immediately
       - Prevents stale consumer registrations in RabbitMQ

## How to Deploy

**Prerequisites:**
  - GitHub repository with Actions enabled
  - Google Cloud Project with billing enabled
  - Service account with required permissions

**Required GitHub Secrets:**

  GCP Configuration:
    - `GCP_PROJECT_ID` - Your Google Cloud project ID
    - `GCP_REGION` - GCP region (e.g., `us-central1`)
    - `GCP_ZONE` - GCP zone (e.g., `us-central1-a`)
    - `GCP_SA_KEY` - Service account JSON key with deployment permissions

  Database (Cloud SQL):
    - `CLOUD_SQL_CONNECTION_NAME` - Format: `project:region:instance`
    - `DB_USER` - Database username
    - `DB_PASS` - Database password
    - `DB_NAME` - Database name

  Authentication:
    - `GOOGLE_CLIENT_ID` - Google OAuth client ID
    - `SECRET_KEY` - Flask secret key for sessions

  Message Queue (RabbitMQ):
    - `RABBITMQ_HOST` - Static IP address of RabbitMQ VM
    - `RABBITMQ_PORT` - Port (default: `5672`)
    - `RABBITMQ_USER` - RabbitMQ username
    - `RABBITMQ_PASS` - RabbitMQ password
    - `RABBITMQ_VHOST` - Virtual host (default: `/`)

  Optional:
    - `VPC_CONNECTOR_NAME` - VPC connector name (if using private networking)
    - `VPC_NETWORK` - VPC network name
    - `VPC_CONNECTOR_REGION` - VPC connector region

**Deployment Process:**

  1. **Initial Setup:**
     - Add all required secrets to GitHub repository (Settings → Secrets and variables → Actions)
     - Ensure service account has these IAM roles:
       - `roles/run.admin` - Cloud Run deployment
       - `roles/compute.admin` - Compute Engine management
       - `roles/cloudsql.client` - Cloud SQL access
       - `roles/artifactregistry.writer` - Container image push
       - `roles/cloudbuild.builds.editor` - Cloud Build access
       - `roles/logging.logWriter` - Cloud Logging access

  2. **Automatic Deployment:**
     - Push changes to `main` or `master` branch
     - GitHub Actions automatically triggers the appropriate workflow:
       - Changes to `flask-app/**` → Server deployment
       - Changes to `report-maker/**` → Worker deployment
     - Workflows run tests, build containers, and deploy to GCP
     - Monitor deployment progress in GitHub Actions tab

  3. **Manual Deployment:**
     - Go to Actions tab in GitHub
     - Select the workflow you want to run
     - Click "Run workflow" button
     - Choose branch and click "Run workflow"

  4. **Verify Deployment:**
     - Server: Visit https://flaskr-app-707268319983.us-central1.run.app
     - Worker: Check VM logs in Cloud Console
     - RabbitMQ: Access management UI at `http://{RABBITMQ_HOST}:15672`

**Deployment Features:**
  - Zero-downtime deployments (new containers start before old ones stop)
  - Automatic rollback on deployment failures
  - Version tracking via Git commit SHA in container tags
  - Graceful shutdown handling (worker closes RabbitMQ connections on SIGTERM)
  - Health checks and automatic restarts

## Project Structure

```
.
├── flask-app/              # Flask web application
│   ├── flaskr/            # Application package
│   │   ├── __init__.py   # Flask app factory
│   │   ├── auth.py       # Google OAuth authentication
│   │   ├── transactionAnalyzer.py  # Transaction upload & analysis
│   │   └── templates/    # HTML templates
│   ├── tests/            # Test suite
│   ├── Dockerfile        # Container image definition
│   └── cloudbuild.yaml   # Cloud Build configuration
│
├── report-maker/          # Worker application
│   ├── mainConsumerScript.py  # RabbitMQ consumer
│   ├── ReportMaker.py    # AI report generation (Vertex AI)
│   ├── Dockerfile        # Container image definition
│   └── cloudbuild.yaml   # Cloud Build configuration
│
├── shared/                # Shared utilities
│   ├── db.py             # Database connection (Cloud SQL)
│   └── rabbitmq_client.py  # RabbitMQ client utilities
│
├── workQueue/            # RabbitMQ deployment config
│   └── docker-compose.yml  # RabbitMQ container setup
│
└── .github/workflows/    # CI/CD pipelines
    ├── deploy-server.yml  # Server deployment workflow
    └── deploy-worker.yml # Worker deployment workflow
```

## Local Development

**Prerequisites:**
  - Python 3.11+
  - Docker and Docker Compose
  - Local PostgreSQL or Cloud SQL Proxy

**Setup:**

  1. Clone the repository
  2. Set up virtual environment:

     ```bash
     cd flask-app
     python -m venv venv
     source venv/bin/activate  # On Windows: venv\Scripts\activate
     pip install -r requirements.txt
     pip install -e .
     ```

  3. Configure environment variables (create `.env` file):

     ```
     FLASK_APP=flaskr
     FLASK_ENV=development
     SECRET_KEY=your-secret-key
     GOOGLE_CLIENT_ID=your-google-client-id
     CLOUD_SQL_CONNECTION_NAME=project:region:instance
     DB_USER=postgres
     DB_PASS=your-password
     DB_NAME=flaskr
     RABBITMQ_HOST=localhost
     RABBITMQ_PORT=5672
     RABBITMQ_USER=admin
     RABBITMQ_PASS=admin
     RABBITMQ_VHOST=/
     ```

  4. Start RabbitMQ locally:

     ```bash
     cd workQueue
     docker-compose up -d
     ```

  5. Run Flask development server:

     ```bash
     cd flask-app
     flask run
     ```

  6. Run worker locally (in separate terminal):

     ```bash
     cd report-maker
     python mainConsumerScript.py
     ```

## Features

- **Secure Authentication** - Google OAuth 2.0 integration
- **CSV Upload** - Drag-and-drop file upload with validation
- **AI-Powered Analysis** - Vertex AI (Gemini) generates insights from transactions
- **Spending Reports** - Detailed markdown reports with:
  - Transaction categorization
  - Spending trends and patterns
  - Budget recommendations
  - Monthly summaries
- **Asynchronous Processing** - RabbitMQ queue for scalable report generation
- **Responsive UI** - Modern, mobile-friendly interface

## License

See LICENSE.rst for details.


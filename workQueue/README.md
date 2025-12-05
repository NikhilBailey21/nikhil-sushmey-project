# RabbitMQ Work Queue Setup

## Overview

RabbitMQ is deployed to a Compute Engine VM instance with a **static IP address** to ensure consistent connectivity. The configuration is managed through GitHub secrets and automatically passed to Cloud Run services.

## Architecture

- **RabbitMQ**: Deployed on Compute Engine VM (stateful, persistent)
- **Static IP**: Reserved to prevent IP changes
- **Configuration**: Managed via GitHub secrets
- **Services**: Flask app and worker connect via environment variables

## GitHub Secrets Required

After deploying RabbitMQ for the first time, add these secrets to your GitHub repository:

1. **RABBITMQ_HOST** - The static IP address of the RabbitMQ VM (output from deployment)
2. **RABBITMQ_PORT** - Port number (default: 5672)
3. **RABBITMQ_USER** - Username (default: admin)
4. **RABBITMQ_PASS** - Password (default: admin)
5. **RABBITMQ_VHOST** - Virtual host (default: /)

## Deployment Process

1. **First Deployment**: 
   - The workflow reserves a static IP address
   - Creates the VM with the static IP
   - Outputs the IP address in the workflow logs
   - **Action Required**: Copy the IP address and add it to `RABBITMQ_HOST` secret

2. **Subsequent Deployments**:
   - Uses the existing static IP
   - Updates the RabbitMQ container
   - Cloud Run services automatically get the latest config from secrets

## Accessing RabbitMQ

- **AMQP Port**: `{RABBITMQ_HOST}:5672`
- **Management UI**: `http://{RABBITMQ_HOST}:15672`
- **Credentials**: Use the values from GitHub secrets

## Environment Variables in Cloud Run

The following environment variables are automatically set in Cloud Run services (if secrets are configured):

- `RABBITMQ_HOST`
- `RABBITMQ_PORT`
- `RABBITMQ_USER`
- `RABBITMQ_PASS`
- `RABBITMQ_VHOST`

## Local Development

For local development, use the `.env` file in `flask-app/`:

```bash
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=admin
RABBITMQ_PASS=admin
RABBITMQ_VHOST=/
```

Run RabbitMQ locally using docker-compose:

```bash
cd workQueue
docker-compose up -d
```

## Monitoring

- **Queue Status Endpoint**: `GET /analyzer/queue/status` (requires authentication)
- **Management UI**: Access via browser at `http://{RABBITMQ_HOST}:15672`

## Important Notes

⚠️ **Static IP**: The static IP is reserved in the same region as your VM. If you delete the VM, the IP remains reserved (you'll be charged for it until you delete the reservation).

⚠️ **Credentials**: Change default credentials in production by updating the GitHub secrets.

⚠️ **Firewall**: The workflow automatically creates firewall rules for ports 5672 and 15672. Ensure your VPC network allows these connections.


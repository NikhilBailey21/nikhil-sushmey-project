# Use official RabbitMQ image
FROM rabbitmq:3-management-alpine

# Expose ports
# 5672: AMQP protocol port
# 15672: Management UI port
EXPOSE 5672 15672

# Set environment variables for RabbitMQ
ENV RABBITMQ_DEFAULT_USER=admin
ENV RABBITMQ_DEFAULT_PASS=admin

# Enable management plugin
RUN rabbitmq-plugins enable rabbitmq_management

# Persist data to volume
VOLUME ["/var/lib/rabbitmq"]


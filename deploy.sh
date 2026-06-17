#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=== Starting AI Outreach Platform Deployment ==="

# Check if .env file exists
if [ ! -f .env ]; then
  echo "Error: .env file is missing! Please create one with your production secrets."
  exit 1
fi

# Export domain name for Caddy
if grep -q "DOMAIN_NAME" .env; then
  export $(grep DOMAIN_NAME .env | xargs)
  echo "Deploying for Domain: $DOMAIN_NAME"
else
  echo "Error: DOMAIN_NAME is not set in your .env file."
  exit 1
fi

# Pull latest changes from the repository (if initialized as a git repo)
if [ -d .git ]; then
  echo "Pulling latest changes from Git..."
  git pull origin main
else
  echo "Warning: Not a git repository, skipping git pull."
fi

echo "Building production Docker containers..."
docker compose -f docker-compose.prod.yml build

echo "Starting deployment stack..."
docker compose -f docker-compose.prod.yml up -d --remove-orphans

echo "Pruning unused Docker images and builders to save disk space..."
docker image prune -f

echo "=== Deployment Completed Successfully ==="
echo "Checking service status:"
docker compose -f docker-compose.prod.yml ps

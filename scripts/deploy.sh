#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}          # dev | staging | prod
PROJECT_NAME=${2:-broker}      # project name

echo "🚀 Deploying ${PROJECT_NAME} to ${ENVIRONMENT}..."

# backend/deploy.py handles the full deployment:
#   1. Prerequisite checks (Docker, Terraform, Node, AWS CLI)
#   2. Lambda packaging (uv run package_docker.py)
#   3. Terraform init (with S3 backend bootstrap) + apply
#      - Uses backend key: terraform/${ENVIRONMENT}/terraform.tfstate
#      - Uses prod.tfvars for prod environment
#   4. NextJS frontend build with production API URL
#   5. S3 upload + CloudFront cache invalidation
#
# This script delegates everything to backend/deploy.py to avoid
# conflicting Terraform backend initializations.

cd "$(dirname "$0")/.."

echo "📦 Running full deployment..."
(cd backend && ENVIRONMENT="${ENVIRONMENT}" PROJECT_NAME="${PROJECT_NAME}" uv run deploy.py "${ENVIRONMENT}")

echo "✅ Deployment complete!"

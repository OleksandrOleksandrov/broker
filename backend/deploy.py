#!/usr/bin/env python3
"""
Deploy the Broker AI frontend and API infrastructure.
This script:
1. Packages the Lambda function
2. Deploys infrastructure with Terraform to get API URL
3. Builds the NextJS frontend with production API URL
4. Uploads frontend files to S3
5. Invalidates CloudFront cache
"""

import subprocess
import sys
import os
import json
import time
import shutil
from pathlib import Path

# On Windows, npm/node are .cmd files and need shell=True to be found
IS_WINDOWS = sys.platform == "win32"


def run_command(cmd, cwd=None, check=True, capture_output=False, env=None):
    """Run a command and optionally capture output."""
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")

    if capture_output:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=isinstance(cmd, str),
            env=env,
        )
        if check and result.returncode != 0:
            print(f"Error: {result.stderr}")
            sys.exit(1)
        return result.stdout.strip()
    else:
        result = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), env=env)
        if check and result.returncode != 0:
            sys.exit(1)
        return None


def check_prerequisites():
    """Check that all required tools are installed."""
    print("🔍 Checking prerequisites...")

    # Check for required tools
    tools = {
        "docker": "Docker is required for Lambda packaging",
        "terraform": "Terraform is required for infrastructure deployment",
        "npm": "npm is required for building the frontend",
        "aws": "AWS CLI is required for S3 sync and CloudFront invalidation",
    }

    for tool, message in tools.items():
        try:
            use_shell = IS_WINDOWS and tool == "npm"
            if use_shell:
                run_command(f"{tool} --version", capture_output=True)
            else:
                run_command([tool, "--version"], capture_output=True)
            print(f"  ✅ {tool} is installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"  ❌ {message}")
            sys.exit(1)

    # Check if Docker is running
    try:
        run_command(["docker", "info"], capture_output=True)
        print("  ✅ Docker is running")
    except subprocess.CalledProcessError:
        print("  ❌ Docker is not running. Please start Docker Desktop.")
        sys.exit(1)

    # Check AWS credentials
    try:
        run_command(["aws", "sts", "get-caller-identity"], capture_output=True)
        print("  ✅ AWS credentials configured")
    except subprocess.CalledProcessError:
        print("  ❌ AWS credentials not configured. Run 'aws configure'")
        sys.exit(1)


def package_lambda():
    """Package the Lambda function using Docker."""
    print("\n📦 Packaging Lambda function...")

    api_dir = Path(__file__).parent.parent / "backend" / "api"

    if not api_dir.exists():
        print(f"  ❌ API directory not found: {api_dir}")
        sys.exit(1)

    # Run the packaging script
    run_command(["uv", "run", "package_docker.py"], cwd=api_dir)

    # Verify the package was created
    lambda_zip = api_dir / "api_lambda.zip"
    if not lambda_zip.exists():
        print(f"  ❌ Lambda package not created: {lambda_zip}")
        sys.exit(1)

    size_mb = lambda_zip.stat().st_size / (1024 * 1024)
    print(f"  ✅ Lambda package created: {lambda_zip} ({size_mb:.2f} MB)")

    # Copy to the location expected by Terraform
    backend_dir = Path(__file__).parent.parent / "backend"
    terraform_zip = backend_dir / "lambda-deployment.zip"
    shutil.copy2(lambda_zip, terraform_zip)
    print(f"  ✅ Copied to: {terraform_zip} ({size_mb:.2f} MB)")


def build_frontend(api_url=None):
    """Build the NextJS frontend."""
    print("\n🎨 Building frontend...")

    frontend_dir = Path(__file__).parent.parent / "frontend"

    if not frontend_dir.exists():
        print(f"  ❌ Frontend directory not found: {frontend_dir}")
        sys.exit(1)

    # Install dependencies if needed
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        print("  Installing dependencies...")
        run_command(
            "npm install" if IS_WINDOWS else ["npm", "install"], cwd=frontend_dir
        )

    # If API URL is provided, create .env.production.local to override .env.local
    if api_url:
        print(f"  Creating .env.production.local with API URL: {api_url}")
        env_prod_local = frontend_dir / ".env.production.local"

        # Copy from .env.production as base
        env_prod = frontend_dir / ".env.production"
        if env_prod.exists():
            with open(env_prod, "r") as f:
                lines = f.readlines()
        else:
            # Fallback to .env.local if .env.production doesn't exist
            env_local = frontend_dir / ".env.local"
            if env_local.exists():
                with open(env_local, "r") as f:
                    lines = f.readlines()
            else:
                lines = []

        # Update the API URL
        api_line_found = False
        for i, line in enumerate(lines):
            if line.startswith("NEXT_PUBLIC_API_URL="):
                lines[i] = f"NEXT_PUBLIC_API_URL={api_url}\n"
                api_line_found = True
                break

        if not api_line_found:
            lines.append(f"\nNEXT_PUBLIC_API_URL={api_url}\n")

        # Write to .env.production.local (highest priority for production builds)
        with open(env_prod_local, "w") as f:
            f.writelines(lines)
        print("  ✅ Created .env.production.local with API URL")

    # Build the frontend - NextJS will automatically use .env.production for production builds
    print("  Building NextJS app for production...")
    # Set NODE_ENV to production to ensure .env.production is used
    build_env = os.environ.copy()
    build_env["NODE_ENV"] = "production"
    run_command(
        "npm run build" if IS_WINDOWS else ["npm", "run", "build"],
        cwd=frontend_dir,
        env=build_env,
    )

    # Verify the build
    out_dir = frontend_dir / "out"
    if not out_dir.exists():
        print(f"  ❌ Build output not found: {out_dir}")
        print("  Make sure next.config.ts has output: 'export'")
        sys.exit(1)

    print(f"  ✅ Frontend built successfully")


def deploy_terraform(environment: str = "dev"):
    """Deploy infrastructure with Terraform."""
    print(f"\n🏗️  Deploying infrastructure with Terraform ({environment})...")

    terraform_dir = Path(__file__).parent.parent / "terraform"

    if not terraform_dir.exists():
        print(f"  ❌ Terraform directory not found: {terraform_dir}")
        sys.exit(1)

    # Get AWS account and region for backend configuration
    account_id = run_command(
        ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
        capture_output=True,
    )
    region = os.environ.get("AWS_DEFAULT_REGION") or run_command(
        ["aws", "configure", "get", "region"],
        capture_output=True,
    )

    # Backend configuration values (environment-aware backend key)
    backend_bucket = f"broker-terraform-state-{account_id}"
    backend_key = f"terraform/{environment}/terraform.tfstate"
    backend_table = "broker-terraform-locks"

    backend_configs = [
        f"-backend-config=bucket={backend_bucket}",
        f"-backend-config=key={backend_key}",
        f"-backend-config=region={region}",
        f"-backend-config=dynamodb_table={backend_table}",
        "-backend-config=encrypt=true",
    ]

    # Remove old .terraform to force clean init
    terraform_meta = terraform_dir / ".terraform"
    if terraform_meta.exists():
        print("  Removing old Terraform metadata for backend reconfiguration...")
        shutil.rmtree(terraform_meta)

    # Step 1: Try initializing with S3 backend
    print(f"  Attempting S3 backend init (bucket={backend_bucket})...")
    init_result = subprocess.run(
        ["terraform", "init"] + backend_configs,
        cwd=terraform_dir,
        capture_output=True,
        text=True,
    )

    if init_result.returncode != 0:
        if "does not exist" in init_result.stderr:
            print(f"  ⚠️  Backend bucket does not exist yet. Bootstrapping...")

            # Step 2: Initialize with local backend to create bootstrap resources
            print("  Initializing with local backend to create state bucket...")
            backend_tf = terraform_dir / "backend.tf"
            backend_tf_backup = terraform_dir / "backend.tf.bak"
            # Clean up any leftover backup from a previously interrupted run
            if backend_tf_backup.exists():
                backend_tf_backup.unlink()
            if backend_tf.exists():
                backend_tf.rename(backend_tf_backup)
            try:
                run_command(["terraform", "init"], cwd=terraform_dir)
                # Keep the backend block out of the configuration while the
                # bootstrap resources are created with the local state.
                print("  Creating Terraform state bucket and lock table...")
                run_command(
                    [
                        "terraform",
                        "apply",
                        "-auto-approve",
                        "-target=aws_s3_bucket.terraform_state",
                        "-target=aws_dynamodb_table.terraform_locks",
                    ],
                    cwd=terraform_dir,
                )
            finally:
                if backend_tf_backup.exists():
                    backend_tf_backup.rename(backend_tf)
            # Step 4: Reinitialize with S3 backend and migrate state
            print("  Migrating state to S3 backend...")
            shutil.rmtree(terraform_meta)
            run_command(
                ["terraform", "init", "-migrate-state", "-force-copy"] + backend_configs,
                cwd=terraform_dir,
            )
        else:
            print(f"  ❌ Terraform init failed:\n{init_result.stderr}")
            sys.exit(1)
    else:
        print("  ✅ S3 backend initialized successfully")

    # Adopt resources that may have been created by an earlier deployment.
    # This keeps redeployments from failing when the remote state was replaced
    # or is being initialized for the first time.
    import_existing_resources(terraform_dir, environment)

    # Build terraform plan/apply args based on environment
    terraform_args = []
    if environment == "prod":
        terraform_args = ["-var-file=prod.tfvars", "-var=environment=prod"]
    elif environment != "dev":
        terraform_args = ["-var=environment=" + environment, "-var=project_name=" + os.environ.get("PROJECT_NAME", "broker")]

    # Plan the deployment
    print("  Planning deployment...")
    run_command(["terraform", "plan"] + terraform_args, cwd=terraform_dir)

    # Apply the deployment
    print("\n  Applying deployment...")
    print("  Creating AWS resources...")
    run_command(["terraform", "apply"] + terraform_args + ["-auto-approve"], cwd=terraform_dir)

    # Get outputs
    print("\n  Getting outputs...")
    outputs = run_command(
        ["terraform", "output", "-json"], cwd=terraform_dir, capture_output=True
    )

    return json.loads(outputs)


def import_existing_resources(terraform_dir: Path, environment: str):
    """Import known environment resources when they are not in Terraform state."""
    project_name = os.environ.get("PROJECT_NAME", "broker")
    name_prefix = f"{project_name}-{environment}"
    resources = {
        "aws_s3_bucket.memory": f"{name_prefix}-memory-{get_aws_account_id()}",
        "aws_s3_bucket.frontend": f"{name_prefix}-frontend-{get_aws_account_id()}",
        "aws_iam_role.lambda_role": f"{name_prefix}-lambda-role",
        "aws_lambda_function.api": f"{name_prefix}-api",
        "aws_lambda_permission.api_gw": (
            f"{name_prefix}-api/AllowExecutionFromAPIGateway"
        ),
    }

    state_result = subprocess.run(
        ["terraform", "state", "list"],
        cwd=terraform_dir,
        capture_output=True,
        text=True,
    )
    if state_result.returncode != 0:
        print(f"  ❌ Unable to inspect Terraform state:\n{state_result.stderr}")
        sys.exit(1)

    managed_resources = set(state_result.stdout.splitlines())
    for address, resource_id in resources.items():
        if address in managed_resources:
            continue

        print(f"  Checking whether existing resource can be adopted: {address}")
        import_result = subprocess.run(
            ["terraform", "import", address, resource_id],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
        )
        if import_result.returncode == 0:
            print(f"  ✅ Imported {address}")
            continue

        if "Cannot import non-existent remote object" in import_result.stderr:
            print(f"  Resource {address} does not exist; Terraform will create it.")
            continue

        print(f"  ❌ Failed to import {address}:\n{import_result.stderr}")
        sys.exit(1)


def get_aws_account_id() -> str:
    """Return the account ID used in environment resource names."""
    return run_command(
        [
            "aws",
            "sts",
            "get-caller-identity",
            "--query",
            "Account",
            "--output",
            "text",
        ],
        capture_output=True,
    )


def upload_frontend(bucket_name, cloudfront_id):
    """Upload frontend files to S3."""
    print(f"\n📤 Uploading frontend to S3 bucket: {bucket_name}")

    frontend_dir = Path(__file__).parent.parent / "frontend" / "out"

    if not frontend_dir.exists():
        print(f"  ❌ Frontend build not found: {frontend_dir}")
        sys.exit(1)

    # First, clear the bucket
    print("  Clearing S3 bucket...")
    run_command(["aws", "s3", "rm", f"s3://{bucket_name}/", "--recursive"])

    # Upload all files — AWS S3 sync auto-detects content types from extensions
    print("  Uploading all files...")
    run_command(
        [
            "aws",
            "s3",
            "sync",
            str(frontend_dir) + "/",
            f"s3://{bucket_name}/",
            "--delete",
            "--cache-control",
            "max-age=31536000,public",
        ]
    )

    # Override HTML files with correct content-type and no-cache header
    print("  Setting no-cache headers on HTML files...")
    html_files = list(frontend_dir.rglob("*.html"))
    for html_file in html_files:
        rel_path = html_file.relative_to(frontend_dir)
        run_command(
            [
                "aws",
                "s3",
                "cp",
                str(html_file),
                f"s3://{bucket_name}/{rel_path.as_posix()}",
                "--content-type",
                "text/html",
                "--cache-control",
                "max-age=0,no-cache,no-store,must-revalidate",
            ]
        )

    print(f"  ✅ Frontend uploaded successfully")

    # Invalidate CloudFront cache
    print(f"\n🔄 Invalidating CloudFront cache...")
    run_command(
        [
            "aws",
            "cloudfront",
            "create-invalidation",
            "--distribution-id",
            cloudfront_id,
            "--paths",
            "/*",
        ],
        capture_output=True,
    )

    print(f"  ✅ CloudFront invalidation created")


def display_deployment_info(outputs):
    """Display deployment information without modifying local env files."""
    print("\n📝 Deployment Information")

    # Extract values from outputs
    api_url = outputs["api_gateway_url"]["value"]
    cloudfront_url = outputs["cloudfront_url"]["value"]
    s3_bucket = outputs["s3_frontend_bucket"]["value"]

    print(f"\n  ✅ Deployment successful!")
    print(f"\n  CloudFront URL: {cloudfront_url}")
    print(f"  API Gateway URL: {api_url}")
    print(f"  S3 Frontend Bucket: {s3_bucket}")
    print(f"\n  Note: Your local .env.local file remains unchanged.")
    print(f"  The production build uses .env.production.local with the AWS API URL.")


def main():
    """Main deployment function."""
    environment = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ENVIRONMENT", "dev")
    print(f"🚀 Broker AI - Frontend Deployment ({environment})")
    print("=" * 50)

    # Check prerequisites
    check_prerequisites()

    # Package Lambda
    package_lambda()

    # Deploy infrastructure first to get the API URL
    outputs = deploy_terraform(environment)

    # Get the API URL from terraform outputs
    api_url = outputs["api_gateway_url"]["value"]

    # Build frontend with the production API URL
    build_frontend(api_url)

    # Get CloudFront distribution ID from terraform outputs
    cloudfront_id = outputs["cloudfront_distribution_id"]["value"]
    cloudfront_url = outputs["cloudfront_url"]["value"]

    # Upload frontend
    bucket_name = outputs["s3_frontend_bucket"]["value"]
    upload_frontend(bucket_name, cloudfront_id)

    # Display deployment info (no longer modifies .env.local)
    display_deployment_info(outputs)

    print("\n" + "=" * 50)
    print("✅ Deployment complete!")
    print(f"\n🌐 Your application is available at:")
    print(f"   {outputs['cloudfront_url']['value']}")
    print(f"\n📊 Monitor your Lambda function at:")
    print(f"   AWS Console > Lambda > {outputs['lambda_function_name']['value']}")
    print("\n⏳ Note: CloudFront distribution may take 5-10 minutes to fully propagate")


if __name__ == "__main__":
    main()

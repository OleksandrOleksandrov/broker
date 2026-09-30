#!/usr/bin/env python3
"""
Package the FastAPI API for Lambda deployment using Docker.
This ensures binary compatibility with Lambda's runtime environment.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a shell command and handle errors."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout


def build_poppler_layer(temp_path, output_path):
    """Build an ARM64 Poppler + Tesseract layer for Lambda.

    Tesseract backs the readability check in ``api.utils.pdf_quality``:
    pytesseract is only a Python wrapper, the OCR engine itself has to ship in
    the layer. It is therefore mandatory, and the build fails loudly if the
    resulting binaries are unusable.

    Two constraints shape the base image:

    * Amazon Linux 2023 - the Lambda runtime - ships neither tesseract nor
      leptonica in its repositories, so ``dnf install tesseract`` cannot work.
      Ubuntu 20.04 has tesseract 4.x with the eng and ukr trained data.
    * Ubuntu 20.04 links against glibc 2.31 while the AL2023 runtime provides
      2.34, so the binaries are forward compatible. Shipping Ubuntu's libc
      into the layer is not: it shadows the runtime's newer libc and breaks
      every other program on the function (coreutils included). The glibc
      family is therefore excluded from the copied libraries and the runtime
      supplies its own.

    The zip is rooted at bin/, lib/ and share/, which Lambda mounts under
    /opt, giving /opt/bin/... to match the ``poppler_path`` variable.
    """
    layer_dir = temp_path / "poppler-layer"
    layer_dir.mkdir()
    dockerfile = layer_dir / "Dockerfile"
    dockerfile.write_text(
        """FROM ubuntu:20.04
RUN set -eux; \\
    export DEBIAN_FRONTEND=noninteractive; \\
    apt-get update -qq; \\
    apt-get install -y -qq --no-install-recommends \\
        poppler-utils tesseract-ocr tesseract-ocr-eng tesseract-ocr-ukr; \\
    rm -rf /var/lib/apt/lists/*; \\
    mkdir -p /opt/poppler/bin /opt/poppler/lib /opt/poppler/share/tessdata; \\
    cp /usr/bin/pdfinfo /usr/bin/pdftoppm /usr/bin/tesseract /opt/poppler/bin/; \\
    for d in /usr/share/tesseract-ocr/*/tessdata; do cp -r "$d"/. /opt/poppler/share/tessdata/; done; \\
    rm -f /opt/poppler/share/tessdata/osd.traineddata; \\
    ldd /opt/poppler/bin/pdfinfo /opt/poppler/bin/pdftoppm /opt/poppler/bin/tesseract \\
        | awk '{for (i = 1; i <= NF; i++) if ($i ~ /^\\//) print $i}' | sort -u \\
        | while read -r lib; do \\
            case "$(basename "$lib")" in \\
                libc.so*|libm.so*|libmvec.so*|libpthread.so*|libdl.so*|librt.so*|ld-linux*|libresolv.so*|libnsl*|libutil.so*|libanl.so*|libcrypt.so*|libBrokenLocale.so*) \\
                    continue ;; \\
            esac; \\
            cp -n "$lib" /opt/poppler/lib/ 2>/dev/null || true; \\
        done; \\
    if ldd /opt/poppler/bin/tesseract | grep -q "not found"; then \\
        echo "MISSING TESSERACT LIBRARIES"; exit 1; fi; \\
    if ls /opt/poppler/lib | grep -qE '^(libc\\.so|libm\\.so|libmvec\\.so|libpthread\\.so|libdl\\.so|librt\\.so|ld-linux|libresolv\\.so|libnsl|libutil\\.so|libanl\\.so|libcrypt\\.so|libBrokenLocale\\.so)'; then \\
        echo "GLIBC LEAKED INTO LAYER - would shadow the runtime libc"; exit 1; fi
# Prove the layer is self-contained by running the copied binaries from their
# final location, and that the trained data tesseract needs is really there.
RUN set -eux; \\
    /opt/poppler/bin/pdfinfo -v; \\
    /opt/poppler/bin/tesseract --version; \\
    TESSDATA_PREFIX=/opt/poppler/share/tessdata /opt/poppler/bin/tesseract --list-langs \\
        | grep -qw eng; \\
    TESSDATA_PREFIX=/opt/poppler/share/tessdata /opt/poppler/bin/tesseract --list-langs \\
        | grep -qw ukr
"""
    )
    print("Building ARM64 Poppler Lambda layer...")
    run_command(
        [
            "docker",
            "build",
            "--platform",
            "linux/arm64",
            "-t",
            "broker-poppler-layer",
            ".",
        ],
        cwd=layer_dir,
    )
    container_name = "broker-poppler-extract"
    run_command(["docker", "rm", "-f", container_name], cwd=layer_dir)
    run_command(
        ["docker", "create", "--name", container_name, "broker-poppler-layer"],
        cwd=layer_dir,
    )
    extract_dir = temp_path / "poppler-extract"
    extract_dir.mkdir()
    run_command(
        ["docker", "cp", f"{container_name}:/opt/poppler/.", str(extract_dir)]
    )
    run_command(["docker", "rm", "-f", container_name])

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(extract_dir):
            for file in files:
                file_path = Path(root) / file
                zipf.write(file_path, file_path.relative_to(extract_dir))
    print(f"Created Poppler layer package: {output_path}")


def main():
    # Get the API directory
    api_dir = Path(__file__).parent.absolute()
    backend_dir = api_dir.parent
    project_root = backend_dir.parent

    print(f"API directory: {api_dir}")
    print(f"Backend directory: {backend_dir}")

    # Check if Docker is running
    try:
        run_command(["docker", "info"])
    except Exception as e:
        print("Error: Docker is not running or not installed")
        print("Please ensure Docker Desktop is running and try again")
        sys.exit(1)

    # Create temp directory for packaging
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        package_dir = temp_path / "package"
        package_dir.mkdir()

        print(f"Packaging in: {package_dir}")

        # Copy API code
        api_package = package_dir / "api"
        shutil.copytree(
            api_dir,
            api_package,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                ".env*",
                ".venv",
                ".git",
                "*.zip",
                "package_docker.py",
                "test_*.py",
            ),
        )

        # Copy lambda_handler.py to root level for Lambda to find it
        shutil.copy2(api_dir / "lambda_handler.py", package_dir / "lambda_handler.py")

        # Copy database package
        database_src = backend_dir / "database" / "src"
        database_dst = package_dir / "src"
        if database_src.exists():
            shutil.copytree(
                database_src,
                database_dst,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            print(f"Copied database package from {database_src}")
        else:
            print(f"Warning: Database package not found at {database_src}")

        # Create requirements.txt from pyproject.toml using uv pip compile.
        # This generates a fully-resolved, pinned list (including transitive
        # dependencies) so that `pip install -r requirements.txt` inside the
        # Docker image installs exactly the versions declared in pyproject.toml.
        requirements_file = package_dir / "requirements.txt"
        pyproject_path = api_dir / "pyproject.toml"
        print(f"Compiling requirements from {pyproject_path} ...")
        compiled = run_command(
            [
                "uv",
                "pip",
                "compile",
                "--no-annotate",
                "--no-strip-markers",
                str(pyproject_path),
            ],
            cwd=api_dir,
        )
        with open(requirements_file, "w") as f:
            f.write(compiled)
        print(f"Wrote {len(compiled.splitlines())} lines to {requirements_file}")

        # Create Dockerfile
        dockerfile_content = """
FROM public.ecr.aws/lambda/python:3.12

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -t /var/task

# Copy application code
COPY . /var/task/

# Set the handler
CMD ["api.main.handler"]
"""

        dockerfile = package_dir / "Dockerfile"
        with open(dockerfile, "w") as f:
            f.write(dockerfile_content)

        # Build the package for the same architecture as the Lambda function
        # and the Poppler layer used by Terraform.
        print("Building Docker image for arm64 architecture...")
        run_command(
            [
                "docker",
                "build",
                "--platform",
                "linux/arm64",
                "-t",
                "broker-api-packager",
                ".",
            ],
            cwd=package_dir,
        )

        # Create container and extract files
        print("Extracting Lambda package...")
        container_name = "broker-api-extract"

        # Remove container if it exists
        run_command(["docker", "rm", "-f", container_name], cwd=package_dir)

        # Create container
        run_command(
            ["docker", "create", "--name", container_name, "broker-api-packager"],
            cwd=package_dir,
        )

        # Extract /var/task contents
        extract_dir = temp_path / "lambda"
        extract_dir.mkdir()

        run_command(["docker", "cp", f"{container_name}:/var/task/.", str(extract_dir)])

        # Clean up container
        run_command(["docker", "rm", "-f", container_name])

        # Create the final zip
        zip_path = api_dir / "api_lambda.zip"
        print(f"Creating zip file: {zip_path}")

        # Files pip copies but Lambda never loads. The 250 MiB ceiling is
        # measured on the UNZIPPED function plus its layers, so dropping the
        # test suites, type stubs and C headers that ride along with every
        # wheel is what keeps the deployable inside the quota. Trimming here
        # rather than in the image also avoids needing findutils, which the
        # Lambda base image does not ship.
        pruned_dirs = {"tests", "__pycache__", "test"}
        pruned_suffixes = (".pyc", ".pyi", ".h", ".so.debug")
        pruned_names = {"RECORD", "INSTALLER"}

        uncompressed_size = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(extract_dir):
                # Skip __pycache__ directories
                dirs[:] = [
                    d
                    for d in dirs
                    if d != "__pycache__" and d not in pruned_dirs
                ]

                for file in files:
                    # Skip .pyc files
                    if file.endswith(".pyc"):
                        continue

                    if file.endswith(pruned_suffixes):
                        continue
                    if file in pruned_names and ".dist-info" in root:
                        continue

                    file_path = Path(root) / file
                    arcname = file_path.relative_to(extract_dir)
                    zipf.write(file_path, arcname)
                    uncompressed_size += file_path.stat().st_size

        layer_path = api_dir / "poppler_layer.zip"
        build_poppler_layer(temp_path, layer_path)

        # Get file size
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        uncompressed_mb = uncompressed_size / (1024 * 1024)
        print(
            f"✅ Lambda package created: {zip_path} "
            f"({size_mb:.2f} MB compressed, {uncompressed_mb:.2f} MB uncompressed)"
        )

        # Lambda caps the UNZIPPED size of the function plus all of its layers,
        # not the size of each artifact. Checking the function on its own is
        # what let a 200 MiB package plus a 68 MiB layer through the build and
        # then fail at deploy time with InvalidParameterValueException.
        layer_uncompressed = sum(
            info.file_size for info in zipfile.ZipFile(layer_path).infolist()
        )
        deployed_size = uncompressed_size + layer_uncompressed
        limit = 250 * 1024 * 1024
        print(
            f"   layer {layer_uncompressed / (1024 * 1024):.2f} MB uncompressed; "
            f"function + layer {deployed_size / (1024 * 1024):.2f} MB "
            f"of {limit / (1024 * 1024):.0f} MB allowed"
        )
        if deployed_size >= limit:
            print(
                "Error: uncompressed function + layer exceeds the 250 MB Lambda "
                "quota. Reduce dependencies or slim the layer before deploying."
            )
            sys.exit(1)

        # Verify the package
        print("\nPackage contents (first 20 files):")
        with zipfile.ZipFile(zip_path, "r") as zipf:
            files = zipf.namelist()[:20]
            for f in files:
                print(f"  - {f}")
            if len(zipf.namelist()) > 20:
                print(f"  ... and {len(zipf.namelist()) - 20} more files")


if __name__ == "__main__":
    main()

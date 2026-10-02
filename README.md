# Broker - Multi-agent SaaS Broker Helper

## 🚀 Deployment Environments

- **🌟 Production**: [https://d3k4ryo482qtfz.cloudfront.net](https://d3k4ryo482qtfz.cloudfront.net)
- **🧪 Staging**: [https://d7olnkgx9sz1v.cloudfront.net](https://d7olnkgx9sz1v.cloudfront.net)
- **🛠️ Development**: [https://d12btaygle265i.cloudfront.net](https://d12btaygle265i.cloudfront.net)

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 15 (Pages Router), React 19, TypeScript, Tailwind CSS v4 |
| **Backend API** | FastAPI, Python 3.14+, uv |
| **AI/ML** | OpenAI API (GPT-4o), SageMaker embeddings, Bedrock Nova Pro |
| **Infrastructure** | AWS (Lambda [arm64], App Runner, CloudFront, S3, API Gateway, SQS, Aurora Serverless v2) |
| **Auth** | Clerk |
| **Deployment** | Terraform, Docker |
| **PDF Processing** | Poppler (`pdfinfo`, `pdftoppm`) + Tesseract OCR packaged as a Lambda Layer |

---

## 📁 Project Structure

```
broker/
├── backend/
│   ├── api/              # FastAPI backend (document parsing, export)
│   │   ├── main.py       # Main FastAPI application
│   │   ├── models/       # Pydantic models
│   │   └── pyproject.toml
│   ├── deploy.py         # Backend deployment script
│   └── ...
├── frontend/
│   ├── pages/            # Next.js pages (Pages Router)
│   ├── components/       # React components
│   ├── lib/              # Shared utilities
│   ├── server.js         # Express server for file upload proxying
│   ├── package.json
│   └── next.config.ts
├── scripts/
│   ├── run_local.py      # Local development launcher (backend + frontend)
│   ├── deploy.sh         # Deployment script
│   └── destroy.py        # Cleanup script
├── terraform/            # Infrastructure as Code
├── .env                  # Environment variables (local)
├── .env.example          # Environment template
└── README.md
```

---

## 🖥️ Running Locally

### Prerequisites

- **Node.js** (18+) and **npm**
- **Python 3.14+** with **uv** package manager
- **Docker Desktop** (required for Lambda packaging, not needed for local dev)
- **Git**

### Option 1: Automated Local Setup (Recommended)

Use the provided script that starts both the FastAPI backend and Next.js frontend together:

```bash
# 1. Copy environment file and fill in your values
cp .env.example .env

# 2. Run the local development launcher
cd scripts
uv run run_local.py
```

> **Note:** The Lambda function and Poppler layer are built for **arm64** architecture. Docker must be running with `linux/arm64` platform support to package the Lambda deployment artifacts.

The script will:
- Check all prerequisites (Node.js, npm, uv)
- Verify environment files exist
- Install backend dependencies (`uv sync` in `backend/api`)
- Install frontend dependencies (`npm install` in `frontend`)
- Start the FastAPI backend at `http://localhost:8000`
- Start the Next.js frontend at `http://localhost:3000`

Services will keep running until you press **Ctrl+C**.

### Option 2: Manual Setup (Separate Processes)

#### 1. Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` with your actual values. Key variables:
- `OPENAI_API_KEY` — required for AI document parsing
- `FRONTEND_URL=http://localhost:3000`
- `BEDROCK_REGION` — AWS region for Bedrock models

Also ensure `frontend/.env.local` is configured with Clerk keys and API URL.

#### 2. Start the Backend

```bash
cd backend/api
uv sync                    # Install Python dependencies
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.

#### 3. Start the Frontend

In a separate terminal:

```bash
cd frontend
npm install                # Install Node.js dependencies
npm run dev                # Start Next.js dev server
```

The frontend will be available at `http://localhost:3000`.

### Option 3: Express Server (File Upload Proxy)

The project includes an Express server (`frontend/server.js`) that proxies file uploads to the FastAPI backend:

```bash
cd frontend
npm install
node server.js
```

This runs on `http://localhost:3000` and requires the FastAPI backend running on `http://localhost:8000`.

---

## 📡 API Endpoints

All endpoints are served by the FastAPI backend at `http://localhost:8000`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/parse-invoice` | Parse invoice PDF with GPT-4o Vision, optional UKT ZED classification |
| POST | `/api/parse-application` | Parse transport application PDF |
| POST | `/api/parse-cmr` | Parse CMR (international transport note) PDF |
| POST | `/api/parse-transport-documents` | Parse invoice + application + CMR together |
| POST | `/api/parse-transport-documents-row` | Parse 3 transport docs, return flat row |
| POST | `/api/export-excel` | Export invoice data to Excel (.xlsx) |
| POST | `/api/compress-pdf` | Compress PDF (reduce size with grayscale/quality/DPI options) |

API documentation is available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

---

## 🔧 Useful Commands

```bash
# Deploy to an environment (dev, staging, prod)
./scripts/deploy.sh dev
./scripts/deploy.sh staging
./scripts/deploy.sh prod

# Run local development (both services)
cd scripts && uv run run_local.py

# Package Lambda + Poppler layer for deployment (requires Docker with arm64 support)
cd backend/api && python package_docker.py

# Destroy all infrastructure (cleanup)
uv run destroy.py
```

### Poppler & Tesseract Layer

PDF processing (`pdfinfo`, `pdftoppm`, `tesseract`) is provided by Poppler/Tesseract, packaged as a **Lambda Layer** built for **arm64** architecture. The layer is created by `backend/api/package_docker.py` using an Amazon Linux base image and is referenced in Terraform. It must be rebuilt whenever the Poppler tooling or layer configuration changes.

**Why Poppler?** The FastAPI backend uses `pdfinfo` and `pdftoppm` (from Poppler) to extract text, metadata, and page images from transport documents (invoices, CMRs, applications) before passing them to GPT-4o Vision for parsing. These binaries are not part of the Python runtime, so they must be bundled as a Lambda Layer. Building the layer with Docker ensures binary compatibility with the Lambda runtime environment.

**Why Tesseract?** Tesseract is the OCR engine behind the PDF quality check (see [PDF Quality Scoring](#-pdf-quality-scoring)) and ships in the same layer. Otsu binarization is implemented in pure NumPy rather than with OpenCV, which would add ~120 MB to the deployment package and push the Lambda function past its size limit.

**Why arm64?** AWS Lambda functions on **arm64** (Graviton2/Graviton3) offer up to **~34% better price-performance** compared to x86_64 for compute-heavy workloads. Since this application performs CPU-intensive PDF parsing and AI inference, running on arm64 significantly reduces per-request cost. The Lambda function, its dependencies, and the Poppler layer are all built for `linux/arm64` to match.

---

## 📊 PDF Quality Scoring

Scanned transport documents (invoices, CMRs, applications) vary wildly in quality. A crisp 300 DPI scan is parsed reliably by a cheap model, while a blurry, noisy or faded fax-quality scan needs the expensive multimodal model. Instead of guessing from image statistics, the backend asks the question that actually matters: **how much text can an OCR engine recover from the page?**

**Why it was made:** AI vision parsing is billed per request and costs far more with an expensive model. Sending every fax-quality scan to the top-tier model was wasteful, while blindly using the cheap model on blurry scans produced failed extractions. The readability check makes the model choice data-driven per document, cutting cost and latency on the majority of clean scans without degrading accuracy on poor ones.

### How it works

`backend/api/utils/pdf_quality.py` renders the page, preprocesses it, runs a Tesseract OCR pass and combines two signals into a 0-100 score:

- **Confidence (70%)** — mean confidence Tesseract reports across the words it found. This is the direct, empirical measure of legibility and it responds to blur, noise, fading and low resolution alike.
- **Volume (30%)** — how much text was recovered at all, so a sharp but nearly blank page does not score as highly readable.

### Model routing

| Score | Model | Env var |
|-------|-------|---------|
| `>= PDF_QUALITY_THRESHOLD` (default 75) | Cheap — `gpt-4o-2024-11-20` | `GPT_CHEAP_MODEL` |
| `< threshold` | Expensive — `GPT_MODEL` | `GPT_MODEL` |

If OCR cannot run at all (pytesseract missing, no Tesseract binary, no usable language data) the document scores 0 and is routed to the expensive model. That is deliberate: OCR is the only signal, so there is nothing to fall back on, and defaulting to the expensive model keeps an unreadable document off the cheap model.

### Performance optimisations

The check runs on every parsed document, so latency matters as much as accuracy:

- **Middle 50% crop** — only the middle 50% vertical band of the page is scored. Invoices and standard forms carry their densest content (tables and line items) in the centre, and dropping the rest halves the pixel volume, cutting image-processing and OCR time by ~50%.
- **Downscale to 1000 px** — Tesseract accuracy plateaus early, so the grayscale image is downscaled before Otsu binarization, avoiding binarize/ink-fraction passes over every pixel of a high-DPI scan (which can exceed 12M pixels at `PDF_DPI=350`).
- **At most 3 pages, sequentially** — a document is consistent across its pages, so only the first three are scored, and pages run one at a time because parallel Tesseract processes thrash the single vCPU. Scoring stops early as soon as a page passes the threshold.
- **Blank-page skip** — if the ink fraction after Otsu binarization is below 0.5%, the Tesseract subprocess is skipped entirely.
- **Overlapped with payload build** — model selection and JPEG encoding are independent, so `select_model_and_payload` runs them concurrently, hiding encoding cost behind OCR cost rather than adding it to the request tail.

Reference constants were calibrated against the sample scans in `pdf_examples/` and their artificially blurred, noised and faded variants.

### Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `PDF_QUALITY_THRESHOLD` | `75` | Minimum score (0-100) to use the cheap model |
| `GPT_CHEAP_MODEL` | `gpt-4o-2024-11-20` | Model for legible documents |
| `GPT_MODEL` | `GPT_MODEL` env value | Model for poor-quality documents |
| `TESSERACT_CMD` | autodetected | Override Tesseract binary path |
| `OCR_LANG` | `eng+ukr` | Languages tried, with fallback to the primary and `eng` |

Scoring runs in `backend/api/utils/parsers.py` and all document routers (`invoice.py`, `application.py`, `cmr.py`) via `select_model_and_payload`. The resulting score, threshold and selected model are logged for every document.

---

## 📝 Environment Files

| File | Purpose |
|------|---------|
| `.env` | Root — backend configuration (AWS, Bedrock, OpenAI, database) |
| `frontend/.env.local` | Frontend — Clerk auth keys and API URL |
| `.env.example` | Template with placeholder values |

---

## 🔍 Debugging

- **Backend logs**: The FastAPI app logs all requests with method, path, status code, and duration
- **API docs**: `http://localhost:8000/docs` — test endpoints interactively
- **Frontend**: Next.js dev mode auto-reloads on changes
- **Environment issues**: Ensure `.env` and `frontend/.env.local` are properly configured before starting services

---

*Last updated: October 2026*

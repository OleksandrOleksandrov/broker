# Broker - Multi-agent SaaS Broker Helper

**Alex** (Agentic Learning Equities eXplainer) is a multi-agent enterprise-grade SaaS financial planning platform. It processes transport documents (invoices, CMRs, transport applications) using AI-powered parsing, and provides portfolio management and financial analysis.

## 🚀 Deployment Environments

- **🌟 Production**: [https://d3k4ryo482qtfz.cloudfront.net](https://d3k4ryo482qtfz.cloudfront.net)
- **🧪 Staging**: [https://d7olnkgx9sz1v.cloudfront.net](https://d7olnkgx9sz1v.cloudfront.net)
- **🛠️ Development**: [https://d12btaygle265i.cloudfront.net](https://d12btaygle265i.cloudfront.net)

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 15 (Pages Router), React 19, TypeScript, Tailwind CSS v4 |
| **Backend API** | FastAPI, Python 3.12+, uv |
| **AI/ML** | OpenAI API (GPT-4o), SageMaker embeddings, Bedrock Nova Pro |
| **Infrastructure** | AWS (Lambda, App Runner, CloudFront, S3, API Gateway, SQS, Aurora Serverless v2) |
| **Auth** | Clerk |
| **Deployment** | Terraform, Docker |

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
- **Python 3.12+** with **uv** package manager
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

# Destroy all infrastructure (cleanup)
uv run destroy.py
```

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

*Last updated: September 2026*

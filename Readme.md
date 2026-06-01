# Enterprise AI - Text to SQL API

## Overview

Enterprise AI is a Text-to-SQL system that converts natural language questions into executable SQLite queries using:

* Schema Retrieval (RAG)
* Chroma Vector Database
* LLM-powered SQL Generation
* SQL Validation
* Automatic Retry Logic
* FastAPI REST API

The system retrieves relevant database schema information, generates SQL queries using an LLM, validates the generated SQL, executes the query, and returns structured results.

SQLite is used for portability; the design is DB-agnostic via connection string and can be swapped to PostgreSQL/MySQL without code changes.

---

## Features

* Natural Language to SQL Conversion
* Schema-aware Retrieval
* SQLite Support
* SQL Validation Layer
* Retry Logic for Invalid SQL
* FastAPI REST Endpoints
* Chroma Vector Store for Schema Search

---

## Project Structure

```text
client_project/
│
├── main.py
├── Dockerfile
├── requirements.txt
├── README.md
├── .env
│
├── Services/
│   ├── response_generator.py
│   ├── prompt_connection.py
│   ├── schema_extractor.py
│   ├── sql_validator.py
│   └── vector_embedding.py
│
├── chromadb/
│
└── enterprise_ai.db
```

---

## Installation

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Environment

Windows:

```bash
venv\Scripts\activate
```

Linux/Mac:

```bash
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file in the project root with these values:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_LLM_MODEL=groq/your-groq-model-name
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHROMA_DB_PATH=chromadb
DATA_PATH=./data
JSON_FILE_PATH=./data/metadata.json
SQL_DB_PATH=./enterprise_ai.db
```

Required values:

* `GROQ_API_KEY` — your Groq API key.
* `GROQ_LLM_MODEL` — the Groq model name to use for generation, for example `groq/gpt-xxx`.
* `EMBED_MODEL` — the embedding model used for Chroma vector creation.
* `CHROMA_DB_PATH` — local Chroma store path.
* `SQL_DB_PATH` — path to the temporary SQLite database file.

Optional values:

* `DATA_PATH` — location for the generated metadata files.
* `JSON_FILE_PATH` — path to the metadata JSON file used by schema retrieval.
* `HF_TOKEN` — optional Hugging Face token if you use HF-hosted embedding models and want faster downloads.

> Note: The `.env` keys must match the config names used by `config.py`. Do not use lowercase names like `chroma_db_path`.
>
> Note: `DATA_PATH` and `SQL_DB_PATH` are used for temporary metadata and SQLite storage. If you connect this application to a permanent database, remove or replace `./data` and `./enterprise_ai.db` from your configuration.
>
> Note: On first run, the service may generate `data/metadata.json` and build the Chroma vector store automatically.

---

## Running the Application

### Recommended (Windows)

```bash
run.bat
```

### Direct Python / Uvicorn

From the project root:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

If you run `python main.py` directly, the app starts on port `8080` by default.

After startup, open the API docs at:

* `http://localhost:8000/docs` when using `run.bat` or `uvicorn main:app --host 0.0.0.0 --port 8000`
* `http://localhost:8080/docs` when using `python main.py`

---

## API Endpoints

### Health Check

```http
GET /health
```

Response:

```json
{
  "status": "healthy"
}
```

---

### Query Endpoint

```http
POST /api/v1/query
```

Request:

```json
{
  "question": "Show unpaid invoices above 5 lakhs"
}
```

Response:

```json
{
  "status": "success",
  "question": "Show unpaid invoices above 5 lakhs",
  "generated_sql": "SELECT * FROM invoices WHERE status='unpaid' AND invoice_amount > 500000;",
  "summary": "Found 12 unpaid invoices totalling ₹48.2L",
  "confidence": 0.95,
  "retry_count": 0,
  "row_count": 12,
  "data": []
}
```

---

## Docker

Build Image:

```bash
docker build -t enterprise-ai .
```

Run Container:

```bash
docker run -p 8000:8000 enterprise-ai
```

---

## Architecture

```text
User Question
      ↓
Schema Retrieval (Chroma)
      ↓
Prompt Builder
      ↓
LLM SQL Generation
      ↓
SQL Validation
      ↓
Retry Logic
      ↓
SQLite Execution
      ↓
Response
```

---

## Example Questions

* Show unpaid invoices
* Show unpaid invoices above 5 lakhs
* Show total invoice amount
* Show customer names and invoice amounts
* Show vendor payments delayed more than 30 days
* Show top 10 invoices by amount

---

## Author

Kuladeep Reddy

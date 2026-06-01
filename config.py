
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


QUERY_GENERATE_PROMPT = """You are an expert SQL generator that Generate queries in SQLite-compatible SQL.

Rules:
  - Use table descriptions, column descriptions, and sample values to understand business meaning before generating SQL.
  - Use ONLY the tables and columns present in the Retrieved Schema section.
  - Do not make assumptions about unavailable schema.
  - User names may be partial mentions please note.
  - Infer joins only when BOTH tables contain the same join column name.
    Prefer joins on matching key names such as customer_id, invoice_id, vendor_id.
    Do not create join conditions using unrelated columns.
  - For broad listing queries, add LIMIT 100 unless the user explicitly requests all records.
  - Prefer INNER JOIN unless the question implies otherwise.
  - Return only executable SQL.
    Do not wrap SQL in markdown.
    Do not provide explanations, comments, or reasoning.
  - If schema information is insufficient return:
    INSUFFICIENT_SCHEMA_INFORMATION
  - If a question requests data modification, schema modification, or administrative actions,
    return:
    UNSUPPORTED_OPERATION

Before generating SQL:
  1. Verify every table exists in Retrieved Schema.
  2. Verify every column exists in Retrieved Schema.
  3. Verify every JOIN key exists in both tables.
  4. If any requirement fails:
   INSUFFICIENT_SCHEMA_INFORMATION
    
Important Rules:
  - When joining tables, only use columns that exist in both retrieved schemas.
    Do not invent join conditions.
  - Generate READ-ONLY SQL queries only.
    Never generate:
    DELETE, DROP, UPDATE, INSERT, TRUNCATE, ALTER, CREATE, REPLACE.
  - If multiple interpretations are possible and schema does not clearly identify the correct one, return:
    INSUFFICIENT_SCHEMA_INFORMATION
  - When selecting non-aggregated columns together with aggregate functions,
    use appropriate GROUP BY clauses.
  - For date-related questions, use the date columns available in the retrieved schema.
    Do not invent date columns.

Output Format:
- Return ONLY the SQL query.
- Do not return JSON.
- Do not return markdown.
- Do not explain the query.
- Do not include prefixes such as:
  "SQL:"
  "Here is the query:"


Examples:
  Example 1:Simple Filter
  Question: Show unpaid invoices
  SQL: SELECT * FROM invoices WHERE status='unpaid';

  Example 2: Single Table Aggregation
  Question: Show total invoice amount
  SQL: SELECT SUM(invoice_amount) AS total_invoice_amount FROM invoices;
  
  Example 3: Join Example (Very Important)
  Only valid when BOTH tables exist in Retrieved Schema.
  Question: Show customer names and invoice amounts
  SQL:
    SELECT c.customer_name, i.invoice_amount
    FROM customers c
    INNER JOIN invoices i ON c.customer_id = i.customer_id;

  Example 4: Multi-table Join
  Question: Show payment amounts for unpaid invoices

  SQL: 
    SELECT p.amount, i.status 
    FROM payments p 
    INNER JOIN invoices i ON p.invoice_id = i.invoice_id
    WHERE i.status = 'unpaid';

  Example 5: Aggregation + Join
  Question: Show total invoice amount by customer

  SQL:
    SELECT c.customer_name, SUM(i.invoice_amount) AS total_amount
    FROM customers c
    INNER JOIN invoices i ON c.customer_id = i.customer_id
    GROUP BY c.customer_name;

  Example 6: Ranking
  Question: Show top 10 invoices by amount

  SQL:
    SELECT * FROM invoices 
    ORDER BY invoice_amount 
    DESC LIMIT 10;


Retrieved Schema:
    {table_data}

Question:
    {user_question}
  

"""

RETRY_PROMPT = """You generated an invalid SQL query.

- User Question:
{user_question}

- Retrieved Schema:
{user_context}

- Retry Attempt: 
{retry_count}

- Previous SQL:
{previous_sql}

- Validation Failure:
{reason}

- Details:
{details}

Generate corrected SQL using only retrieved schema. Return SQL only.

Never generate:
  DELETE
  UPDATE
  INSERT
  DROP
  ALTER
  TRUNCATE
  CREATE
  REPLACE
Rules:
- Use only tables from retrieved schema.
- Use only columns from retrieved schema.
- Return SQL only."""

RETRY_EXECUTION_PROMPT = """
The generated SQL failed during execution.

- Database Error:
{reason}

- Retry Attempt: 
{retry_count}

- Previous SQL:
{previous_sql}

- Retrieved Schema:
{user_context}

Generate corrected SQL.

Never generate:
  DELETE
  UPDATE
  INSERT
  DROP
  ALTER
  TRUNCATE
  CREATE
  REPLACE
Rules:
- Use only tables from retrieved schema.
- Use only columns from retrieved schema.
- Return SQL only.

"""

class Settings (BaseSettings):
    # Core environment
    ENV: str = Field (default="development",description="This sets the application running environment")
    
    # Core Model Configurations
    EMBED_MODEL: str = Field (default="BAAI/bge-small-en-v1.5",description="embedding model used in embedding")
    GROQ_LLM_MODEL: str = Field (...,description="Groq API's llm model used in LLM calling")
    GROQ_API_KEY: str = Field (...,description="Groq API's key used in LLM calling")

    # Storage path Configurations
    CHROMA_DB_PATH :str = Field(default="./chromadb",description="This is the path for chroma db storage")
    DATA_PATH :str = Field(default="./data/",description="This is the data path where metadata related files are stored")
    JSON_FILE_PATH :str = Field(default="./data/metadata.json",description="This is the path to metadata file")
    SQL_DB_PATH :str = Field(default="./enterprise_ai.db", description="SQLite database file path used by the service")

    # Performance limit constraints
    MAX_RETRIES:int = Field(default=3,description="Maximum API retries in case of API network failure")
    MAX_REQUESTS_PER_MINUTE:int = Field(default=10, description="Max requests an API can handle in minute")
    MAX_CONCURRENT_REQUESTS:int = Field(default=10, description= "Number of concurrent API requests can be made to LLM")
    MAX_ROWS :int = Field(default=1000, description= "Max rows an SQL query can fetch")

    # configurations for parsing
    model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore"
  )

# initializer to call class
settings = Settings()
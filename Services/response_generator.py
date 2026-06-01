
import json
import logging
from Services.schema_extractor import SchemaExtractor, metadata_to_text
from Services.vector_embedding import SchemaRetrival
from Services.prompt_connection import LLM_connect
from Services.sql_validator import SQLExecutor
import asyncio

import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from config import *

logger = logging.getLogger(__name__)

class ResponseGenerator:
    def __init__(self):
        logger.info("Initializing ResponseGenerator")
        self.vector_schema = SchemaRetrival()
        self.intial_extractor_sql = SchemaExtractor()
        self.LLM_connect = None
        self.sql_valid = SQLExecutor()
        self.vector_db = self._chroma_db_check()
    

    def _metadata_create(self):
        path = settings.DATA_PATH
        doc_list = []
        logger.info("Creating metadata directory at %s", path)
        os.makedirs(path, exist_ok=True)
        path = settings.JSON_FILE_PATH
        logger.info("Generating metadata JSON at %s", path)
        with self.intial_extractor_sql as sql:
            doc_data_list = []
            table_data = sql.get_all_tables()
            logger.info("Found %s tables in database", len(table_data) if table_data else 0)
            for i in table_data:
                cols = [{"column_name": col[1], 'Format': col[2], "sample_values": sql.get_sample_data(col[1], i[0])} for col in sql.get_column_data(i[0])]
                doc_data = {
                    "table_name": i[0],
                    "columns": cols
                }
                doc_data_list.append(doc_data)
                doc = metadata_to_text(doc_data)
                doc_list.append(doc)

        with open(path, "w", encoding="utf-8") as json_file:
            json.dump(doc_data_list, json_file, indent=4)

        logger.info("Created %s metadata documents", len(doc_list))
        if not doc_list:
            logger.warning("No metadata documents were created; metadata.json is empty. Check the source database for tables.")

        return doc_list

    def _metadata_file_check(self):
        if os.path.exists(settings.JSON_FILE_PATH):
            logger.info("Metadata file found at %s; loading", settings.JSON_FILE_PATH)
            doc_list = []
            with open(settings.JSON_FILE_PATH, "r", encoding="utf-8") as json_data:
                docs_list = json.load(json_data)

            if not docs_list:
                logger.warning("Metadata file %s is empty; regenerating metadata.", settings.JSON_FILE_PATH)
                return self._metadata_create()

            for doc_data in docs_list:
                doc = metadata_to_text(doc_data)
                doc_list.append(doc)
            return doc_list
        else:
            logger.info("Metadata file %s not found; creating metadata.", settings.JSON_FILE_PATH)
            return self._metadata_create()
        
    def _chroma_db_check(self):
        logger.info("Checking chroma DB at %s", settings.CHROMA_DB_PATH)
        doc = None
        if not os.path.exists(settings.CHROMA_DB_PATH):
            logger.info("Chroma DB path missing- rebuilding metadata and vectors")
            doc = self._metadata_file_check()
        if self.vector_schema.db_count_collections() > 0:
            logger.info("Found existing vector store")
            vector_db = self.vector_schema.load_vector_store()
        else:
            logger.info("Building new vector store")
            if not doc:
                doc = self._metadata_file_check()

            if not doc:
                logger.error("No metadata documents available; cannot build vector store")
                raise Exception("No metadata documents available to build vector store")

            vector_db = self.vector_schema.build_vector_store(doc)
        return vector_db
        
    async def llm_check(self, question):
        stream = False
        logger.info("Starting LLM check for question: %s", question)
        user_context, prompt = self.LLM_connect.build_prompt(question)
        query = ""
        if stream:
            for i in self.LLM_connect.llm_connection(prompt, stream=True):
                query += " " + i
        else:
            try:
                chunk = await self.LLM_connect.llm_connection(prompt)
            except Exception:
                logger.exception("LLM invocation failed")
                raise
            query = chunk
            logger.info("Fetched output from LLM: %s", repr(query)[:200])
        return user_context, query

    async def build_retry_prompt(self, question, user_context, query_response, validation_error):
        stream = False
        logger.info("Building retry prompt- retry_error=%s", validation_error)
        prompt = self.LLM_connect.retry_llm(question, user_context, query_response, validation_error)
        query = ""
        if stream:
            for i in self.LLM_connect.llm_connection(prompt, stream=True):
                query += " " + i
        else:
            chunk = await self.LLM_connect.llm_connection(prompt)
            query = chunk
            logger.info("Fetched output from retry LLM: %s", repr(query)[:50])
        return query

    async def valid_rety_cases(self, question, sql, user_context, query_response, retry_count=0):
        validation = None
        # if not query_response or not query_response.strip():
        #     validation = {
        #             "status":"failed",
        #             "reason":"INVALID_QUERY",
        #             "details":"QUERY is not properly generated"
        #     }
        #     retry_count+=1
        #     query_response = await self.build_retry_prompt(
        #         question,
        #         user_context,
        #         query_response,
        #         validation
        #     )
            
        while retry_count < settings.MAX_RETRIES:
            logger.info("Validating SQL attempt %s", retry_count)
            if not query_response or not query_response.strip():
                validation = {
                    "status": "failed",
                    "reason": "INVALID_QUERY",
                    "details": "QUERY is not properly generated"
                }
            else:
                validation = sql._validator(query_response)
            if validation["status"] == "success":
                logger.info("SQL validation succeeded")
                break

            retry_count += 1
            validation.update({"retry_count": retry_count})
            logger.warning("Validation retry %s failed: %s", retry_count, validation.get('reason'))
            query_response = await self.build_retry_prompt(
                question,
                user_context,
                query_response,
                validation,
            )

        if validation is not None and validation["status"] == "failed":
            logger.error("Validation ultimately failed after retries: %s", validation)
            return {
                "status": "failed",
                "reason": "MAX_RETRIES_EXCEEDED",
                "last_error": validation,
                "generated_sql": query_response,
            }

        try:
            data = sql.execute_query(query_response)
            logger.info("SQL executed successfully; rows=%s", len(data) if isinstance(data, list) else 0)
            return {
                "status": "success",
                "generated_sql": query_response,
                "data": data,
                "retry_count": retry_count,
            }
        
        except Exception as e:
            database_error = str(e)
            logger.exception("Execution retry failed- database_error=%s", database_error)
            if retry_count >= settings.MAX_RETRIES:
                return {
                    "status": "failed",
                    "reason": "MAX_RETRIES_EXCEEDED",
                    "last_error": {
                        "status": "failed",
                        "reason": database_error,
                    },
                    "generated_sql": query_response,
                }
            retry_count += 1
            execution_error = {
                "status": "failed",
                "retry_count": retry_count,
                "reason": "database_error",
                "database_error": database_error,
            }
            query_response = await self.build_retry_prompt(
                question,
                user_context,
                query_response,
                execution_error,
            )
            return await self.valid_rety_cases(question, sql, user_context, query_response, retry_count)
        

    async def summarize_results(self, question, sql_query, data, retry_count=0):
        """Call the LLM to produce a one-line summary and a confidence score (0.0-1.0).

        Returns (summary:str, confidence:float)
        """
        if not self.LLM_connect:
            self.LLM_connect = LLM_connect(vector_db=self.vector_db)

        # Prepare a compact sample of the data for the LLM
        try:
            sample = data if isinstance(data, list) else []
            sample = sample[:10]
            sample_str = json.dumps(sample, default=str, ensure_ascii=False)
            if len(sample_str) > 2000:
                sample_str = sample_str[:2000] + "..."
        except Exception:
            sample_str = str(data)

        prompt = (
            "You are an expert assistant that summarizes SQL query results for business users.\n"
            f"User question: {question}\n"
            f"SQL: {sql_query}\n"
            f"Results (sample up to 10 rows): {sample_str}\n"
            "Provide a JSON object only with two keys: 'summary' (one-line human friendly summary) "
            "and 'confidence' (a float between 0.0 and 1.0 indicating how confident you are in the summary)."
        )

        logger.info("Requesting LLM summary for query; rows=%s", len(data) if isinstance(data, list) else 0)
        resp = await self.LLM_connect.llm_connection(prompt)

        # Try to parse JSON from LLM
        summary = None
        confidence = None
        try:
            if isinstance(resp, str):
                # Attempt JSON parse
                parsed = None
                try:
                    parsed = json.loads(resp)
                except Exception:
                    # try to extract JSON substring
                    import re

                    m = re.search(r"\{.*\}", resp, re.DOTALL)
                    if m:
                        try:
                            parsed = json.loads(m.group(0))
                        except Exception:
                            parsed = None

                if isinstance(parsed, dict):
                    summary = parsed.get("summary")
                    confidence = parsed.get("confidence")
                else:
                    # Fallback: take first line as summary, try to find a float
                    first_line = resp.strip().splitlines()[0]
                    summary = first_line.strip()
                    try:
                        # find a float in text
                        import re

                        m = re.search(r"(0(?:\.\d+)?|1(?:\.0+)?)", resp)
                        if m:
                            confidence = float(m.group(0))
                    except Exception:
                        confidence = None
            elif isinstance(resp, dict):
                summary = resp.get("summary")
                confidence = resp.get("confidence")
        except Exception:
            logger.exception("Failed parsing LLM summarization response")

        # Fallback values
        if summary is None:
            row_count = len(data) if isinstance(data, list) else 0
            summary = f"Found {row_count} rows"

        if confidence is None:
            confidence = max(0.0, 1.0 - (retry_count / max(1,settings.MAX_RETRIES)))

        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except Exception:
            confidence = max(0.0, 1.0 - (retry_count / max(1,settings.MAX_RETRIES)))

        logger.info("LLM summary done; summary=%s confidence=%s", summary[:200], confidence)
        return summary, confidence

    async def query_generation(self, question=None):
        logger.info("Starting query generation for question: %s", question)
        try:
            self.LLM_connect = LLM_connect(vector_db=self.vector_db)
            user_context, query_response = await self.llm_check(question)
            validation = None
            with self.sql_valid as sql:
                response = await self.valid_rety_cases(question, sql, user_context, query_response)

                if response["status"] != "success":
                    logger.warning("Query generation returned non-success status: %s", response.get("status"))
                    return response

                data = response["data"]
                query_response = response["generated_sql"]
                retry_count = response.get("retry_count", 0)

            # Call LLM to summarize the returned data (one-line) and provide confidence
            try:
                summary, confidence = await self.summarize_results(question, query_response, data, retry_count)
            except Exception:
                logger.exception("Summarization failed; falling back to heuristic summary")
                summary = None
                confidence = max(0.0, 1.0 - (retry_count / max(1,settings.MAX_RETRIES)))

            return {
                "status": "success",
                "question": question,
                "generated_sql": query_response,
                "row_count": len(data) if isinstance(data, list) else 0,
                "summary": summary,
                "confidence": confidence,
                "retry_count": retry_count,
                "data": data,
            }
        except Exception as e:
            logger.exception("query_generation failed")
            return {
                "status": "error",
                "message": str(e),
            }
    
       
    
            
            
if __name__=="__main__":
    resp = ResponseGenerator()
    question = "Show unpaid invoices above 5 lakhs"
    table_Data = asyncio.run(resp.query_generation(question))
    print(table_Data)

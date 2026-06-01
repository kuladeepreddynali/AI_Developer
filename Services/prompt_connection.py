import os
import json
import asyncio
import logging
import sys

# Ensure project root is on sys.path so local package imports work when running from Services/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_groq import ChatGroq
from langchain_core.prompts import  ChatPromptTemplate

import Services.vector_embedding as ve
from Services.rate_limiter import GeminiRateLimiter

from config import settings,QUERY_GENERATE_PROMPT, RETRY_EXECUTION_PROMPT, RETRY_PROMPT

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# llm_model = os.getenv("llm_model_name")

# google_api = os.getenv("GOOGLE_API_KEY")

# os.environ['GOOGLE_API_KEY'] = google_api
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
os.environ['GROQ_API_KEY'] = settings.GROQ_API_KEY


class LLM_connect:
    def __init__(self,vector_db = None):
        self.llm_model = settings.GROQ_LLM_MODEL
        # self.google_api = google_api
        self.schema_retriever = ve.SchemaRetrival()
        self.vector_db = vector_db or self.schema_retriever.load_vector_store()
        self.rate_limiter = GeminiRateLimiter(
            max_requests_per_minute=settings.MAX_REQUESTS_PER_MINUTE,
            max_concurrent_requests=settings.MAX_CONCURRENT_REQUESTS
        )

    def _build_schema_context(self,user_query):
        final_str = ""
        
        results = self.schema_retriever.invoke(self.vector_db,
        user_query
        )
        for  data in results:
            final_str+='\n----------------------------------\n'+data.page_content
        logger.debug("schema data is %s", final_str)
        return final_str
    
    def retry_llm(self,user_query,user_context,previous_sql,validation_error):
        # user_context = self._build_schema_context(user_query)
        run_prompt = RETRY_PROMPT
        if "database_error" in validation_error:
            run_prompt = RETRY_EXECUTION_PROMPT

        prompt_template = ChatPromptTemplate.from_template (run_prompt)
        prompt_template = prompt_template.format(user_question = user_query,
            user_context = user_context,
            previous_sql = previous_sql,
            retry_count = validation_error.get("retry_count",1),
            reason = validation_error.get("reason"),
            details =  validation_error.get("details"),
        )
        return prompt_template
    
    def build_prompt (self,user_query,prompt = QUERY_GENERATE_PROMPT):
        user_context = self._build_schema_context(user_query)
        
        prompt_template = ChatPromptTemplate.from_template (prompt)
        prompt_template = prompt_template.format(table_data=user_context,user_question=user_query)
        return user_context,prompt_template
    
    def _stream_llm(self, prompt):
        llm = ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model=self.llm_model, temperature=0.1, max_tokens=2048)
        logger.info("_stream_llm started; model=%s", self.llm_model)
        try:
            for chunk in llm.stream(prompt):
                content = getattr(chunk, "content", None)
                if content:
                    logger.info("stream chunk received: %s", repr(content)[:200])
                    yield content
        except Exception:
            logger.exception("Streaming LLM invocation failed")
            raise

    async def _invoke_llm(self, prompt):
        llm = ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model=self.llm_model, temperature=0.1, max_tokens=2048)
        logger.info("_invoke_llm starting; model=%s", self.llm_model)
        try:
            await self.rate_limiter.acquire()

            try:
                data =  await asyncio.to_thread(
                    llm.invoke,
                    prompt
                )
                
            finally:
                self.rate_limiter.release()
            logger.debug("RAW RESPONSE: %s", repr(data.content))
            logger.debug("LENGTH: %s", len(data.content))

            content = getattr(data, "content", data)
            logger.info("invoke response type=%s content_repr=%s", type(data), repr(content)[:200])
            return content
        except Exception:
            logger.exception("LLM invoke failed")
            raise

    async def llm_connection(self, prompt, stream=False):
        
        logger.info("llm_connection called; stream=%s model=%s", stream, self.llm_model)
        if stream:
            return self._stream_llm(prompt)
        return await self._invoke_llm(prompt)

async def _temp_dict():
    user_checkup = [
        "Show unpaid invoices",
        "Show unpaid invoices above 5 lakhs",
        "Show total invoice amount",
        "Show total unpaid invoice amount",
        "Show customer names and invoice amounts",
        "Show payment amounts for unpaid invoices",
        "Show total invoice amount by customer",
        "Show invoices due after 2026-03-01",
        "Show top 10 invoices by amount",
        "Show vendor payments delayed more than 30 days"
    ]
    dict_data = dict()
    for user_query in user_checkup:
        user_context, prompt = llm.build_prompt(user_query)
        query = ""
        # chunk = llm.llm_connection(prompt)
        # print("prev_chunk",chunk)
        # # query = query+" " +chunk[0].get("text","")
        # query  = chunk
        # for chunk in llm.llm_connection(prompt):
        #     query = query + chunk
        #     print(query)
        stream = False
        try:
            if stream:
                for i in llm.llm_connection(prompt,stream=True):
                    print("i is ",i[0],type(i))
                    query +=" " +i[0].get("text","")
                    print(query,i[0].get("text",""))
            else:
                
                chunk = await llm.llm_connection(prompt)

                query  = chunk
                # print("chunk is ",chunk,type(chunk))
                # query = query+" " +chunk[0].get("text","")
                # query  = chunk
                # print(query,chunk[0].get("text",""))
        except Exception as e:
            print(f"exception for {user_query}",e )
            if not query:
                query = f"Exception is {e}"
            if not prompt :
                prompt  = f"issue with prompt for {user_query}"

        dict_data[user_query] = {
            "prompt": prompt,
            "llm_query" : query
        }
        # return dict_data    

    return dict_data

if __name__=="__main__":
    llm = LLM_connect()
    # with open(JSON_FILE_PATH,"r",encoding="utf-8") as json_file:
    #     doc_data_list = json.load( json_file)
    dict_data = asyncio.run(_temp_dict())
    
    print("dict_data",dict_data)

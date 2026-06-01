
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from Services.response_generator import ResponseGenerator
import uvicorn
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    question: str

app = FastAPI(
    title="Enterprise AI Data Assistant",
    description="NLP-to-SQL Platform",
)
generator = ResponseGenerator()

@app.post("/api/v1/query")
async def query_api(query: QueryRequest):
    try:
        response = await generator.query_generation(query.question)
        if not isinstance(response, dict):
            logger.warning("query_generation returned unexpected type %s", type(response))
            return JSONResponse(status_code=500, content={"status": "error", "message": "Invalid response from query generator"})
        return JSONResponse(status_code=200, content=response)
    except Exception as exc:
        logger.exception("Query API failed")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})

@app.get("/health")
def health():
    return {"status":"healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
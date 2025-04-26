import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    logger.info("Received request at /v1/chat/completions")
    try:
        body = await request.json()
        logger.info(f"Request body: {body}")
    except Exception as e:
        logger.error(f"Failed to parse request body: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Translate OpenAI request to Ollama format
    messages = body.get("messages")
    if not messages:
        logger.error("Missing 'messages' field in request body")
        raise HTTPException(status_code=400, detail="Missing 'messages'")
    model = body.get("model", "llama2")
    ollama_payload = {
        "model": model,
        "messages": messages
    }
    logger.info(f"Forwarding to Ollama at {OLLAMA_URL} with payload: {ollama_payload}")

    try:
        async with httpx.AsyncClient() as client:
            ollama_response = await client.post(OLLAMA_URL, json=ollama_payload, timeout=60.0)
        logger.info(f"Ollama responded with status code: {ollama_response.status_code}")
        if ollama_response.status_code != 200:
            logger.error(f"Ollama error: {await ollama_response.text()}")
            raise HTTPException(status_code=500, detail="Ollama backend error")
        ollama_data = ollama_response.json()
        # Translate Ollama response to OpenAI format
        openai_response = {
            "id": ollama_data.get("id", "ollama-proxy"),
            "object": "chat.completion",
            "created": ollama_data.get("created_at", ""),
            "model": ollama_data.get("model", model),
            "choices": [
                {
                    "index": 0,
                    "message": ollama_data.get("message", {}),
                    "finish_reason": "stop"
                }
            ],
            "usage": ollama_data.get("usage", {})
        }
        return JSONResponse(content=openai_response)
    except httpx.RequestError as exc:
        logger.error(f"HTTP error occurred while requesting {exc.request.url!r}: {exc}")
        raise HTTPException(status_code=503, detail=f"Error connecting to Ollama service: {exc}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in the bridge: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error in bridge") 
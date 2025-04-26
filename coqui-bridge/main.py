import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
COQUI_URL = os.getenv("COQUI_URL", "http://coqui_tts:5002/api/tts")

@app.post("/v1/audio/speech")
async def tts_bridge(request: Request):
    logger.info("Received request at /v1/audio/speech")
    try:
        body = await request.json()
        logger.info(f"Request body: {body}")
    except Exception as e:
        logger.error(f"Failed to parse request body: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    text = body.get("input")
    if not text:
        logger.error("Missing 'input' field in request body")
        raise HTTPException(status_code=400, detail="Missing 'input'")

    voice = body.get("voice", "p225") # Example VCTK speaker ID
    model_url = f"{COQUI_URL}"
    logger.info(f"Extracted text: '{text}', requested voice/speaker_id: '{voice}'")

    # Construct query parameters for Coqui API GET request
    params = {
        "text": text,
        "speaker_id": voice,
        "language_id": "en", # Assuming English, adjust if needed
        "style_wav": "" # Include empty style_wav like the UI does
    }
    logger.info(f"Sending GET request to {model_url} with params: {params}")

    try:
        async with httpx.AsyncClient() as client:
            # Send GET request with parameters, increased timeout
            coqui_response = await client.get(model_url, params=params, timeout=60.0)
        logger.info(f"Received response from Coqui TTS with status code: {coqui_response.status_code}")

        if coqui_response.status_code != 200:
            error_detail = "Unknown error"
            try:
                error_detail = await coqui_response.text()
            except Exception:
                pass
            logger.error(f"Coqui TTS error ({coqui_response.status_code}): {error_detail}")
            raise HTTPException(status_code=500, detail=f"Coqui TTS error: {error_detail}")

        # Stream the audio content back
        return StreamingResponse(
            coqui_response.aiter_bytes(),
            media_type="audio/wav"
        )
    except httpx.RequestError as exc:
        logger.error(f"HTTP error occurred while requesting {exc.request.url!r}: {exc}")
        raise HTTPException(status_code=503, detail=f"Error connecting to Coqui TTS service: {exc}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in the bridge: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error in bridge")

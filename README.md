# Ollama Stack

This repository contains a Docker Compose configuration to set up a comprehensive AI stack, including large language models, text-to-speech services, and a web interface.

## Services

The stack includes the following services:

- **`ollama`**: The core Ollama service for running large language models locally. It is configured to use NVIDIA GPUs if available.
  - Port: `11434`
- **`webui`**: The Open WebUI interface for interacting with Ollama models.
  - Port: `8080`
- **`openedai_speech`**: A text-to-speech service compatible with the OpenAI API standard.
  - Port: `8000`
  - Volumes: Uses `./openedai-speech/voices` for voice data and `./openedai-speech/config` for configuration.
- **`coqui_tts`**: The Coqui TTS server for generating speech. Configured to use NVIDIA GPUs if available.
  - Port: `5002`
- **`coqui_bridge`**: A bridge service to make the Coqui TTS API compatible with other services if needed.
  - Port: `8090`

## Prerequisites

- Docker
- Docker Compose
- NVIDIA drivers and NVIDIA Container Toolkit (if using GPU acceleration)

## Getting Started

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd ollama-stack
    ```
2.  **(Optional) Configure Services:**
    - Modify the `docker-compose.yml` file to adjust resource limits (memory, CPU), ports, or environment variables as needed.
    - Place necessary voice models or configuration files in the `openedai-speech` directory if using that service.
3.  **Run the stack:**
    ```bash
    docker-compose up -d
    ```
    This command will download the necessary images and start all the services in the background.
4.  **Access the services:**
    - **Ollama API:** `http://localhost:11434`
    - **WebUI:** `http://localhost:8080`
    - **OpenedAI Speech API:** `http://localhost:8000`
    - **Coqui TTS API (via bridge):** `http://localhost:8090`
    - **Coqui TTS API (direct):** `http://localhost:5002`

## Configuring Text-to-Speech in Open WebUI

The Open WebUI service can be configured to use either the `openedai_speech` service or the `coqui_tts` service (via the `coqui_bridge`) for text-to-speech functionality. THIS ALLOWS YOU TO TALK TO YOUR MODELS VIA VOICE CHAT, AND FOR IT TO ANSWER YOU WITH AUDIO.

Follow these steps to configure TTS in the Open WebUI settings:

1.  Navigate to the Open WebUI interface (default: `http://localhost:8080`).
2.  Go to Settings -> Speech.
3.  Select the desired Text-to-Speech Engine.

### Using `openedai_speech`

-   **Text-to-Speech Engine:** `OpenAI`
-   **OpenAI-Compatible TTS URL:** `http://openedai_speech:8000/v1` (Use the service name `openedai_speech` as Docker Compose handles the internal networking)
-   **API Key:** (Can be left blank or use any placeholder)
-   **TTS Voice:** Select available voices (e.g., `alloy`)
-   **TTS Model:** `tts-1`

![Open WebUI config for openedai_speech](working_openedai_speech_config.png)

**NOTE:** You can also interact with the `openedai_speech` service directly using its OpenAI-compatible API without going through the Open WebUI. Refer to the [openedai-speech documentation](https://github.com/matatonic/openedai-speech) for more details.

Example using `curl`:
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tts-1",
    "input": "Hello from the openedai speech service!",
    "voice": "alloy"
  }' \
  --output openedai_output.wav

# Play the audio (requires a player like ffplay, vlc, etc.)
# ffplay openedai_output.wav
```

### Using `coqui_tts` (via `coqui_bridge`)

-   **Text-to-Speech Engine:** `OpenAI` (The bridge makes Coqui compatible)
-   **OpenAI-Compatible TTS URL:** `http://coqui_bridge:8080/v1` (Use the service name `coqui_bridge`)
-   **API Key:** (Can be left blank or use any placeholder)
-   **TTS Voice:** Select available Coqui voices (e.g., `p225` - this depends on the Coqui model loaded)
-   **TTS Model:** `tts-1` (or other model identifier if configured differently)

![Open WebUI config for coqui_bridge](working_coqui_tts_config.png)

**NOTE:** You can interact with the Coqui TTS service directly or via the bridge API.

*   **Direct Coqui API:** The native Coqui TTS server runs on port `5002`. Refer to the [Coqui TTS Documentation](https://docs.coqui.ai/en/latest/) for details on its API (often `/api/tts`).

    Example using `curl` (assuming default VCTK model and speaker `p225`):
    ```bash
    curl "http://localhost:5002/api/tts?text=Hello%20directly%20from%20Coqui%20TTS&speaker_id=p225" \
      --output coqui_direct_output.wav

    # Play the audio
    # ffplay coqui_direct_output.wav
    ```
*   **Bridge API:** The `coqui_bridge` service on port `8090` exposes an OpenAI-compatible endpoint.

    Example using `curl`:
    ```bash
    curl -X POST http://localhost:8090/v1/audio/speech \
      -H "Content-Type: application/json" \
      -d '{
        "model": "tts-1",
        "input": "Hello from Coqui via the bridge!",
        "voice": "p225"
      }' \
      --output coqui_bridge_output.wav

    # Play the audio
    # ffplay coqui_bridge_output.wav
    ```

Choose one configuration based on the TTS service you prefer to use.

## Stopping the Stack

To stop the services, run:

```bash
docker-compose down
```

This will stop and remove the containers. Add the `-v` flag (`docker-compose down -v`) if you also want to remove the volumes (ollama models, webui data, coqui models).

## Volumes

The following named volumes are used for persistent storage:

- `ollama_data`: Stores Ollama models and data.
- `webui_data`: Stores Open WebUI configuration and data.
- `coqui_models`: Stores downloaded Coqui TTS models.

The `openedai_speech` service uses bind mounts for its configuration and voice data located in the `./openedai-speech` directory within the project folder.

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

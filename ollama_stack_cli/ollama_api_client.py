import urllib.request
import urllib.error
import json
import socket

from .schemas import ServiceStatus, ResourceUsage
from .display import Display


class OllamaApiClient:
    """A client for interacting with the native Ollama API."""

    def __init__(self, display: Display):
        # Initialization logic for the client, e.g., setting base URL
        self.base_url = "http://localhost:11434"
        self.display = display

    def get_status(self) -> ServiceStatus:
        """
        Gets the status of the native Ollama service by calling its API.
        """
        status = "N/A"
        health = "unknown"
        ports = {}
        is_running = False

        try:
            with urllib.request.urlopen(f"{self.base_url}/api/ps", timeout=2) as response:
                if 200 <= response.status < 300:
                    health = "healthy"
                    is_running = True
                    ports = {'11434/tcp': 11434}
                    data = json.load(response)
                    model_count = len(data.get("models", []))
                    if model_count > 0:
                        status = f"Loaded ({model_count} model{'s' if model_count > 1 else ''})"
                    else:
                        status = "Running"
                else:
                    health = "unhealthy"

        except (urllib.error.URLError, socket.timeout, ConnectionRefusedError):
            health = "unhealthy"
            is_running = False
        except json.JSONDecodeError:
            self.display.warning("Could not parse JSON response from native Ollama API.")
            health = "unhealthy"

        return ServiceStatus(
            name="ollama (Native)",
            is_running=is_running,
            status=status,
            health=health,
            ports=ports,
            usage=ResourceUsage(),  # Native API does not provide usage stats
        ) 
import urllib.request
import urllib.error
import json
import socket
import subprocess
import shutil
import logging

from .schemas import ServiceStatus, ResourceUsage
from .display import Display

log = logging.getLogger(__name__)

class OllamaApiClient:
    """A client for interacting with the native Ollama API and managing the native service."""

    def __init__(self, display: Display):
        # Initialization logic for the client, e.g., setting base URL
        self.base_url = "http://localhost:11434"
        self.display = display

    def get_status(self) -> ServiceStatus:
        """
        Gets the status of the native Ollama service by calling its API and ollama commands.
        """
        status = "N/A"
        health = "unknown"
        ports = {}
        is_running = False

        # First check if ollama command is available
        if not shutil.which("ollama"):
            return ServiceStatus(
                name="ollama (Native)",
                is_running=False,
                status="Not installed",
                health="unavailable",
                ports={},
                usage=ResourceUsage(),
            )

        # Check if ollama server is running via API
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/version", timeout=2) as response:
                if 200 <= response.status < 300:
                    health = "healthy"
                    is_running = True
                    ports = {'11434/tcp': 11434}
                    
                    # Get running models using ollama ps command
                    try:
                        result = subprocess.run(
                            ["ollama", "ps"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            # Parse ollama ps output to count running models
                            lines = result.stdout.strip().split('\n')
                            # Skip header line, count model lines
                            model_count = max(0, len([line for line in lines[1:] if line.strip()]))
                            if model_count > 0:
                                status = f"Running ({model_count} model{'s' if model_count > 1 else ''})"
                            else:
                                status = "Running (no models loaded)"
                        else:
                            status = "Running"
                    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                        status = "Running"
                else:
                    health = "unhealthy"

        except (urllib.error.URLError, socket.timeout, ConnectionRefusedError):
            health = "unhealthy"
            is_running = False
        except json.JSONDecodeError:
            log.warning("Could not parse JSON response from native Ollama API.", exc_info=True)
            health = "unhealthy"

        return ServiceStatus(
            name="ollama (Native)",
            is_running=is_running,
            status=status,
            health=health,
            ports=ports,
            usage=ResourceUsage(),  # Native API does not provide usage stats
        )

    def is_service_running(self) -> bool:
        """Check if the native Ollama service is running."""
        # Check if ollama command is available first
        if not shutil.which("ollama"):
            return False
            
        # Try process check first (fastest)
        try:
            result = subprocess.run(
                ["pgrep", "-f", "ollama serve"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
        
        # Fall back to API check
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/version", timeout=2) as response:
                return 200 <= response.status < 300
        except (urllib.error.URLError, socket.timeout, ConnectionRefusedError):
            return False

    def start_service(self) -> bool:
        """Start the native Ollama service."""
        # Check if ollama command is available
        if not shutil.which("ollama"):
            log.warning("Ollama is not installed or not in PATH. Please install Ollama.")
            return False
        
        # Check if ollama is already running
        if self.is_service_running():
            log.info("Ollama service is already running.")
            return True
        
        try:
            log.info("Starting native Ollama service...")
            # Start ollama serve in background
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            log.info("Ollama service started successfully.")
            return True
        except Exception as e:
            log.error(f"Failed to start Ollama service: {e}")
            log.info("Please start Ollama manually with: ollama serve")
            return False

    def stop_service(self) -> bool:
        """Stop the native Ollama service."""
        # Check if ollama command is available
        if not shutil.which("ollama"):
            log.warning("Ollama is not installed or not in PATH.")
            return True  # Consider success since service can't be running
        
        # Check if service is running first
        if not self.is_service_running():
            log.info("Ollama service is not running.")
            return True
        
        # Try to stop gracefully by killing the serve process
        # Note: 'ollama stop' stops models, not the server itself
        try:
            result = subprocess.run(
                ["pkill", "-f", "ollama serve"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                log.info("Ollama service stopped successfully.")
                return True
            else:
                # Process might not exist, check if service is actually stopped
                if not self.is_service_running():
                    log.info("Ollama service is now stopped.")
                    return True
                else:
                    log.warning("Failed to stop Ollama service via pkill.")
                    return False
        except subprocess.TimeoutExpired:
            log.error("Timeout while stopping Ollama service.")
            return False
        except Exception as e:
            log.error(f"Failed to stop Ollama service: {e}")
            log.info("Please stop Ollama manually (kill the 'ollama serve' process).")
            return False 
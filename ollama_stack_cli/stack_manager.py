from .docker_client import DockerClient
from .ollama_api_client import OllamaApiClient
from .schemas import AppConfig, StackStatus, CheckReport
from .display import Display
from typing import Optional


class StackManager:
    """
    The primary backend interface for all CLI commands.
    Orchestrates operations across different backend services.
    """

    def __init__(self, config: AppConfig, display: Display):
        self.config = config
        self.display = display
        self.docker_client = DockerClient(config, display)
        self.ollama_api_client = OllamaApiClient(display)
        self.platform = self.docker_client.detect_platform()

    def get_stack_status(self) -> StackStatus:
        """
        Gathers and returns the status of the entire stack,
        handling different platforms.
        """
        if self.platform == 'apple':
            # On Apple, get container status and native ollama status separately
            container_services = self.docker_client.get_container_status(['webui', 'mcp_proxy'])
            ollama_service = self.ollama_api_client.get_status()
            core_services = [ollama_service] + container_services
        else:
            # On other platforms, all services are in docker
            core_services = self.docker_client.get_container_status(['ollama', 'webui', 'mcp_proxy'])
        
        return StackStatus(core_services=core_services, extensions=[])

    def start_services(self, update: bool = False):
        """Starts the services."""
        self.docker_client.start_services(update=update, platform=self.platform)

    def stop_services(self):
        """Stops the services."""
        self.docker_client.stop_services()

    def restart_services(self, update: bool = False):
        """Restarts the services."""
        self.stop_services()
        self.start_services(update=update)

    def stream_logs(self, service_or_extension: Optional[str] = None, follow: bool = False, tail: Optional[int] = None):
        """Streams logs from a specific service/extension or the whole stack."""
        if self.platform == "apple" and service_or_extension == "ollama":
            yield "[WARNING] Ollama runs natively on Apple Silicon. No container logs are available."
            yield "[INFO] To view logs for the native Ollama application, use the 'log' command provided by Ollama."
            return
        
        yield from self.docker_client.stream_logs(service_or_extension, follow, tail)

    def run_environment_checks(self) -> CheckReport:
        """Runs checks for the environment and returns a report."""
        return self.docker_client.run_environment_checks() 
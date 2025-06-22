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
        service_names = list(self.config.services.keys())
        if self.platform == 'apple':
            container_service_names = [s for s in service_names if s != 'ollama']
            container_services = self.docker_client.get_container_status(container_service_names)
            ollama_service = self.ollama_api_client.get_status()
            services = [ollama_service] + container_services
        else:
            services = self.docker_client.get_container_status(service_names)
        
        return StackStatus(core_services=services, extensions=[])

    def start_services(self, update: bool = False):
        """Starts the services."""
        if self.docker_client.is_stack_running():
            self.display.info("Ollama Stack is already running.")
            return

        if update:
            self.docker_client.pull_images()

        if self.platform == "apple":
            self.display.info("On Apple Silicon, ensure the native Ollama application is running.")

        self.docker_client.start_services()
        # Health checks and access points display would be added here

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
            self.display.warning("Ollama runs natively on Apple Silicon. No container logs are available.")
            self.display.info("To view logs for the native Ollama application, use the 'log' command provided by Ollama.")
            return
        
        yield from self.docker_client.stream_logs(service_or_extension, follow, tail)

    def run_environment_checks(self) -> CheckReport:
        """Runs checks for the environment and returns a report."""
        return self.docker_client.run_environment_checks() 
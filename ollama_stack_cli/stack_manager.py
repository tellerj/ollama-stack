import logging
from .docker_client import DockerClient
from .ollama_api_client import OllamaApiClient
from .schemas import AppConfig, StackStatus, CheckReport, ServiceStatus
from .display import Display
from typing import Optional, List

log = logging.getLogger(__name__)

class StackManager:
    """
    The primary backend interface for all CLI commands.
    Provides access to underlying clients without containing business logic.
    """

    def __init__(self, config: AppConfig, display: Display):
        self.config = config
        self.display = display
        self.docker_client = DockerClient(config, display)
        self.ollama_api_client = OllamaApiClient(display)
        self.platform = self.docker_client.detect_platform()

    # Delegation methods for Docker operations
    def is_stack_running(self) -> bool:
        """Check if any stack component containers are running."""
        return self.docker_client.is_stack_running()

    def pull_images(self):
        """Pull the latest images for the services."""
        return self.docker_client.pull_images()

    def start_docker_services(self, services: List[str]):
        """Start specific Docker services."""
        return self.docker_client.start_services(services)

    def stop_docker_services(self):
        """Stop Docker services."""
        return self.docker_client.stop_services()

    def get_docker_services_status(self, service_names: List[str]) -> List[ServiceStatus]:
        """Get status for Docker services."""
        return self.docker_client.get_container_status(service_names)

    def stream_docker_logs(self, service_or_extension: Optional[str] = None, follow: bool = False, tail: Optional[int] = None, level: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None):
        """Stream logs from Docker containers."""
        yield from self.docker_client.stream_logs(service_or_extension, follow, tail, level, since, until)

    def run_docker_environment_checks(self, fix: bool = False, verbose: bool = False) -> CheckReport:
        """Run environment checks via Docker client."""
        return self.docker_client.run_environment_checks(fix=fix, verbose=verbose)

    # Delegation methods for API-based services
    def get_ollama_status(self) -> ServiceStatus:
        """Get status for Ollama API service."""
        return self.ollama_api_client.get_status()

 
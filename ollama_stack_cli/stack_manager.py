import logging
from .docker_client import DockerClient
from .ollama_api_client import OllamaApiClient
from .schemas import AppConfig, StackStatus, CheckReport
from .display import Display
from typing import Optional

log = logging.getLogger(__name__)

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

    def get_stack_status(self, extensions_only: bool = False) -> StackStatus:
        """
        Gathers and returns the status of the entire stack,
        handling different platforms.
        """
        core_services = []
        if not extensions_only:
            # Group services by type for efficient processing
            docker_services = [name for name, conf in self.config.services.items() if conf.type == 'docker']
            api_services = {name: conf for name, conf in self.config.services.items() if conf.type == 'native-api'}

            # Get status for all Docker services in one call
            if docker_services:
                core_services.extend(self.docker_client.get_container_status(docker_services))

            # Get status for individual API-based services
            for name, config in api_services.items():
                if name == 'ollama': # This could be a registry of clients in the future
                    core_services.append(self.ollama_api_client.get_status())
        
        return StackStatus(core_services=core_services, extensions=[])

    def start_services(self, update: bool = False):
        """Starts the services."""
        if self.docker_client.is_stack_running():
            log.info("Ollama Stack is already running.")
            return

        if update:
            self.docker_client.pull_images()

        # Filter services by type
        docker_services = [name for name, conf in self.config.services.items() if conf.type == 'docker']
        native_services = [name for name, conf in self.config.services.items() if conf.type == 'native-api']

        # Start only Docker services
        if docker_services:
            log.info("Starting Docker-based services...")
            self.docker_client.start_services(docker_services)

        # Display info for non-docker services
        for service_name in native_services:
            log.info(f"Please ensure the native '{service_name}' service is running.")

    def stop_services(self):
        """Stops the services."""
        self.docker_client.stop_services()

    def restart_services(self, update: bool = False):
        """Restarts the services."""
        self.stop_services()
        self.start_services(update=update)

    def stream_logs(self, service_or_extension: Optional[str] = None, follow: bool = False, tail: Optional[int] = None, level: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None):
        """Streams logs from a specific service/extension or the whole stack."""
        service_config = self.config.services.get(service_or_extension) if service_or_extension else None

        if service_config and service_config.type == "native-api":
            log.warning(f"'{service_or_extension}' runs as a native service. No container logs are available.")
            log.info(f"To view its logs, please consult the service's own logging mechanisms.")
            return
        
        yield from self.docker_client.stream_logs(service_or_extension, follow, tail, level, since, until)

    def run_environment_checks(self, fix: bool = False, verbose: bool = False) -> CheckReport:
        """Runs checks for the environment and returns a report."""
        return self.docker_client.run_environment_checks(fix=fix, verbose=verbose) 
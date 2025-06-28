import logging
import platform
import docker
from .docker_client import DockerClient
from .ollama_api_client import OllamaApiClient
from .schemas import AppConfig, StackStatus, CheckReport, ServiceStatus
from .display import Display
from typing import Optional, List

log = logging.getLogger(__name__)

class StackManager:
    """
    Platform-aware orchestrator for the Ollama Stack.
    Handles platform detection, service configuration, and cross-service coordination.
    """

    def __init__(self, config: AppConfig, display: Display):
        self.config = config
        self.display = display
        
        # Detect platform first and configure services accordingly
        self.platform = self.detect_platform()
        self.configure_services_for_platform()
        
        # Initialize clients after platform configuration
        self.docker_client = DockerClient(config, display)
        self.ollama_api_client = OllamaApiClient(display)

    def detect_platform(self) -> str:
        """
        Detects the current platform (apple, nvidia, or cpu).
        Moved from DockerClient to centralize platform-specific logic.
        """
        system = platform.system()
        machine = platform.machine()

        if system == "Darwin" and machine == "arm64":
            log.info("Apple Silicon platform detected.")
            return "apple"
        
        # For NVIDIA detection, we need to check Docker info
        try:
            client = docker.from_env()
            info = client.info()
            if info.get("Runtimes", {}).get("nvidia"):
                log.info("NVIDIA GPU platform detected.")
                return "nvidia"
        except Exception:
            log.warning("Could not get Docker info to check for NVIDIA runtime.")

        log.info("Defaulting to CPU platform.")
        return "cpu"

    def configure_services_for_platform(self):
        """
        Applies platform-specific service configurations.
        Moved from config.py to centralize platform-specific logic.
        """
        if self.platform == "apple":
            log.info("Applying Apple Silicon specific configuration.")
            if "ollama" in self.config.services:
                self.config.services["ollama"].type = "native-api"
                self.config.services["ollama"].health_check_url = "http://localhost:11434"

    def get_compose_files(self) -> list[str]:
        """
        Determines the appropriate docker-compose files to use based on platform.
        Returns files for DockerClient to use, doesn't invoke commands directly.
        """
        compose_files = [self.config.docker_compose_file]
        
        platform_config = self.config.platform.get(self.platform)
        if platform_config:
            compose_files.append(platform_config.compose_file)
            log.info(f"Using platform-specific compose file: {platform_config.compose_file}")
        
        return compose_files

    # Delegation methods for Docker operations
    def is_stack_running(self) -> bool:
        """Check if any stack component containers are running."""
        return self.docker_client.is_stack_running()

    def pull_images(self):
        """Pull the latest images for the services."""
        compose_files = self.get_compose_files()
        return self.docker_client.pull_images(compose_files)

    def start_docker_services(self, services: List[str]):
        """Start specific Docker services."""
        compose_files = self.get_compose_files()
        return self.docker_client.start_services(services, compose_files)

    def stop_docker_services(self):
        """Stop Docker services."""
        compose_files = self.get_compose_files()
        return self.docker_client.stop_services(compose_files)

    def get_docker_services_status(self, service_names: List[str]) -> List[ServiceStatus]:
        """Get status for Docker services."""
        return self.docker_client.get_container_status(service_names)

    def stream_docker_logs(self, service_or_extension: Optional[str] = None, follow: bool = False, tail: Optional[int] = None, level: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None):
        """Stream logs from Docker containers."""
        compose_files = self.get_compose_files()
        yield from self.docker_client.stream_logs(service_or_extension, follow, tail, level, since, until, compose_files)

    def run_docker_environment_checks(self, fix: bool = False, verbose: bool = False) -> CheckReport:
        """Run environment checks via Docker client."""
        return self.docker_client.run_environment_checks(fix=fix, verbose=verbose, platform=self.platform)

    # Delegation methods for API-based services
    def get_ollama_status(self) -> ServiceStatus:
        """Get status for Ollama API service."""
        return self.ollama_api_client.get_status()

    def start_native_services(self, services: List[str]) -> bool:
        """Start native services."""
        success = True
        for service_name in services:
            if service_name == "ollama":
                if not self.ollama_api_client.start_service():
                    success = False
            else:
                log.info(f"Please ensure the native '{service_name}' service is running.")
        return success

    def stop_native_services(self, services: List[str]) -> bool:
        """Stop native services."""
        success = True
        for service_name in services:
            if service_name == "ollama":
                if not self.ollama_api_client.stop_service():
                    success = False
            else:
                log.info(f"Please stop the native '{service_name}' service manually.")
        return success

    def is_native_service_running(self, service_name: str) -> bool:
        """Check if a native service is running."""
        if service_name == "ollama":
            return self.ollama_api_client.is_service_running()
        return False

 
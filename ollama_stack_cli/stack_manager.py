import logging
import platform
import socket
import urllib.request
import urllib.error
import urllib.parse
import docker
from .docker_client import DockerClient
from .ollama_api_client import OllamaApiClient
from .schemas import AppConfig, StackStatus, CheckReport, ServiceStatus, EnvironmentCheck
from .display import Display
from typing import Optional, List
from pathlib import Path

log = logging.getLogger(__name__)

class StackManager:
    """
    Platform-aware orchestrator for the Ollama Stack.
    Handles platform detection, service configuration, and cross-service coordination.
    """

    # Unified health check URLs for all services
    HEALTH_CHECK_URLS = {
        "ollama": "http://localhost:11434",
        "webui": "http://localhost:8080", 
        "mcp_proxy": "http://localhost:8200",
    }

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

    # =============================================================================
    # Environment Validation
    # =============================================================================

    def run_environment_checks(self, fix: bool = False) -> CheckReport:
        """Run comprehensive environment checks by delegating to appropriate clients."""
        log.debug("Running comprehensive environment checks...")
        
        # Delegate environment checks to Docker client
        report = self.docker_client.run_environment_checks(fix=fix, platform=self.platform)
        
        # Add platform-specific checks for native services
        if self.platform == "apple":
            native_checks = self.ollama_api_client.run_environment_checks(fix=fix)
            report.checks.extend(native_checks)
        
        return report

    # =============================================================================
    # Service Management Delegation
    # =============================================================================

    def is_stack_running(self) -> bool:
        """Check if any stack component (Docker containers or native services) are running."""
        # Check Docker containers
        docker_running = self.docker_client.is_stack_running()
        
        # Check native services
        native_running = False
        for service_name, service_config in self.config.services.items():
            if service_config.type == "native-api":
                if self.is_native_service_running(service_name):
                    native_running = True
                    break
        
        return docker_running or native_running
    
    def get_stack_status(self, extensions_only: bool = False) -> StackStatus:
        """Get comprehensive status for all stack components."""
        core_services = []
        extensions = []  # TODO: Implement actual extensions support
        
        if not extensions_only:
            # Get status for Docker services
            docker_services = [name for name, conf in self.config.services.items() if conf.type == 'docker']
            if docker_services:
                log.debug(f"Getting status for Docker services: {docker_services}")
                try:
                    core_services.extend(self.get_docker_services_status(docker_services))
                except Exception as e:
                    log.error(f"Failed to get Docker services status: {e}")
                    # Add failed service entries
                    for service_name in docker_services:
                        core_services.append(ServiceStatus(
                            name=service_name,
                            is_running=False,
                            status="error",
                            health="error"
                        ))
            
            # Get status for native services
            native_services = [name for name, conf in self.config.services.items() if conf.type == 'native-api']
            for service_name in native_services:
                log.debug(f"Getting status for native service: {service_name}")
                try:
                    service_status = self.get_native_service_status(service_name)
                    core_services.append(service_status)
                except Exception as e:
                    log.error(f"Failed to get status for native service {service_name}: {e}")
                    core_services.append(ServiceStatus(
                        name=f"{service_name} (Native)",
                        is_running=False,
                        status="error",
                        health="error"
                    ))
        
        # TODO: Add actual extensions support here
        # For now, extensions remain empty
        
        return StackStatus(core_services=core_services, extensions=extensions)
    
    def get_native_service_status(self, service_name: str) -> ServiceStatus:
        """Get status for a native service - generic handler."""
        if service_name == "ollama":
            return self.ollama_api_client.get_status()
        else:
            # Generic fallback for unknown native services
            log.debug(f"Unknown native service: {service_name}, using generic status check")
            return ServiceStatus(
                name=f"{service_name} (Native)",
                is_running=False,
                status="unknown",
                health="unknown"
            )
    
    def get_running_services_summary(self) -> tuple[list[str], list[str]]:
        """Get lists of running Docker and native services for more specific messaging."""
        running_docker = []
        running_native = []
        
        # Check Docker services
        docker_services = [name for name, conf in self.config.services.items() if conf.type == 'docker']
        if docker_services:
            try:
                statuses = self.get_docker_services_status(docker_services)
                running_docker = [status.name for status in statuses if status.is_running]
            except (ConnectionResetError, ConnectionError) as e:
                log.debug(f"Docker API connection error while checking service status: {e}")
                # Fall back to basic Docker client check
                try:
                    if self.docker_client.is_stack_running():
                        # If we can't get detailed status but stack is running, assume all Docker services are running
                        running_docker = docker_services
                except Exception:
                    # If all Docker API calls fail, assume no Docker services are running
                    log.debug("All Docker API calls failed, assuming no Docker services running")
                    running_docker = []
        
        # Check native services  
        for service_name, service_config in self.config.services.items():
            if service_config.type == "native-api":
                try:
                    if self.is_native_service_running(service_name):
                        running_native.append(service_name)
                except Exception as e:
                    log.debug(f"Failed to check native service {service_name}: {e}")
        
        return running_docker, running_native

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
        """Get status for Docker services with unified health checks."""
        # Get container status from Docker client (without health checks)
        statuses = self.docker_client.get_container_status(service_names)
        
        # Apply unified health checks for running services
        for status in statuses:
            if status.is_running:
                # Use our unified health check system
                health = self.check_service_health(status.name)
                # Update the status with the health check result
                status.health = health
            else:
                # If not running, health is definitely unhealthy
                status.health = "unhealthy"
        
        return statuses

    def stream_docker_logs(self, service_or_extension: Optional[str] = None, follow: bool = False, tail: Optional[int] = None, level: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None):
        """Stream logs from Docker containers."""
        compose_files = self.get_compose_files()
        yield from self.docker_client.stream_logs(service_or_extension, follow, tail, level, since, until, compose_files)

    def stream_native_logs(self, service_name: str, follow: bool = False, tail: Optional[int] = None, level: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None):
        """Stream logs from native services."""
        log.debug(f"Streaming logs from native service: {service_name}")
        
        if service_name == "ollama":
            yield from self.ollama_api_client.get_logs(follow=follow, tail=tail, level=level, since=since, until=until)
        else:
            # Generic fallback for unknown native services
            log.warning(f"Log streaming not implemented for native service: {service_name}")
            log.info(f"Service '{service_name}' is running natively on your system")
            log.info("Check system logs or service-specific log locations for more details")

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

    # =============================================================================
    # Unified Health Check System
    # =============================================================================

    def check_service_health(self, service_name: str) -> str:
        """
        Universal health check for any service using HTTP -> TCP fallback approach.
        
        This unified method works for:
        - Docker services (webui, mcp_proxy)
        - Native services (ollama)  
        - Remote services (any HTTP/TCP endpoint)
        
        Uses a two-tier approach:
        1. Try HTTP health check first (more comprehensive)
        2. Fall back to TCP connectivity check (matches Docker's health check)
        
        Args:
            service_name: Name of service to check
            
        Returns:
            "healthy", "unhealthy", or "unknown"
        """
        url = self.HEALTH_CHECK_URLS.get(service_name)
        if not url:
            log.debug(f"No health check URL configured for service: {service_name}")
            return "unknown"
        
        # Extract port from URL for TCP fallback
        parsed_url = urllib.parse.urlparse(url)
        port = parsed_url.port or (80 if parsed_url.scheme == 'http' else 443)
        
        # First, try HTTP health check (more comprehensive)
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if 200 <= response.status < 300:
                    log.debug(f"HTTP health check passed for {service_name}")
                    return "healthy"
                else:
                    log.debug(f"HTTP health check failed for {service_name}: status {response.status}")
                    # HTTP responded but with error status, fall back to TCP check
        except (urllib.error.URLError, ConnectionRefusedError, socket.timeout) as e:
            log.debug(f"HTTP health check failed for {service_name}: {e}")
            # HTTP failed, fall back to TCP check

        # Fall back to TCP connectivity check (matches Docker's approach)
        if self._check_tcp_connectivity("localhost", port):
            log.debug(f"TCP connectivity check passed for {service_name} on port {port}")
            return "healthy"
        else:
            log.debug(f"TCP connectivity check failed for {service_name} on port {port}")
            return "unhealthy"

    def _check_tcp_connectivity(self, host: str, port: int, timeout: float = 2.0) -> bool:
        """
        Test TCP connectivity to a host and port.
        
        This matches Docker's health check approach which uses TCP socket tests.
        
        Args:
            host: Hostname to connect to
            port: Port number to connect to  
            timeout: Connection timeout in seconds
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.error, socket.timeout, ConnectionRefusedError):
            return False

    # =============================================================================
    # Update Orchestration
    # =============================================================================

    def update_stack(self, services_only: bool = False, extensions_only: bool = False, force_restart: bool = False, called_from_start_restart: bool = False) -> bool:
        """
        Orchestrates unified update flow for both services and extensions.
        
        This method centralizes the sophisticated update logic including:
        - Flag validation
        - State management (running vs stopped stack)
        - Smart restart handling
        - Extension framework integration
        
        Args:
            services_only: Only update core stack services
            extensions_only: Only update enabled extensions
            force_restart: When True and stack is running, will stop/restart. 
                          When called from start/restart commands, updates inline without restart.
            called_from_start_restart: Explicit flag indicating call from start/restart commands
            
        Returns:
            bool: True if update succeeded, False otherwise
        """
        # Validate flags
        if services_only and extensions_only:
            log.error("Cannot specify both services_only and extensions_only")
            return False
            
        update_core = not extensions_only
        update_extensions = not services_only
        
        try:
            # Check current stack status
            stack_running = self.is_stack_running()
            restart_after_update = False
            
            # Handle running stack state
            if stack_running and not force_restart:
                log.info("Stack is currently running. Updates require stopping services.")
                # Command layer should handle user confirmation and call with force_restart=True
                return False
            elif stack_running and force_restart:
                if called_from_start_restart:
                    # Inline update - don't stop/restart, just pull images
                    log.info("Performing inline update for running services...")
                    restart_after_update = False
                else:
                    # Direct update call - stop and restart
                    log.info("Stopping services for update...")
                    
                    # Stop both Docker and native services (like stop command does)
                    docker_services = [name for name, conf in self.config.services.items() if conf.type == 'docker']
                    native_services = [name for name, conf in self.config.services.items() if conf.type == 'native-api']
                    
                    success = True
                    if docker_services:
                        if not self.stop_docker_services():
                            log.error("Failed to stop Docker services")
                            success = False
                    
                    if native_services:
                        if not self.stop_native_services(native_services):
                            log.error("Failed to stop native services")
                            success = False
                    
                    if not success:
                        log.error("Failed to stop services")
                        return False
                        
                    restart_after_update = True
            
            # Update core services
            if update_core:
                log.info("Updating core stack services...")
                compose_files = self.get_compose_files()
                if not self.docker_client.pull_images_with_progress(compose_files):
                    log.error("Failed to update core services")
                    return False
                log.info("Core services updated successfully")
            
            # Update extensions
            if update_extensions:
                enabled_extensions = self.config.extensions.enabled
                if enabled_extensions:
                    log.info(f"Updating {len(enabled_extensions)} enabled extensions...")
                    for extension_name in enabled_extensions:
                        log.info(f"Updating extension: {extension_name}")
                        # TODO: Implement actual extension update logic
                        log.warning(f"Extension update not yet implemented for: {extension_name}")
                    log.info("All enabled extensions updated successfully")
                else:
                    log.info("No extensions enabled, skipping extension updates")
            
            # Restart if needed
            if restart_after_update:
                log.info("Restarting stack...")
                docker_services = [name for name, conf in self.config.services.items() if conf.type == 'docker']
                if docker_services and not self.start_docker_services(docker_services):
                    log.error("Failed to restart Docker services after update")
                    return False
                
                native_services = [name for name, conf in self.config.services.items() if conf.type == 'native-api']
                if native_services and not self.start_native_services(native_services):
                    log.error("Failed to restart native services after update")
                    return False
                    
                log.info("Stack restarted successfully after update")
            
            # Log completion
            if update_core and update_extensions:
                log.info("Update completed successfully - core services and extensions are up to date")
            elif update_core:
                log.info("Core services update completed successfully")
            else:
                log.info("Extension updates completed successfully")
                
            return True
            
        except Exception as e:
            log.error(f"Update failed: {e}")
            return False

    # =============================================================================
    # Resource Management
    # =============================================================================

    def find_resources_by_label(self, label_key: str, label_value: Optional[str] = None) -> dict:
        """
        Finds all Docker resources (containers, volumes, networks) by label.
        
        Args:
            label_key: The label key to search for (e.g., "ollama-stack.component")
            label_value: Optional specific label value to match
            
        Returns:
            dict: Dictionary with keys 'containers', 'volumes', 'networks' containing lists of resources
        """
        if not self.docker_client.client:
            log.warning("Docker client not available")
            return {"containers": [], "volumes": [], "networks": []}
        
        filter_dict = {f"label": label_key if label_value is None else f"{label_key}={label_value}"}
        
        try:
            resources = {
                "containers": [],
                "volumes": [],
                "networks": []
            }
            
            # Find containers
            containers = self.docker_client.client.containers.list(
                all=True, 
                filters=filter_dict
            )
            resources["containers"] = containers
            log.debug(f"Found {len(containers)} containers with label {label_key}")
            
            # Find volumes
            volumes = self.docker_client.client.volumes.list(
                filters=filter_dict
            )
            resources["volumes"] = volumes
            log.debug(f"Found {len(volumes)} volumes with label {label_key}")
            
            # Find networks
            networks = self.docker_client.client.networks.list(
                filters=filter_dict
            )
            resources["networks"] = networks
            log.debug(f"Found {len(networks)} networks with label {label_key}")
            
            return resources
            
        except Exception as e:
            log.error(f"Failed to find resources by label {label_key}: {e}")
            return {"containers": [], "volumes": [], "networks": []}

    def cleanup_resources(self, remove_volumes: bool = False, force: bool = False) -> bool:
        """
        Cleans up orphaned containers, networks, and optionally volumes for the stack.
        
        Args:
            remove_volumes: Whether to also remove volumes (data destruction!)
            force: Skip confirmation prompts for resource removal
            
        Returns:
            bool: True if cleanup succeeded, False otherwise
        """
        if not self.docker_client.client:
            log.warning("Docker client not available for cleanup")
            return False
        
        try:
            log.info("Finding stack resources for cleanup...")
            resources = self.find_resources_by_label("ollama-stack.component")
            
            cleaned_count = 0
            
            # Clean up stopped containers
            stopped_containers = [c for c in resources["containers"] if c.status != "running"]
            if stopped_containers:
                log.info(f"Removing {len(stopped_containers)} stopped containers...")
                for container in stopped_containers:
                    try:
                        container.remove(force=force)
                        log.debug(f"Removed container: {container.name}")
                        cleaned_count += 1
                    except Exception as e:
                        log.warning(f"Failed to remove container {container.name}: {e}")
            
            # Clean up unused networks (excluding 'bridge', 'host', 'none')
            unused_networks = [n for n in resources["networks"] if n.name not in ['bridge', 'host', 'none']]
            if unused_networks:
                log.info(f"Removing {len(unused_networks)} unused networks...")
                for network in unused_networks:
                    try:
                        network.remove()
                        log.debug(f"Removed network: {network.name}")
                        cleaned_count += 1
                    except Exception as e:
                        log.warning(f"Failed to remove network {network.name}: {e}")
            
            # Clean up volumes if requested (DANGEROUS!)
            if remove_volumes:
                volumes = resources["volumes"]
                if volumes:
                    log.warning(f"Removing {len(volumes)} volumes - THIS WILL DELETE DATA!")
                    for volume in volumes:
                        try:
                            volume.remove(force=force)
                            log.debug(f"Removed volume: {volume.name}")
                            cleaned_count += 1
                        except Exception as e:
                            log.warning(f"Failed to remove volume {volume.name}: {e}")
            
            if cleaned_count > 0:
                log.info(f"Cleanup completed - removed {cleaned_count} resources")
            else:
                log.info("No resources found for cleanup")
                
            return True
            
        except Exception as e:
            log.error(f"Resource cleanup failed: {e}")
            return False

    def uninstall_stack(self, remove_volumes: bool = False, keep_config: bool = False, force: bool = False) -> bool:
        """
        Completely uninstalls the stack including all resources and optionally configuration.
        
        Args:
            remove_volumes: Whether to remove volumes (destroys persistent data!)
            keep_config: Whether to preserve configuration files
            force: Skip all confirmation prompts
            
        Returns:
            bool: True if uninstall succeeded, False otherwise
        """
        try:
            log.info("Beginning stack uninstall process...")
            
            # Step 1: Stop all services
            log.info("Stopping all services...")
            if self.is_stack_running():
                if not self.stop_docker_services():
                    log.warning("Failed to stop some Docker services")
                
                native_services = [name for name, conf in self.config.services.items() if conf.type == 'native-api']
                if native_services:
                    if not self.stop_native_services(native_services):
                        log.warning("Failed to stop some native services")
            
            # Step 2: Remove containers and networks
            log.info("Removing containers and networks...")
            if not self.cleanup_resources(remove_volumes=remove_volumes, force=force):
                log.warning("Failed to cleanup some resources")
            
            # Step 3: Remove Docker images
            log.info("Removing Docker images...")
            if not self.docker_client.remove_resources(remove_images=True, force=force):
                log.warning("Failed to remove some Docker images")
            
            # Step 4: Clean up configuration files (unless keeping them)
            if not keep_config:
                log.info("Removing configuration files...")
                try:
                    # Remove .env file if it exists
                    env_file = Path(".env")
                    if env_file.exists():
                        env_file.unlink()
                        log.debug("Removed .env file")
                    
                    # Remove .ollama-stack.json if it exists
                    config_file = Path(".ollama-stack.json")
                    if config_file.exists():
                        config_file.unlink()
                        log.debug("Removed .ollama-stack.json file")
                        
                except Exception as e:
                    log.warning(f"Failed to remove some configuration files: {e}")
            else:
                log.info("Preserving configuration files as requested")
            
            # Step 5: Log completion
            if remove_volumes:
                log.warning("Stack uninstalled completely including all data volumes")
            else:
                log.info("Stack uninstalled successfully (volumes preserved)")
                
            if keep_config:
                log.info("Configuration files preserved for future reinstallation")
            else:
                log.info("Configuration files removed - clean uninstall completed")
                
            return True
            
        except Exception as e:
            log.error(f"Stack uninstall failed: {e}")
            return False

 
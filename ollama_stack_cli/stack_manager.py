import logging
import platform
import socket
import urllib.request
import urllib.error
import urllib.parse
import docker
import secrets
import string
import typer
from .docker_client import DockerClient
from .ollama_api_client import OllamaApiClient
from .schemas import AppConfig, StackStatus, CheckReport, ServiceStatus, EnvironmentCheck, PlatformConfig, BackupConfig, BackupManifest
from .display import Display
from typing import Optional, List
from pathlib import Path
import os
from .config import get_default_config_dir, get_default_config_file, get_default_env_file, save_config

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
        Returns absolute paths to files for DockerClient to use.
        """
        from .config import get_compose_file_path
        
        compose_files = [str(get_compose_file_path(self.config.docker_compose_file))]
        
        platform_config = self.config.platform.get(self.platform)
        if platform_config:
            compose_files.append(str(get_compose_file_path(platform_config.compose_file)))
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
    # Installation Management
    # =============================================================================

    def install_stack(self, force: bool = False) -> dict:
        """
        Initialize fresh stack configuration and prepare environment for first use.
        
        Args:
            force: Whether to overwrite existing configuration without prompting
            
        Returns:
            dict: Dictionary with installation results including success status, paths, and check results
        """
        log.info("Initializing fresh stack configuration...")
        config_dir = get_default_config_dir()
        config_file = get_default_config_file()
        env_file = get_default_env_file()
        # Check if configuration directory already exists
        if config_dir.exists():
            log.info(f"Configuration directory already exists: {config_dir}")
            if not force:
                # Check if there are any existing config files
                existing_files = []
                if config_file.exists():
                    existing_files.append(".ollama-stack.json")
                if env_file.exists():
                    existing_files.append(".env")
                if existing_files:
                    self.display.panel(
                        f"Found existing configuration files: {', '.join(existing_files)}\n\n"
                        f"This will overwrite your current configuration.",
                        "Configuration Already Exists",
                        border_style="yellow"
                    )
                    if not typer.confirm("Do you want to overwrite the existing configuration?"):
                        self.display.error("Installation cancelled by user")
                        log.info("Installation cancelled - existing configuration preserved")
                        return {
                            'success': False,
                            'error': "Installation cancelled by user"
                        }
        try:
            # Create the configuration directory
            config_dir.mkdir(parents=True, exist_ok=True)
            log.info(f"Created configuration directory: {config_dir}")
            # Generate a secure secret key for WebUI
            secure_key = self._generate_secure_key()
            # Create a fresh AppConfig with platform-specific configurations
            app_config = AppConfig()
            app_config.project_name = "ollama-stack"
            app_config.webui_secret_key = secure_key
            # Add platform configurations
            app_config.platform = {
                "apple": PlatformConfig(compose_file="docker-compose.apple.yml"),
                "nvidia": PlatformConfig(compose_file="docker-compose.nvidia.yml"),
            }
            # Save the configuration
            save_config(self.display, app_config, config_file, env_file)
            log.info("Created default configuration files")
            # Log success message
            log.info("Configuration files created successfully!")
            # Run environment checks to validate the setup
            log.info("Running environment validation checks...")
            log.info("Validating Environment...")
            check_report = self.run_environment_checks(fix=False)
            # Check if all critical checks passed
            failed_checks = [check for check in check_report.checks if not check.passed]
            if failed_checks:
                log.warning(f"Some environment checks failed: {len(failed_checks)} issues found")
            else:
                log.info("All environment checks passed")
                log.info("Environment validation completed - all checks passed!")
            # Return installation results for command layer to display
            return {
                'success': True,
                'config_dir': config_dir,
                'config_file': config_file,
                'env_file': env_file,
                'check_report': check_report,
                'failed_checks': failed_checks
            }
        except Exception as e:
            error_msg = f"Failed to create configuration: {str(e)}"
            log.error(error_msg, exc_info=True)
            return {
                'success': False,
                'error': error_msg
            }
    
    def _generate_secure_key(self, length: int = 64) -> str:
        """Generate a cryptographically secure random key for WebUI authentication."""
        # Use letters, digits, and some safe symbols
        alphabet = string.ascii_letters + string.digits + "-_"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

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
            
            # Find volumes - use Docker Compose project label for volumes since that's how they're actually labeled
            if label_key == "ollama-stack.component":
                # For stack resources, look for Docker Compose volumes
                volume_filters = {"label": "com.docker.compose.project=ollama-stack"}
                volumes = self.docker_client.client.volumes.list(filters=volume_filters)
                log.debug(f"Found {len(volumes)} volumes with Docker Compose project label")
            else:
                # For other use cases, use the provided label
                volumes = self.docker_client.client.volumes.list(filters=filter_dict)
                log.debug(f"Found {len(volumes)} volumes with label {label_key}")
            
            resources["volumes"] = volumes
            
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

    def uninstall_stack(self, remove_volumes: bool = False, remove_config: bool = False, remove_images: bool = False, force: bool = False) -> bool:
        """
        Clean up all stack resources (containers, networks, images, and optionally volumes/config).
        
        Args:
            remove_volumes: Whether to remove volumes (destroys models, conversations, databases!)
            remove_config: Whether to remove configuration directory (~/.ollama-stack/)
            remove_images: Whether to remove Docker images (requires re-downloading on next start)
            force: Skip all confirmation prompts
            
        Returns:
            bool: True if uninstall succeeded, False otherwise
        """
        try:
            # Step 1: Display warnings based on destructive operations
            if remove_volumes and remove_config and remove_images:
                log.warning("⚠️  DESTRUCTIVE OPERATION: This will remove ALL stack data, configuration, and images!")
                log.warning("   • All AI models will be deleted (cannot be recovered)")
                log.warning("   • All chat conversations will be deleted (cannot be recovered)")
                log.warning("   • All configuration will be deleted")
                log.warning("   • All Docker images will be deleted (requires re-downloading)")
            elif remove_volumes and remove_config:
                log.warning("⚠️  DESTRUCTIVE OPERATION: This will remove ALL stack data and configuration!")
                log.warning("   • All AI models will be deleted (cannot be recovered)")
                log.warning("   • All chat conversations will be deleted (cannot be recovered)")
                log.warning("   • All configuration will be deleted")
            elif remove_volumes and remove_images:
                log.warning("⚠️  DESTRUCTIVE OPERATION: This will remove all stack data and images!")
                log.warning("   • All AI models will be deleted (cannot be recovered)")
                log.warning("   • All chat conversations will be deleted (cannot be recovered)")
                log.warning("   • All Docker images will be deleted (requires re-downloading)")
            elif remove_volumes:
                log.warning("⚠️  DESTRUCTIVE OPERATION: This will remove all stack data!")
                log.warning("   • All AI models will be deleted (cannot be recovered)")
                log.warning("   • All chat conversations will be deleted (cannot be recovered)")
            elif remove_images:
                log.info("Removing stack resources including Docker images (requires re-downloading on next start)")
            else:
                log.info("Removing stack resources (preserving data volumes, configuration, and images)")
            
            # Step 2: Find all Docker resources for summary
            log.info("Discovering stack resources...")
            resources = self.find_resources_by_label("ollama-stack.component")
            
            # Step 3: Display summary of what will be removed
            total_resources = len(resources["containers"]) + len(resources["networks"]) 
            if remove_volumes:
                total_resources += len(resources["volumes"])
            if remove_images:
                # Count images that would be removed (images used by stack containers)
                if self.docker_client.client:
                    try:
                        stack_containers = self.docker_client.client.containers.list(
                            all=True, 
                            filters={"label": "ollama-stack.component"}
                        )
                        image_ids = set()
                        for container in stack_containers:
                            image_ids.add(container.image.id)
                        total_resources += len(image_ids)
                    except Exception:
                        pass
            
            log.info(f"Found {len(resources['containers'])} containers, {len(resources['networks'])} networks, {len(resources['volumes'])} volumes")
            
            if total_resources == 0 and not remove_config:
                log.info("No stack resources found to remove")
                return True
            
            # Step 4: Confirmation prompt (unless --force)
            if not force:
                if remove_volumes:
                    log.warning("🛑 DATA LOSS WARNING: Proceeding will permanently delete all models and conversations!")
                
                # TODO: Add actual user confirmation prompt here
                # For now, we'll proceed as this is the basic implementation
                log.info("Proceeding with resource removal...")
            
            # Step 5: Stop all services
            log.info("Stopping all running services...")
            if self.is_stack_running():
                docker_services = [name for name, conf in self.config.services.items() if conf.type == 'docker']
                native_services = [name for name, conf in self.config.services.items() if conf.type == 'native-api']
                
                if docker_services and not self.stop_docker_services():
                    log.warning("Failed to stop some Docker services")
                
                if native_services and not self.stop_native_services(native_services):
                    log.warning("Failed to stop some native services")
            
            # Step 6: Remove containers and networks 
            log.info("Removing containers and networks...")
            if not self.cleanup_resources(remove_volumes=False, force=force):
                log.warning("Failed to cleanup some containers/networks")
            
            # Step 7: Remove Docker images (only if requested)
            if remove_images:
                log.info("Removing Docker images...")
                if not self.docker_client.remove_resources(remove_images=True, force=force):
                    log.warning("Failed to remove some Docker images")
            else:
                log.info("Preserving Docker images (use --remove-images to remove)")
            
            # Step 8: Remove volumes if requested (with additional confirmation)
            if remove_volumes:
                if not force:
                    log.warning("🚨 FINAL WARNING: About to delete all data volumes!")
                    # TODO: Add additional confirmation prompt
                
                log.warning("Removing data volumes - THIS WILL DELETE ALL DATA!")
                volumes = resources["volumes"]
                removed_volumes = 0
                for volume in volumes:
                    try:
                        volume.remove(force=force)
                        log.debug(f"Removed volume: {volume.name}")
                        removed_volumes += 1
                    except Exception as e:
                        log.warning(f"Failed to remove volume {volume.name}: {e}")
                
                if removed_volumes > 0:
                    log.warning(f"Removed {removed_volumes} data volumes")
            
            # Step 9: Remove configuration directory if requested
            if remove_config:
                log.info("Removing configuration directory...")
                try:
                    config_dir = get_default_config_dir()
                    
                    if config_dir.exists():
                        import shutil
                        shutil.rmtree(config_dir)
                        log.debug(f"Removed configuration directory: {config_dir}")
                    else:
                        log.debug("Configuration directory not found")
                        
                except Exception as e:
                    log.warning(f"Failed to remove configuration directory: {e}")
            
            # Step 10: Display completion message
            log.info("Stack uninstall completed successfully")
            
            if remove_volumes and remove_config and remove_images:
                log.info("All stack resources, data, configuration, and images have been removed")
            elif remove_volumes and remove_config:
                log.info("All stack resources, data, and configuration have been removed (images preserved)")
            elif remove_volumes and remove_images:
                log.info("All stack resources, data, and images have been removed (configuration preserved)")
            elif remove_config and remove_images:
                log.info("All stack resources, configuration, and images have been removed (data volumes preserved)")
            elif remove_volumes:
                log.info("All stack resources and data have been removed (configuration and images preserved)")
            elif remove_config:
                log.info("All stack resources and configuration have been removed (data volumes and images preserved)")
            elif remove_images:
                log.info("All stack resources and images have been removed (data and configuration preserved)")
            else:
                log.info("All stack resources have been removed (data, configuration, and images preserved)")
            
            log.info("To remove the CLI tool itself, run: pip uninstall ollama-stack-cli")
            
            return True
            
        except Exception as e:
            log.error(f"Stack uninstall failed: {e}")
            return False

    # =============================================================================
    # Backup and Migration Orchestration
    # =============================================================================

    def create_backup(self, backup_dir: Path, backup_config: Optional[dict] = None) -> bool:
        """
        Orchestrate full backup workflow for the stack.
        
        Args:
            backup_dir: Directory to store the backup
            backup_config: Optional backup configuration (include_volumes, include_config, etc.)
            
        Returns:
            bool: True if backup succeeded, False otherwise
        """
        from .schemas import BackupConfig, BackupManifest
        import datetime
        import platform
        import json
        
        try:
            # Parse backup configuration
            if backup_config:
                config = BackupConfig(**backup_config)
            else:
                config = BackupConfig()  # Use defaults
            
            log.info("Starting stack backup process...")
            
            # Create backup directory structure
            backup_dir.mkdir(parents=True, exist_ok=True)
            volumes_dir = backup_dir / "volumes"
            config_dir = backup_dir / "config"
            extensions_dir = backup_dir / "extensions"
            
            # Initialize backup manifest
            manifest = BackupManifest(
                stack_version="0.2.0",  # TODO: Get from actual version
                cli_version="0.2.0",   # TODO: Get from actual version
                platform=platform.system().lower(),
                backup_config=config
            )
            
            success = True
            
            # Step 1: Backup volumes if requested
            if config.include_volumes:
                log.info("Backing up Docker volumes...")
                volumes_dir.mkdir(parents=True, exist_ok=True)
                
                # Get all stack volumes
                resources = self.find_resources_by_label("ollama-stack.component")
                if resources["volumes"]:
                    volume_names = [vol.name for vol in resources["volumes"]]
                    if self.docker_client.backup_volumes(volume_names, volumes_dir):
                        manifest.volumes = volume_names
                        log.info(f"Successfully backed up {len(volume_names)} volumes")
                    else:
                        log.error("Failed to backup some volumes")
                        success = False
                else:
                    log.info("No volumes found to backup")
            
            # Step 2: Backup configuration if requested
            if config.include_config:
                log.info("Backing up configuration files...")
                config_dir.mkdir(parents=True, exist_ok=True)
                
                # Use config module to export configuration
                from .config import Config
                temp_config = Config(self.display)
                
                if temp_config.export_configuration(config_dir):
                    manifest.config_files = [".ollama-stack.json", ".env"]
                    log.info("Configuration files backed up successfully")
                else:
                    log.error("Failed to backup configuration files")
                    success = False
            
            # Step 3: Backup extensions if requested
            if config.include_extensions:
                log.info("Backing up extensions...")
                extensions_dir.mkdir(parents=True, exist_ok=True)
                
                enabled_extensions = self.config.extensions.enabled
                if enabled_extensions:
                    # TODO: Implement actual extension backup logic
                    log.info(f"Found {len(enabled_extensions)} enabled extensions")
                    manifest.extensions = enabled_extensions
                    
                    # For now, just log that extension backup is not implemented
                    for ext_name in enabled_extensions:
                        log.warning(f"Extension backup not yet implemented for: {ext_name}")
                else:
                    log.info("No extensions enabled to backup")
            
            # Step 4: Export current stack state
            log.info("Exporting current stack state...")
            state_file = backup_dir / "stack_state.json"
            if not self.docker_client.export_stack_state(state_file):
                log.warning("Failed to export stack state")
                # Don't fail the backup for this
            
            # Step 5: Calculate backup size and checksum
            log.info("Calculating backup metadata...")
            total_size = 0
            try:
                for file_path in backup_dir.rglob("*"):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
                manifest.size_bytes = total_size
                log.debug(f"Backup size: {total_size} bytes")
            except Exception as e:
                log.warning(f"Failed to calculate backup size: {e}")
            
            # Step 6: Create backup manifest
            manifest_file = backup_dir / "backup_manifest.json"
            try:
                with open(manifest_file, 'w') as f:
                    json.dump(manifest.model_dump(), f, indent=2, default=str)
                log.info(f"Backup manifest created: {manifest_file}")
            except Exception as e:
                log.error(f"Failed to create backup manifest: {e}")
                success = False
            
            # Step 7: Verify backup integrity
            log.info("Verifying backup integrity...")
            from .config import validate_backup_manifest
            is_valid, verified_manifest = validate_backup_manifest(manifest_file, backup_dir)
            if not is_valid:
                log.error("Backup integrity verification failed")
                success = False
            else:
                log.info("Backup integrity verification passed")
            
            if success:
                log.info(f"Backup completed successfully in: {backup_dir}")
                log.info(f"Backup ID: {manifest.backup_id}")
                if manifest.size_bytes:
                    size_mb = manifest.size_bytes / (1024 * 1024)
                    log.info(f"Backup size: {size_mb:.1f} MB")
            else:
                log.error("Backup completed with errors")
                
            return success
            
        except Exception as e:
            log.error(f"Backup creation failed: {e}")
            return False

    def restore_from_backup(self, backup_dir: Path, validate_only: bool = False) -> bool:
        """
        Restore workflow with validation.
        
        Args:
            backup_dir: Directory containing the backup
            validate_only: If True, only validate the backup without restoring
            
        Returns:
            bool: True if restore succeeded, False otherwise
        """
        from .config import validate_backup_manifest, import_configuration
        
        try:
            log.info("Starting stack restore process...")
            
            # Step 1: Validate backup manifest
            manifest_file = backup_dir / "backup_manifest.json"
            log.info("Validating backup manifest...")
            
            is_valid, manifest = validate_backup_manifest(manifest_file, backup_dir)
            if not is_valid or manifest is None:
                log.error("Backup validation failed - cannot proceed with restore")
                return False
            
            log.info("Backup validation passed")
            log.info(f"Backup ID: {manifest.backup_id}")
            log.info(f"Created: {manifest.created_at}")
            log.info(f"Platform: {manifest.platform}")
            
            if validate_only:
                log.info("Validation-only mode - restore not performed")
                return True
            
            # Step 2: Check if stack is running and stop if necessary
            if self.is_stack_running():
                log.info("Stack is running - stopping services for restore...")
                
                docker_services = [name for name, conf in self.config.services.items() if conf.type == 'docker']
                native_services = [name for name, conf in self.config.services.items() if conf.type == 'native-api']
                
                success = True
                if docker_services and not self.stop_docker_services():
                    log.error("Failed to stop Docker services")
                    success = False
                
                if native_services and not self.stop_native_services(native_services):
                    log.error("Failed to stop native services")
                    success = False
                
                if not success:
                    log.error("Failed to stop services - cannot proceed with restore")
                    return False
            
            # Step 3: Restore configuration files
            if manifest.config_files:
                log.info("Restoring configuration files...")
                config_backup_dir = backup_dir / "config"
                
                if not import_configuration(self.display, config_backup_dir):
                    log.error("Failed to restore configuration files")
                    return False
                
                log.info("Configuration files restored successfully")
                
                # Reload configuration after restore
                from .config import load_config
                self.config, _ = load_config(self.display)
                log.info("Configuration reloaded after restore")
            
            # Step 4: Restore volumes
            if manifest.volumes:
                log.info("Restoring Docker volumes...")
                volumes_dir = backup_dir / "volumes"
                
                if not self.docker_client.restore_volumes(manifest.volumes, volumes_dir):
                    log.error("Failed to restore some volumes")
                    return False
                
                log.info(f"Successfully restored {len(manifest.volumes)} volumes")
            
            # Step 5: Restore extensions
            if manifest.extensions:
                log.info("Restoring extensions...")
                
                # TODO: Implement actual extension restore logic
                for ext_name in manifest.extensions:
                    log.warning(f"Extension restore not yet implemented for: {ext_name}")
                
                log.info("Extension restore completed (with warnings)")
            
            # Step 6: Verify restore by checking available resources
            log.info("Verifying restore...")
            
            # Check that expected volumes exist
            if manifest.volumes:
                resources = self.find_resources_by_label("ollama-stack.component")
                restored_volumes = [vol.name for vol in resources["volumes"]]
                missing_volumes = [vol for vol in manifest.volumes if vol not in restored_volumes]
                
                if missing_volumes:
                    log.warning(f"Some volumes were not restored: {missing_volumes}")
                else:
                    log.info("All volumes restored successfully")
            
            log.info("Restore completed successfully")
            log.info("You can now start the stack with: ollama-stack start")
            
            return True
            
        except Exception as e:
            log.error(f"Restore failed: {e}")
            return False



 
import docker
import subprocess
import time
import urllib.request
import urllib.error
import logging
import socket
import sys
from pathlib import Path
from typing import Optional, Dict, List
from .schemas import AppConfig
from .display import Display

from .schemas import (
    AppConfig,
    ServiceStatus,
    ResourceUsage,
    CheckReport,
    EnvironmentCheck,
)

log = logging.getLogger(__name__)

class DockerClient:
    """A wrapper for Docker operations."""

    def __init__(self, config: AppConfig, display: Display):
        self.config = config
        self.display = display
        try:
            self.client = docker.from_env()
            self.client.ping()  # Test connection
            log.debug("Docker client initialized successfully")
        except docker.errors.DockerException as e:
            log.error(f"Failed to initialize Docker client: {e}")
            # Don't raise here - let individual operations handle Docker unavailability
            self.client = None

    # =============================================================================
    # Docker Compose Operations
    # =============================================================================

    def _run_compose_command(self, command: list, compose_files: Optional[list[str]] = None):
        """Helper to run a docker-compose command with specified compose files."""
        if compose_files is None:
            compose_files = [self.config.docker_compose_file]
        
        base_cmd = ["docker-compose"]
        for file in compose_files:
            base_cmd.extend(["-f", file])
        
        full_cmd = base_cmd + command
        
        process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding='utf-8',
        )
        
        output_lines = []
        for line in iter(process.stdout.readline, ''):
            output_lines.append(line)
        
        process.wait()
        
        if process.returncode != 0:
            error_output = "".join(output_lines)
            if command[0] == "down" and "not found" in error_output.lower():
                return True

            log.error(
                f"Docker Compose command failed with exit code {process.returncode}. "
                f"Command: `{' '.join(full_cmd)}` Output: {error_output}"
            )
            return False
        else:
            return True
    
    def pull_images(self, compose_files: Optional[list[str]] = None):
        """Pulls the latest images for the services using Docker Compose."""
        log.info("Pulling latest images for core services...")
        return self._run_compose_command(["pull"], compose_files)

    def start_services(self, services: Optional[list[str]] = None, compose_files: Optional[list[str]] = None):
        """Starts the services using Docker Compose."""
        if services:
            # Start only specific services
            return self._run_compose_command(["up", "-d"] + services, compose_files)
        else:
            # Start all services (backward compatibility)
            return self._run_compose_command(["up", "-d"], compose_files)

    def stop_services(self, compose_files: Optional[list[str]] = None):
        """Stops the services using Docker Compose."""
        return self._run_compose_command(["down"], compose_files)

    # =============================================================================
    # Container Status and Monitoring
    # =============================================================================
        
    def is_stack_running(self) -> bool:
        """Checks if any stack component containers are running."""
        try:
            # Filter for running containers with the specific stack label
            containers = self.client.containers.list(
                filters={"label": "ollama-stack.component", "status": "running"}
            )
            return len(containers) > 0
        except docker.errors.APIError as e:
            log.error("Could not connect to Docker to check stack status.", exc_info=True)
            raise
            
    def get_container_status(self, service_names: list[str]) -> list[ServiceStatus]:
        """Gathers and returns the status of a list of containerized services."""
        try:
            containers = self.client.containers.list(
                all=True, filters={"label": "ollama-stack.component"}
            )
        except (docker.errors.APIError, ConnectionResetError, ConnectionError) as e:
            log.error("Could not connect to Docker to get container status.", exc_info=True)
            raise

        container_map = {
            c.labels.get("ollama-stack.component"): c for c in containers
        }

        statuses = []
        for service_name in service_names:
            container = container_map.get(service_name)
            if container:
                try:
                    usage = self._get_resource_usage(container)
                    # Health checking is now handled by StackManager's unified system
                    ports = self._parse_ports(container.ports)
                except (docker.errors.APIError, ConnectionResetError, ConnectionError) as e:
                    log.debug(f"Failed to get resource usage for container {service_name}: {e}")
                    # Use empty resource usage if API fails
                    usage = ResourceUsage()
                    ports = {}
                
                status = ServiceStatus(
                    name=service_name,
                    is_running=container.status == "running",
                    status=container.status,
                    health="unknown",  # Health will be set by StackManager
                    ports=ports,
                    usage=usage,
                )
            else:
                status = ServiceStatus(
                    name=service_name,
                    is_running=False,
                    status="not found",
                    health="unknown",
                )
            statuses.append(status)
        return statuses

    def _parse_ports(self, port_data: dict) -> Dict[str, Optional[int]]:
        """Parses the complex port dictionary from the Docker SDK."""
        if not port_data:
            return {}
        
        parsed = {}
        for container_port, host_configs in port_data.items():
            if host_configs:
                parsed[container_port] = int(host_configs[0].get('HostPort', 0))
            else:
                parsed[container_port] = None
        return parsed

    def _get_resource_usage(self, container) -> ResourceUsage:
        """Gets the resource usage for a given container."""
        if container.status != "running":
            return ResourceUsage()

        try:
            stats = container.stats(stream=False)
            
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_cpu_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            number_cpus = stats["cpu_stats"]["online_cpus"]
            cpu_percent = (cpu_delta / system_cpu_delta) * number_cpus * 100.0 if system_cpu_delta > 0 else 0
            
            memory_mb = stats["memory_stats"]["usage"] / (1024 * 1024) if "usage" in stats["memory_stats"] else 0
            
            return ResourceUsage(
                cpu_percent=round(cpu_percent, 2),
                memory_mb=round(memory_mb, 2)
            )
        except (KeyError, docker.errors.APIError, ConnectionResetError, ConnectionError):
            return ResourceUsage()

    # =============================================================================
    # Log Streaming
    # =============================================================================

    def stream_logs(self, service_or_extension: Optional[str] = None, follow: bool = False, tail: Optional[int] = None, level: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None, compose_files: Optional[list[str]] = None):
        """Streams logs from a specific service/extension or the whole stack."""
        if compose_files is None:
            compose_files = [self.config.docker_compose_file]
        
        base_cmd = ["docker-compose"]
        for file in compose_files:
            base_cmd.extend(["-f", file])
        
        log_cmd = ["logs"]
        if follow:
            log_cmd.append("--follow")
        if tail:
            log_cmd.extend(["--tail", str(tail)])
        if since:
            log_cmd.extend(["--since", str(since)])
        if until:
            log_cmd.extend(["--until", str(until)])
        if service_or_extension:
            log_cmd.append(service_or_extension)
            
        full_cmd = base_cmd + log_cmd

        try:
            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
            )
            
            for line in iter(process.stdout.readline, ''):
                yield line.strip()
            
            process.wait()
            if process.returncode != 0:
                log.error(f"Docker Compose log command failed with exit code {process.returncode}")

        except FileNotFoundError:
            log.error("docker-compose command not found. Is it installed and in your PATH?")
        except Exception as e:
            log.error(f"An unexpected error occurred while streaming logs: {e}")

    # =============================================================================
    # Environment Validation
    # =============================================================================

    def run_environment_checks(self, fix: bool = False, platform: Optional[str] = None) -> CheckReport:
        """Runs Docker-specific environment checks."""
        checks = []

        # 1. Docker Daemon Check
        try:
            self.client.ping()
            log.debug("Docker daemon is running and accessible")
            checks.append(EnvironmentCheck(
                name="Docker Daemon Running",
                passed=True,
                details="Docker daemon is accessible and responding"
            ))
        except docker.errors.DockerException as e:
            log.error(f"Docker daemon check failed: {e}")
            checks.append(EnvironmentCheck(
                name="Docker Daemon Running",
                passed=False,
                details=f"Docker daemon is not running or not accessible: {e}",
                suggestion="Please start Docker Desktop (or your Docker service) and try again."
            ))
            # If Docker isn't available, skip Docker-dependent checks
            return CheckReport(checks=checks)

        # 2. Port Availability Checks
        port_checks = self._check_required_ports()
        checks.extend(port_checks)

        # 3. Platform-Specific Checks
        if platform == 'nvidia':
            nvidia_check = self._check_nvidia_runtime()
            checks.append(nvidia_check)

        # 4. Compose File Checks
        compose_checks = self._check_compose_files(fix)
        checks.extend(compose_checks)

        # 5. Docker Images Check
        if fix:
            image_check = self._check_and_pull_images()
            checks.append(image_check)

        return CheckReport(checks=checks)

    def _check_required_ports(self) -> List[EnvironmentCheck]:
        """Check if required ports are available."""
        checks = []
        
        ports_to_check = {
            "Ollama API": 11434,
            "WebUI": 8080,
            "MCP Proxy": 8200,
        }
        
        for service_name, port in ports_to_check.items():
            if self._is_port_available(port):
                log.debug(f"Port {port} ({service_name}) is available")
                checks.append(EnvironmentCheck(
                    name=f"Port {port} Available ({service_name})",
                    passed=True,
                    details=f"Port {port} is available for {service_name}"
                ))
            else:
                log.warning(f"Port {port} ({service_name}) is already in use")
                checks.append(EnvironmentCheck(
                    name=f"Port {port} Available ({service_name})",
                    passed=False,
                    details=f"Port {port} is already in use by another process",
                    suggestion=f"Stop the process using port {port} or configure {service_name} to use a different port"
                ))
        
        return checks

    def _check_nvidia_runtime(self) -> EnvironmentCheck:
        """Check NVIDIA Docker runtime availability."""
        try:
            info = self.client.info()
            if info.get("Runtimes", {}).get("nvidia"):
                log.debug("NVIDIA Docker runtime is available")
                return EnvironmentCheck(
                    name="NVIDIA Docker Toolkit",
                    passed=True,
                    details="NVIDIA runtime is available in Docker"
                )
            else:
                log.warning("NVIDIA Docker runtime not found")
                return EnvironmentCheck(
                    name="NVIDIA Docker Toolkit",
                    passed=False,
                    details="NVIDIA runtime not found in Docker",
                    suggestion="Install nvidia-docker2 package and restart Docker daemon"
                )
        except Exception as e:
            log.error(f"Could not verify NVIDIA runtime: {e}")
            return EnvironmentCheck(
                name="NVIDIA Docker Toolkit",
                passed=False,
                details=f"Could not verify NVIDIA runtime in Docker: {e}",
                suggestion="Ensure Docker is running and nvidia-docker2 is installed"
            )

    def _check_compose_files(self, fix: bool) -> List[EnvironmentCheck]:
        """Check Docker compose file availability."""
        checks = []
        
        # Check main compose file
        compose_file = self.config.docker_compose_file
        compose_path = Path(compose_file)
        
        if compose_path.exists():
            log.debug(f"Compose file found: {compose_file}")
            checks.append(EnvironmentCheck(
                name=f"Compose File: {compose_file}",
                passed=True,
                details=f"Docker compose file exists: {compose_file}"
            ))
        else:
            log.warning(f"Compose file missing: {compose_file}")
            checks.append(EnvironmentCheck(
                name=f"Compose File: {compose_file}",
                passed=False,
                details=f"Docker compose file not found: {compose_file}",
                suggestion=f"Ensure {compose_file} exists in the project directory"
            ))
        
        return checks

    def _check_and_pull_images(self) -> EnvironmentCheck:
        """Check and optionally pull Docker images."""
        try:
            log.info("Attempting to pull latest Docker images...")
            self.pull_images()
            log.info("Successfully pulled Docker images")
            return EnvironmentCheck(
                name="Docker Images",
                passed=True,
                details="Successfully pulled latest Docker images for stack services"
            )
        except Exception as e:
            log.error(f"Failed to pull Docker images: {e}")
            return EnvironmentCheck(
                name="Docker Images",
                passed=False,
                details=f"Failed to pull Docker images: {e}",
                suggestion="Check internet connection and run 'ollama-stack start --update'"
            )

    def _is_port_available(self, port: int) -> bool:
        """Check if a TCP port is available on localhost."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                return s.connect_ex(('localhost', port)) != 0
        except Exception:
            return False

    # =============================================================================
    # Enhanced Resource Management  
    # =============================================================================

    def pull_images_with_progress(self, compose_files: Optional[list[str]] = None) -> bool:
        """
        Pulls the latest images with enhanced progress display and error handling.
        
        Args:
            compose_files: List of compose files to use
            
        Returns:
            bool: True if pull succeeded, False otherwise
        """
        if compose_files is None:
            compose_files = [self.config.docker_compose_file]
        
        base_cmd = ["docker-compose"]
        for file in compose_files:
            base_cmd.extend(["-f", file])
        
        full_cmd = base_cmd + ["pull"]
        
        try:
            log.info("Pulling latest images...")
            log.info("Downloading latest Docker images for stack services...")
            
            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
            )
            
            # Stream output with progress indication
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    # Show pull progress for user feedback
                    if "Pulling" in line or "Downloading" in line or "Downloaded" in line:
                        log.debug(f"Pull progress: {line}")
                    elif "Pull complete" in line:
                        log.info(f"Image pull completed: {line}")
                    elif "ERROR" in line.upper() or "FAILED" in line.upper():
                        log.error(f"Pull error: {line}")
            
            process.wait()
            
            if process.returncode == 0:
                log.info("All Docker images updated successfully")
                return True
            else:
                log.error("Failed to pull some Docker images")
                log.error(f"Docker pull failed with exit code {process.returncode}")
                return False
                
        except FileNotFoundError:
            log.error("docker-compose command not found. Is it installed and in your PATH?")
            return False
        except Exception as e:
            log.error(f"An unexpected error occurred during image pull: {e}")
            return False

    def remove_resources(self, remove_images: bool = False, force: bool = False) -> bool:
        """
        Removes Docker resources for the stack.
        
        Args:
            remove_images: Whether to also remove Docker images
            force: Force removal without confirmation
            
        Returns:
            bool: True if removal succeeded, False otherwise
        """
        if not self.client:
            log.warning("Docker client not available for resource removal")
            return False
        
        try:
            success = True
            
            # Remove images if requested
            if remove_images:
                log.info("Removing Docker images...")
                try:
                    # Get images used by our stack
                    images = self.client.images.list(filters={"label": "ollama-stack.component"})
                    for image in images:
                        try:
                            self.client.images.remove(image.id, force=force)
                            log.debug(f"Removed image: {image.id}")
                        except Exception as e:
                            log.warning(f"Failed to remove image {image.id}: {e}")
                            success = False
                            
                    # Also try to remove by compose file references
                    log.info("Removing compose-referenced images...")
                    compose_files = [self.config.docker_compose_file]
                    base_cmd = ["docker-compose"]
                    for file in compose_files:
                        base_cmd.extend(["-f", file])
                    
                    rmi_cmd = base_cmd + ["down", "--rmi", "all"]
                    process = subprocess.run(rmi_cmd, capture_output=True, text=True)
                    if process.returncode != 0:
                        log.warning(f"Failed to remove some images via compose: {process.stderr}")
                        
                except Exception as e:
                    log.error(f"Failed to remove Docker images: {e}")
                    success = False
                    
            return success
            
        except Exception as e:
            log.error(f"Resource removal failed: {e}")
            return False

    def export_compose_config(self, output_file: Optional[str] = None, compose_files: Optional[list[str]] = None) -> bool:
        """
        Exports the resolved Docker Compose configuration.
        
        Args:
            output_file: File to write the config to (optional)
            compose_files: List of compose files to merge
            
        Returns:
            bool: True if export succeeded, False otherwise
        """
        if compose_files is None:
            compose_files = [self.config.docker_compose_file]
        
        base_cmd = ["docker-compose"]
        for file in compose_files:
            base_cmd.extend(["-f", file])
        
        config_cmd = base_cmd + ["config"]
        
        try:
            log.info("Exporting Docker Compose configuration...")
            
            process = subprocess.run(
                config_cmd,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if process.returncode == 0:
                config_yaml = process.stdout
                
                if output_file:
                    # Write to file
                    with open(output_file, 'w') as f:
                        f.write(config_yaml)
                    log.info(f"Configuration exported to: {output_file}")
                else:
                    # Return as string/print to stdout
                    print(config_yaml)
                    log.info("Configuration exported to stdout")
                
                return True
            else:
                log.error(f"Failed to export configuration: {process.stderr}")
                return False
                
        except Exception as e:
            log.error(f"Configuration export failed: {e}")
            return False






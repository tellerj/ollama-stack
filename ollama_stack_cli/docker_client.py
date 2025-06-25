import platform
import docker
import subprocess
import time
import urllib.request
import urllib.error
import logging
from .schemas import AppConfig
from .display import Display
import socket
from typing import Optional, Dict

from .schemas import (
    AppConfig,
    StackStatus,
    ServiceStatus,
    ExtensionStatus,
    ResourceUsage,
    CheckReport,
    EnvironmentCheck,
)

log = logging.getLogger(__name__)

class DockerClient:
    """A wrapper for Docker operations."""

    HEALTH_CHECK_URLS = {
        "ollama": "http://localhost:11434",
        "webui": "http://localhost:8080",
        "mcp_proxy": "http://localhost:8200",
    }
    HEALTH_CHECK_TIMEOUT = 30  # seconds
    HEALTH_CHECK_INTERVAL = 5  # seconds

    def __init__(self, config: AppConfig, display: Display):
        self.config = config
        self.display = display
        try:
            self.client = docker.from_env()
            self.client.ping()
        except docker.errors.DockerException:
            log.error(
                "Docker is not running or not configured correctly. Please ensure the Docker daemon is running.",
                exc_info=True
            )
            raise
        self.platform = self.detect_platform()

    def detect_platform(self) -> str:
        """Detects the current platform (apple, nvidia, or cpu)."""
        system = platform.system()
        machine = platform.machine()

        if system == "Darwin" and machine == "arm64":
            log.info("Apple Silicon platform detected.")
            return "apple"
        
        try:
            info = self.client.info()
            if info.get("Runtimes", {}).get("nvidia"):
                log.info("NVIDIA GPU platform detected.")
                return "nvidia"
        except Exception:
            log.warning("Could not get Docker info to check for NVIDIA runtime.")

        log.info("Defaulting to CPU platform.")
        return "cpu"

    def get_compose_file(self) -> list[str]:
        """Determines the appropriate docker-compose file to use."""
        compose_files = [self.config.docker_compose_file]
        
        platform_config = self.config.platform.get(self.platform)
        if platform_config:
            compose_files.append(platform_config.compose_file)
            log.info(f"Using platform-specific compose file: {platform_config.compose_file}")
        
        return compose_files

    def _run_compose_command(self, command: list):
        """Helper to run a docker-compose command."""
        base_cmd = ["docker-compose"]
        for file in self.get_compose_file():
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

            self.display.error(
                f"Docker Compose command failed with exit code {process.returncode}.",
                suggestion=f"Command: `{' '.join(full_cmd)}`\n\n[bold]Output:[/]\n{error_output}"
            )
            return False
        else:
            return True
    
    def pull_images(self):
        """Pulls the latest images for the services using Docker Compose."""
        log.info("Pulling latest images for core services...")
        return self._run_compose_command(["pull"])

    def start_services(self, services: Optional[list[str]] = None):
        """Starts the services using Docker Compose."""
        if services:
            # Start only specific services
            self._run_compose_command(["up", "-d"] + services)
        else:
            # Start all services (backward compatibility)
            self._run_compose_command(["up", "-d"])

    def stop_services(self):
        """Stops the services using Docker Compose."""
        self._run_compose_command(["down"])
        
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
        except docker.errors.APIError as e:
            log.error("Could not connect to Docker to get container status.", exc_info=True)
            raise

        container_map = {
            c.labels.get("ollama-stack.component"): c for c in containers
        }

        statuses = []
        for service_name in service_names:
            container = container_map.get(service_name)
            if container:
                usage = self._get_resource_usage(container)
                health = self._get_service_health(service_name)
                ports = self._parse_ports(container.ports)
                
                status = ServiceStatus(
                    name=service_name,
                    is_running=container.status == "running",
                    status=container.status,
                    health=health,
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
            
            return ResourceUsage(cpu_percent=round(cpu_percent, 2), memory_mb=round(memory_mb, 2))
        except (KeyError, docker.errors.APIError):
            return ResourceUsage()

    def _get_service_health(self, service_name: str) -> str:
        """Performs a quick health check for a single service."""
        url = self.HEALTH_CHECK_URLS.get(service_name)
        if not url:
            return "unknown"
        
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return "healthy" if 200 <= response.status < 300 else "unhealthy"
        except (urllib.error.URLError, ConnectionRefusedError, socket.timeout):
            return "unhealthy"

    def stream_logs(self, service_or_extension: Optional[str] = None, follow: bool = False, tail: Optional[int] = None, level: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None):
        """Streams logs from a specific service/extension or the whole stack."""
        base_cmd = ["docker-compose"]
        for file in self.get_compose_file():
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
                yield f"[ERROR] Log command failed with exit code {process.returncode}."

        except FileNotFoundError:
            yield "[ERROR] `docker-compose` command not found. Is it installed and in your PATH?"
        except Exception as e:
            yield f"[ERROR] An unexpected error occurred: {e}"


    def _check_port(self, port: int) -> bool:
        """Checks if a TCP port is available."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0

    def run_environment_checks(self, fix: bool = False, verbose: bool = False) -> CheckReport:
        """Runs checks for the environment and returns a report."""
        checks = []

        try:
            docker_running = self.client.ping()
            checks.append(EnvironmentCheck(name="Docker Daemon Running", passed=docker_running))
        except docker.errors.DockerException:
            checks.append(EnvironmentCheck(name="Docker Daemon Running", passed=False, details="Docker is not running."))
            return CheckReport(checks=checks)

        ports_to_check = {
            "Ollama API Port (11434)": 11434,
            "WebUI Port (8080)": 8080,
            "MCP Proxy Port (8200)": 8200,
        }
        for name, port in ports_to_check.items():
            if self._check_port(port):
                checks.append(EnvironmentCheck(name=f"Port {port} Available", passed=True))
            else:
                checks.append(EnvironmentCheck(
                    name=f"Port {port} Available",
                    passed=False,
                    details=f"Port {port} is already in use."
                ))

        if self.platform == 'nvidia':
            try:
                info = self.client.info()
                if info.get("Runtimes", {}).get("nvidia"):
                     checks.append(EnvironmentCheck(name="NVIDIA Docker Toolkit", passed=True))
                else:
                    checks.append(EnvironmentCheck(name="NVIDIA Docker Toolkit", passed=False, details="NVIDIA runtime not found in Docker."))
            except Exception:
                checks.append(EnvironmentCheck(name="NVIDIA Docker Toolkit", passed=False, details="Could not verify NVIDIA runtime in Docker."))

        return CheckReport(checks=checks)




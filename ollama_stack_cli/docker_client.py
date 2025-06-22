import platform
import docker
import subprocess
import time
import urllib.request
import urllib.error
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
            self.display.error(
                "Docker is not running or not configured correctly.",
                suggestion="Please ensure the Docker daemon is running.",
            )
            raise
        self.platform = self.detect_platform()

    def detect_platform(self) -> str:
        """Detects the current platform (apple, nvidia, or cpu)."""
        system = platform.system()
        machine = platform.machine()

        if system == "Darwin" and machine == "arm64":
            self.display.info("Apple Silicon platform detected.")
            return "apple"
        
        try:
            info = self.client.info()
            if info.get("Runtimes", {}).get("nvidia"):
                self.display.info("NVIDIA GPU platform detected.")
                return "nvidia"
        except Exception:
            self.display.warning("Could not get Docker info to check for NVIDIA runtime.")

        self.display.info("Defaulting to CPU platform.")
        return "cpu"

    def get_compose_file(self) -> str:
        """Determines the appropriate docker-compose file to use."""
        compose_files = [self.config.docker_compose_file]
        
        platform_config = self.config.platform.get(self.platform)
        if platform_config:
            compose_files.append(platform_config.compose_file)
            self.display.info(f"Using platform-specific compose file: {platform_config.compose_file}")
        
        return compose_files

    def _run_compose_command(self, command: list):
        """Helper to run a docker-compose command."""
        base_cmd = ["docker-compose"]
        for file in self.get_compose_file():
            base_cmd.extend(["-f", file])
        
        full_cmd = base_cmd + command
        
        self.display.info(f"Running command: {' '.join(full_cmd)}")
        
        with self.display.progress() as progress:
            task = progress.add_task(f"[cyan]Running {' '.join(command)}...", total=None)
            
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
                if self.display.verbose:
                    self.display.print(line.strip())
            
            process.wait()
            
            if process.returncode != 0:
                error_output = "".join(output_lines)
                # For the 'down' command, "not found" errors are acceptable and mean success.
                if command[0] == "down" and "not found" in error_output.lower():
                    progress.update(task, completed=True, description=f"[green]Services already stopped.")
                    return True

                progress.update(task, completed=True, description=f"[red]Failed: {' '.join(command)}.")
                self.display.error(
                    f"Docker Compose command failed with exit code {process.returncode}.",
                    suggestion=f"Command: `{' '.join(full_cmd)}`\n\n[bold]Output:[/]\n{error_output}"
                )
                return False
            else:
                progress.update(task, completed=True, description=f"[green]Finished {' '.join(command)}.")
                return True

    def _perform_health_checks(self) -> bool:
        """Polls service endpoints to confirm they are operational."""
        self.display.info("Performing health checks...")
        services_to_check = list(self.HEALTH_CHECK_URLS.keys())
        
        with self.display.progress() as progress:
            tasks = {
                service: progress.add_task(f"[cyan]Waiting for {service}...", total=100)
                for service in services_to_check
            }

            start_time = time.time()
            all_healthy = False
            while time.time() - start_time < self.HEALTH_CHECK_TIMEOUT:
                for service in list(services_to_check):
                    url = self.HEALTH_CHECK_URLS[service]
                    task_id = tasks[service]
                    try:
                        # Use a short timeout for the request itself
                        with urllib.request.urlopen(url, timeout=3) as response:
                            if 200 <= response.status < 300:
                                progress.update(task_id, completed=True, description=f"[green]{service} is healthy.")
                                services_to_check.remove(service)
                    except (urllib.error.URLError, ConnectionRefusedError, ConnectionResetError):
                        # Service is not ready yet, just continue
                        pass
                    
                    # Update progress bar to show time elapsed
                    elapsed = time.time() - start_time
                    progress.update(task_id, completed=int((elapsed / self.HEALTH_CHECK_TIMEOUT) * 100))

                if not services_to_check:
                    all_healthy = True
                    break
                
                time.sleep(self.HEALTH_CHECK_INTERVAL)

        if all_healthy:
            self.display.success("All services are healthy.")
            return True
        else:
            for service in services_to_check:
                progress.update(tasks[service], description=f"[red]{service} failed to start.")
            self.display.error(
                "One or more services failed the health check.",
                suggestion="Check the service logs with `ollama-stack logs` for more details."
            )
            return False

    def is_stack_running(self) -> bool:
        """Checks if any of the core stack services are running."""
        # On Apple Silicon, ollama doesn't run as a docker conatiner.
        core_services = (
            ["webui", "mcp_proxy"]
            if self.platform == "apple"
            else ["ollama", "webui", "mcp_proxy"]
        )

        try:
            # Use labels to reliably find running containers for our components
            containers = self.client.containers.list(
                filters={"label": "ollama-stack.component", "status": "running"}
            )
            # Get the component name from the label for each running container
            running_components = {c.labels.get("ollama-stack.component") for c in containers}

            # Check if any of the running components is a core service
            running_core_services = [s for s in core_services if s in running_components]
            
            if running_core_services:
                self.display.info(f"The following core services are already running: {', '.join(running_core_services)}")
                return True
            return False
        except docker.errors.APIError as e:
            self.display.error("Could not connect to Docker to check container status.", suggestion=str(e))
            # Treat Docker connection error as a critical failure.
            raise

    def pull_images(self):
        """Pulls the latest images for the services using Docker Compose."""
        self.display.info("Pulling latest images for core services...")
        return self._run_compose_command(["pull"])

    def start_services(self, platform: str, update: bool = False):
        """Starts the services using Docker Compose and performs health checks."""
        if self.is_stack_running():
            # If it's running, we can just show the access points.
            self.display.panel(
                (
                    "Ollama Stack is already running.\n\n"
                    f"  - Ollama API: {self.HEALTH_CHECK_URLS['ollama']}\n"
                    f"  - Open WebUI: {self.HEALTH_CHECK_URLS['webui']}\n"
                    f"  - MCP Proxy: {self.HEALTH_CHECK_URLS['mcp_proxy']}"
                ),
                title="Access Points"
            )
            return
        
        if update:
            if not self.pull_images():
                # _run_compose_command already displays an error, so we just exit.
                return

        # On Apple Silicon, remind the user to start Ollama manually.
        if platform == "apple":
            self.display.info(
                "On Apple Silicon, ensure the native Ollama application is running."
            )

        if self._run_compose_command(["up", "-d"]):
            if self._perform_health_checks():
                self.display.panel(
                    (
                        "Ollama Stack is running!\n\n"
                        f"  - Ollama API: {self.HEALTH_CHECK_URLS['ollama']}\n"
                        f"  - Open WebUI: {self.HEALTH_CHECK_URLS['webui']}\n"
                        f"  - MCP Proxy: {self.HEALTH_CHECK_URLS['mcp_proxy']}"
                    ),
                    title="Access Points"
                )

    def stop_services(self):
        """Stops the services using Docker Compose."""
        return self._run_compose_command(["down"])

    def get_container_status(self, service_names: list[str]) -> list[ServiceStatus]:
        """Gathers and returns the status of a list of containerized services."""
        services_status = []
        
        try:
            # Use labels to reliably find running containers for our components
            containers = self.client.containers.list(
                all=True, filters={"label": "ollama-stack.component"}
            )
        except docker.errors.APIError as e:
            self.display.error("Could not connect to Docker to get container status.", suggestion=str(e))
            raise

        running_containers = {c.labels.get("ollama-stack.component"): c for c in containers if c.status == 'running'}

        for service_name in service_names:
            container = running_containers.get(service_name)
            if container:
                usage = self._get_resource_usage(container)
                status = ServiceStatus(
                    name=service_name,
                    is_running=True,
                    status=container.status,
                    health=self._get_service_health(service_name),
                    ports=self._parse_ports(container.ports),
                    usage=usage,
                )
            else:
                status = ServiceStatus(name=service_name, is_running=False)
            services_status.append(status)
        
        return services_status

    def _parse_ports(self, port_data: dict) -> Dict[str, Optional[int]]:
        """Parses the complex port dictionary from the Docker SDK."""
        if not port_data:
            return {}
        
        parsed = {}
        for container_port, host_configs in port_data.items():
            if host_configs:
                # Take the first host configuration
                parsed[container_port] = int(host_configs[0].get('HostPort', 0))
            else:
                parsed[container_port] = None
        return parsed

    def _get_resource_usage(self, container) -> ResourceUsage:
        """Gets the resource usage for a given container."""
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
                if 200 <= response.status < 300:
                    return "healthy"
                else:
                    return "unhealthy"
        except (urllib.error.URLError, ConnectionRefusedError, socket.timeout):
            return "unhealthy"

    def stream_logs(self, service_or_extension: Optional[str] = None, follow: bool = False, tail: Optional[int] = None):
        """Streams logs from a specific service/extension or the whole stack."""
        # On Apple Silicon, ollama runs natively and has no container logs.
        if self.platform == "apple" and service_or_extension == "ollama":
            yield "[ERROR] Ollama runs natively on Apple Silicon. No container logs are available."
            yield "[INFO] To view logs for the native Ollama application, use the 'log' command provided by Ollama."
            return

        base_cmd = ["docker-compose"]
        for file in self.get_compose_file():
            base_cmd.extend(["-f", file])
        
        log_cmd = ["logs"]
        if follow:
            log_cmd.append("--follow")
        if tail:
            log_cmd.extend(["--tail", str(tail)])
        if service_or_extension:
            log_cmd.append(service_or_extension)
            
        full_cmd = base_cmd + log_cmd

        self.display.info(f"Streaming logs with command: {' '.join(full_cmd)}")

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

    def run_environment_checks(self) -> CheckReport:
        """Runs checks for the environment and returns a report."""
        checks = []

        # 1. Docker Daemon Status
        try:
            docker_running = self.client.ping()
            checks.append(EnvironmentCheck(
                name="Docker Daemon Running",
                passed=docker_running,
                details="Docker daemon is active and responsive." if docker_running else "Could not ping Docker daemon.",
                suggestion="Ensure the Docker daemon is started." if not docker_running else None
            ))
        except docker.errors.DockerException:
            checks.append(EnvironmentCheck(
                name="Docker Daemon Running",
                passed=False,
                details="Failed to connect to Docker daemon.",
                suggestion="Ensure Docker is installed and the daemon is running."
            ))

        # 2. API Port Availability
        api_port = 11434
        api_port_available = self._check_port(api_port)
        checks.append(EnvironmentCheck(
            name=f"Ollama API Port ({api_port}) Available",
            passed=api_port_available,
            details=f"Port {api_port} is available." if api_port_available else f"Port {api_port} is currently in use.",
            suggestion=f"Stop the process using port {api_port} or change the port mapping." if not api_port_available else None
        ))

        # 3. WebUI Port Availability
        webui_port = 8080
        webui_port_available = self._check_port(webui_port)
        checks.append(EnvironmentCheck(
            name=f"Open WebUI Port ({webui_port}) Available",
            passed=webui_port_available,
            details=f"Port {webui_port} is available." if webui_port_available else f"Port {webui_port} is currently in use.",
            suggestion=f"Stop the process using port {webui_port} or change the port mapping." if not webui_port_available else None
        ))

        # Deferring other checks like nvidia, model perms, etc. for now.

        return CheckReport(checks=checks)




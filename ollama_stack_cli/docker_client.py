import platform
import docker
import subprocess
import time
import urllib.request
import urllib.error
from .schemas import AppConfig
from .display import Display

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

    def start_services(self, update: bool = False):
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
        if self.platform == "apple":
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




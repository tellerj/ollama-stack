import urllib.request
import urllib.error
import json
import socket
import subprocess
import shutil
import logging
from typing import List, Optional

from .schemas import ServiceStatus, ResourceUsage, EnvironmentCheck
from .display import Display

log = logging.getLogger(__name__)

class OllamaApiClient:
    """A client for interacting with the native Ollama API and managing the native service."""

    def __init__(self, display: Display):
        # Initialization logic for the client, e.g., setting base URL
        self.base_url = "http://localhost:11434"
        self.display = display

    def get_status(self) -> ServiceStatus:
        """
        Gets the status of the native Ollama service by calling its API and ollama commands.
        """
        status = "N/A"
        health = "unknown"
        ports = {}
        is_running = False

        # First check if ollama command is available
        if not shutil.which("ollama"):
            return ServiceStatus(
                name="ollama (Native)",
                is_running=False,
                status="Not installed",
                health="unavailable",
                ports={},
                usage=ResourceUsage(),
            )

        # Check if ollama server is running via API
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/version", timeout=2) as response:
                if 200 <= response.status < 300:
                    health = "healthy"
                    is_running = True
                    ports = {'11434/tcp': 11434}
                    
                    # Get running models using ollama ps command
                    try:
                        result = subprocess.run(
                            ["ollama", "ps"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            # Parse ollama ps output to count running models
                            lines = result.stdout.strip().split('\n')
                            # Skip header line, count model lines
                            model_count = max(0, len([line for line in lines[1:] if line.strip()]))
                            if model_count > 0:
                                status = f"Running ({model_count} model{'s' if model_count > 1 else ''})"
                            else:
                                status = "Running (no models loaded)"
                        else:
                            status = "Running"
                    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                        status = "Running"
                else:
                    health = "unhealthy"

        except (urllib.error.URLError, socket.timeout, ConnectionRefusedError):
            health = "unhealthy"
            is_running = False
        except json.JSONDecodeError:
            log.warning("Could not parse JSON response from native Ollama API.", exc_info=True)
            health = "unhealthy"

        return ServiceStatus(
            name="ollama (Native)",
            is_running=is_running,
            status=status,
            health=health,
            ports=ports,
            usage=ResourceUsage(),  # Native API does not provide usage stats
        )

    def is_service_running(self) -> bool:
        """Check if the native Ollama service is running."""
        # Check if ollama command is available first
        if not shutil.which("ollama"):
            return False
            
        # Try process check first (fastest)
        try:
            result = subprocess.run(
                ["pgrep", "-f", "ollama serve"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
        
        # Fall back to API check
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/version", timeout=2) as response:
                return 200 <= response.status < 300
        except (urllib.error.URLError, socket.timeout, ConnectionRefusedError):
            return False

    def start_service(self) -> bool:
        """Start the native Ollama service."""
        # Check if ollama command is available
        if not shutil.which("ollama"):
            log.warning("Ollama is not installed or not in PATH. Please install Ollama.")
            return False
        
        # Check if ollama is already running
        if self.is_service_running():
            log.info("Ollama service is already running.")
            return True
        
        try:
            log.info("Starting native Ollama service...")
            # Start ollama serve in background
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            log.info("Ollama service started successfully.")
            return True
        except Exception as e:
            log.error(f"Failed to start Ollama service: {e}")
            log.info("Please start Ollama manually with: ollama serve")
            return False

    def stop_service(self) -> bool:
        """Stop the native Ollama service."""
        # Check if ollama command is available
        if not shutil.which("ollama"):
            log.warning("Ollama is not installed or not in PATH.")
            return True  # Consider success since service can't be running
        
        # Check if service is running first
        if not self.is_service_running():
            log.info("Ollama service is not running.")
            return True
        
        # Try to stop gracefully by killing the serve process
        # Note: 'ollama stop' stops models, not the server itself
        try:
            result = subprocess.run(
                ["pkill", "-f", "ollama serve"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                log.info("Ollama service stopped successfully.")
                return True
            else:
                # Process might not exist, check if service is actually stopped
                if not self.is_service_running():
                    log.info("Ollama service is now stopped.")
                    return True
                else:
                    log.warning("Failed to stop Ollama service via pkill.")
                    return False
        except subprocess.TimeoutExpired:
            log.error("Timeout while stopping Ollama service.")
            return False
        except Exception as e:
            log.error(f"Failed to stop Ollama service: {e}")
            log.info("Please stop Ollama manually (kill the 'ollama serve' process).")
            return False

    def get_logs(self, follow: bool = False, tail: Optional[int] = None, level: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None):
        r"""
        Stream logs from the native Ollama service using its dedicated log files.
        
        Ollama stores logs in platform-specific locations:
        - macOS/Linux: ~/.ollama/logs/server.log  
        - Linux (systemd): journalctl -u ollama
        - Windows: %LOCALAPPDATA%\Ollama\logs\server.log
        """
        import os
        from pathlib import Path
        
        log.debug("Accessing native Ollama service logs")
        
        # Check if ollama command is available
        if not shutil.which("ollama"):
            log.error("Ollama is not installed or not in PATH")
            return
        
        # Check if service is running
        if not self.is_service_running():
            log.warning("Ollama service is not currently running")
            log.info("Start Ollama with: ollama serve")
            return
        
        system = os.uname().sysname.lower()
        
        # Try to access Ollama's dedicated log files
        if system in ["darwin", "linux"]:
            log_file_path = Path.home() / ".ollama" / "logs" / "server.log"
            
            if system == "linux":
                # First try systemd logs if available
                try:
                    cmd = ["journalctl", "-u", "ollama", "--no-pager"]
                    if tail:
                        cmd.extend(["--lines", str(tail)])
                    if since:
                        cmd.extend(["--since", since])
                    if until:
                        cmd.extend(["--until", until])
                    if follow:
                        cmd.append("-f")
                    
                    log.info("Accessing Ollama logs via systemd journal")
                    result = subprocess.run(
                        cmd,
                        capture_output=not follow,
                        text=True,
                        timeout=None if follow else 10
                    )
                    
                    if result.returncode == 0:
                        if follow:
                            # For follow mode, we need to handle this differently
                            # Since we can't capture output, inform user to use journalctl directly
                            log.info("For real-time log following, use: journalctl -u ollama -f")
                            # Fall back to file-based approach
                        else:
                            if result.stdout.strip():
                                log.debug("Retrieved Ollama logs from systemd journal")
                                for line in result.stdout.strip().split('\n'):
                                    if line.strip():
                                        yield line.strip()
                                return
                            else:
                                log.info("No recent systemd logs found, trying log file")
                except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                    log.debug("systemd journal not available, trying log file")
            
            # Try the dedicated log file
            if log_file_path.exists():
                log.info(f"Reading Ollama logs from: {log_file_path}")
                try:
                    if follow:
                        # Use tail -f for following logs
                        process = subprocess.Popen(
                            ["tail", "-f", str(log_file_path)],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        try:
                            for line in process.stdout:
                                yield line.strip()
                        except KeyboardInterrupt:
                            process.terminate()
                    else:
                        # Read the log file directly
                        with open(log_file_path, 'r') as f:
                            lines = f.readlines()
                            
                        # Apply tail limit if specified
                        if tail and tail > 0:
                            lines = lines[-tail:]
                        
                        for line in lines:
                            line = line.strip()
                            if line:
                                yield line
                        
                        if not lines:
                            log.info("Log file is empty")
                            yield from self._get_ollama_status_output()
                            
                except (IOError, OSError) as e:
                    log.error(f"Failed to read log file {log_file_path}: {e}")
                    yield from self._get_ollama_status_output()
            else:
                log.warning(f"Ollama log file not found at: {log_file_path}")
                log.info("This may indicate Ollama hasn't been started yet or is using a different log location")
                yield from self._get_ollama_status_output()
                
        elif system == "nt":  # Windows
            log.info("Windows log access not implemented yet")
            log.info("On Windows, logs are typically in: %LOCALAPPDATA%\\Ollama\\logs\\server.log")
            yield from self._get_ollama_status_output()
        else:
            log.info(f"Log access not implemented for {system}")
            yield from self._get_ollama_status_output()
    
    def _get_ollama_status_output(self):
        """Get current ollama status as log output when actual logs aren't available."""
        try:
            result = subprocess.run(
                ["ollama", "ps"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                log.debug("Retrieved current Ollama status")
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        yield line.strip()
            else:
                log.warning("Failed to get ollama status")
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            log.error("Unable to get current ollama status")

    # =============================================================================
    # Environment Validation
    # =============================================================================

    def run_environment_checks(self, fix: bool = False) -> List[EnvironmentCheck]:
        """Run Ollama-specific environment checks for native installation."""
        checks = []
        
        # Check Ollama installation
        if shutil.which("ollama"):
            log.debug("Ollama is installed and available in PATH")
            checks.append(EnvironmentCheck(
                name="Ollama Installation (Native)",
                passed=True,
                details="Ollama is installed and available in PATH"
            ))
        else:
            log.warning("Ollama not found in PATH")
            checks.append(EnvironmentCheck(
                name="Ollama Installation (Native)",
                passed=False,
                details="Ollama command not found in PATH",
                suggestion="Install Ollama from https://ollama.ai/ for native Apple Silicon support"
            ))
        
        return checks 
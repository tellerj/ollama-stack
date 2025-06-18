from .config import AppConfig, load_config
from .display import Display
from .docker_client import DockerClient

class AppContext:
    """A context object that holds shared application state."""

    def __init__(self, verbose: bool = False):
        self.display = Display(verbose=verbose)
        self.config = load_config()
        try:
            self.docker_client = DockerClient(config=self.config, display=self.display)
        except Exception:
            # DockerClient handles its own error display. We just need to exit gracefully.
            exit(1)

    @property
    def verbose(self) -> bool:
        return self.display.verbose 
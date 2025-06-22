from .config import Config
from .display import Display
from .stack_manager import StackManager


class AppContext:
    """A central container for the application's runtime state."""

    def __init__(self, verbose: bool = False):
        self.config = Config()
        self.display = Display(verbose=verbose)
        self.stack_manager = StackManager(self.config.app_config, self.display)

    @property
    def verbose(self) -> bool:
        return self.display.verbose 
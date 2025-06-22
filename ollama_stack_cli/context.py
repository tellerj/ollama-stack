import sys
from .config import Config
from .display import Display
from .stack_manager import StackManager


class AppContext:
    """A central container for the application's runtime state."""

    def __init__(self, verbose: bool = False):
        try:
            self.display = Display(verbose=verbose)
            self.config = Config(self.display)
            self.stack_manager = StackManager(self.config.app_config, self.display)
        except Exception as e:
            # Initialize display for error reporting if possible
            if not hasattr(self, 'display'):
                self.display = Display(verbose=verbose)
            self.display.error(f"Failed to initialize application: {e}")
            sys.exit(1)

    @property
    def verbose(self) -> bool:
        return self.display.verbose 
import sys
import logging
from .config import Config
from .display import Display
from .stack_manager import StackManager

log = logging.getLogger(__name__)

class AppContext:
    """A central container for the application's runtime state."""

    def __init__(self, verbose: bool = False):
        try:
            self.display = Display(verbose=verbose)
            self.config = Config(self.display)
            self.stack_manager = StackManager(self.config.app_config, self.display)
        except Exception as e:
            # Manually create a display object for error reporting if the main one fails.
            display = Display(verbose=True) # Use verbose to ensure traceback is shown
            log.error(f"Failed to initialize application: {e}", exc_info=True)
            sys.exit(1)

    @property
    def verbose(self) -> bool:
        return self.display.verbose 
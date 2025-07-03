# Ollama Stack CLI Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 

### Changed
- 

### Fixed
- 

## [v0.3.0] - 2025-01-XX

### Added
- **New Commands**: `install` command for fresh configuration setup, `update` command for stack component updates, `uninstall` command for complete resource cleanup
- **Resource Management**: Comprehensive Docker resource discovery and cleanup with safety controls
- **Configuration Lifecycle**: Fresh configuration directory creation in `~/.ollama-stack/` with secure key generation
- **Selective Updates**: Update filtering with `--services-only` and `--extensions-only` flags
- **Update Orchestration**: Smart state management with stop → pull → restart workflow and inline updates for running stacks
- **Secure Installation**: Cryptographically secure WebUI secret key generation (64-character keys)
- **Volume Protection**: Safe uninstall with `--remove-volumes` flag to prevent accidental data loss
- **Configuration Removal**: `--remove-config` and `--all` flags for complete stack removal
- **Installation Validation**: Environment checks integrated into install workflow with detailed reporting
- **Force Operations**: `--force` flags for non-interactive automation in CI/CD environments

### Changed
- **Enhanced Stack Manager**: New `install_stack()`, `update_stack()`, `find_resources_by_label()`, `cleanup_resources()`, and `uninstall_stack()` methods
- **Docker Client Extensions**: Added `pull_images_with_progress()` and `remove_resources()` for enhanced resource management
- **Install Stack Return Type**: Changed from boolean to dictionary with detailed results including paths, check reports, and failure information
- **Architecture Compliance**: Fixed logging/display violations - core modules now use logging, command layer handles structured UI
- **Configuration Security**: Install command generates secure keys vs start command's placeholder warnings

### Fixed
- **Method Signature Consistency**: Fixed `install_stack()` return type annotation to match actual dictionary returns
- **Test Coverage**: Updated 56 install_stack tests to expect new dictionary return format
- **Display Architecture**: Removed display method calls from core modules (stack_manager, install, status) - now properly separated
- **Security Warnings**: Start command now warns when using placeholder keys and directs users to run install command

### Technical
- **Testing**: 56 updated stack manager tests + 37 install command tests + 1 install integration test
- **Resource Management**: Label-based Docker resource discovery with comprehensive cleanup workflows
- **Error Handling**: Enhanced exception handling in install/update/uninstall operations with detailed error reporting
- **Safety Features**: Multiple confirmation prompts and force flags for destructive operations
- **Architecture**: Proper separation between core logic (logging) and command layer (display)

## [v0.2.0] - 2025-01-14

### Added
- **New Commands**: `check` command for environment validation, `logs` command for service log streaming, enhanced `status` command
- **JSON Output Support**: `--json` flag across commands for programmatic usage
- **MCP Architecture**: Model Context Protocol support with extension registry system
- **Extension Support**: Dia TTS extension with comprehensive MCP integration
- **Installation Scripts**: Cross-platform install scripts (`install-ollama-stack.sh`, `install-ollama-stack.ps1`)
- **Uninstall Command**: Complete stack removal with cleanup
- **Platform Detection**: Automatic Apple Silicon, NVIDIA, and CPU platform detection
- **Configuration Management**: Platform-specific overrides and .env management
- **Unified Health Checks**: HTTP → TCP fallback system for all service types
- **Environment Validation**: Comprehensive checks for Docker, ports, images, and platform requirements

### Changed
- **BREAKING**: Complete CLI architecture refactor with Phase 1 & 2 implementation
- **Stack Manager**: Centralized service orchestration replacing client-specific logic
- **Service Configuration**: Platform-aware service type management (Docker vs native)
- **Error Handling**: Enhanced user feedback and graceful failure modes
- **Logging System**: Structured logging throughout application with proper levels
- **Docker Integration**: Improved container management with label-based operations
- **Apple Silicon Support**: Native Ollama service integration with automatic detection

### Fixed
- Docker daemon availability handling with graceful degradation
- Service health reporting accuracy aligned with Docker's internal checks
- SyntaxWarning in raw string escaping
- Integration test reliability and service lifecycle management
- Configuration loading edge cases and platform-specific paths
- Volume and network cleanup in uninstall operations

### Technical
- **Testing**: 296 unit tests + 11 integration tests with comprehensive coverage
- **Architecture**: Proper delegation patterns between StackManager and service clients
- **Code Quality**: Reduced duplication, improved separation of concerns
- **Documentation**: Comprehensive docstrings and architectural decision records
- **Dependencies**: Optimized dependency management and compatibility

## [v0.1.0] - 2025-06-18

### Added
- Core CLI application with `typer`.
- `start` command to launch the Docker Compose stack.
- `stop` command to gracefully shut down the stack.
- `restart` command to cycle the stack.
- Platform-aware logic to handle CPU, NVIDIA, and Apple Silicon environments.
- Automated health checks on startup to ensure service reliability.
- `--update` flag on the `start` command to pull the latest Docker images.
- Comprehensive unit and integration test suite using `pytest`.
- VS Code `tasks.json` for streamlined development workflows.
- Initial project structure for the `ollama-stack` CLI.
- `pyproject.toml` with dependencies and tool configuration.
- Basic CLI entry point in `main.py`. 
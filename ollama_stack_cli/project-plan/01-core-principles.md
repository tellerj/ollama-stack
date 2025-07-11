# 01: Core Principles and Behaviors

This document outlines the high-level principles that guide the design and behavior of the `ollama-stack` CLI tool and the stack it manages.

### 1. Platform-Aware Optimization

- **Principle**: The tool must be platform-agnostic at its core but adapt its configuration for optimal performance on the host system.
- **Implementation**:
    - The CLI auto-detects the host environment, prioritizing `nvidia`, then `apple` silicon, and defaulting to `cpu`.
    - Platform-specific Docker Compose files (`docker-compose.nvidia.yml`, `docker-compose.apple.yml`) are used as overrides to the base `docker-compose.yml`.
    - Users can manually override the detected platform with the `--platform` flag.

### 2. State and Configuration Integrity

- **Principle**: Configuration must be explicit, transparent, and resilient, with clear separation between environment configuration and CLI state.
- **Implementation**:
    - A `.env` file in the project's root directory is the single source of truth for Docker Compose environment variables (e.g., `PROJECT_NAME`, `WEBUI_SECRET_KEY`).
    - A `.ollama-stack.json` file stores the CLI's internal state, such as the list of enabled extensions.
    - The `PROJECT_NAME` variable generates deterministic and unique names for all Docker resources (containers, volumes, networks), preventing conflicts.
    - All file-based configuration is managed via dedicated libraries (`python-dotenv` for `.env`, Python's `json` module for JSON files) to ensure robustness.

### 3. Graceful Multi-Installation Management

- **Principle**: The tool must be aware of other `ollama-stack` installations on the same machine and help users manage them to avoid conflicts.
- **Implementation**:
    - All Docker resources created by the tool are labeled with their parent installation name (e.g., `ollama-stack.installation=<PROJECT_NAME>`).
    - Read-only commands like `status` detect and warn users about resources from other installations.
    - Destructive commands like `cleanup` and `uninstall` can target specific installations or all of them, preventing accidental data loss.

### 4. User-Controlled Updates

- **Principle**: Updates to underlying stack components (Ollama, WebUI) must be explicit, user-initiated actions. The tool does not perform automatic updates.
- **Implementation**:
    - The `ollama-stack update` command is the designated mechanism for pulling the latest Docker images.
    - The `ollama-stack start` command only pulls images if the `--update` flag is explicitly provided.

### 5. Unified Service Health Monitoring

- **Principle**: The tool's perception of the stack's status must be accurate, reliable, and consistent across all service types.
- **Implementation**:
    - **Centralized Health Checks**: The `StackManager` provides unified health checking logic for all services using HTTP → TCP fallback approach.
    - **Service-Specific Logic**: Each service type (`docker`, `native-api`) maintains its role:
        - `DockerClient`: Manages containers without health checking (returns health="unknown")
        - `OllamaApiClient`: Provides rich native service status (model counts, installation status)
        - `StackManager`: Applies unified health checks to running services for consistent status reporting
    - **Consistent Methodology**: All services use the same health check approach, eliminating discrepancies between Docker's health reporting and CLI status.

### 6. User Data Preservation

- **Principle**: The tool must never delete user data unless explicitly instructed to do so.
- **Implementation**:
    - Standard `stop` commands stop and remove containers but **never** touch Docker volumes.
    - Commands that can delete volumes (`cleanup`, `uninstall`) require an explicit `--remove-volumes` flag.
    - When this flag is used, a prominent warning is displayed, and user confirmation is required.

### 7. Extensible MCP Architecture

- **Principle**: The core architecture must accommodate a growing ecosystem of MCP extensions without requiring major refactoring.
- **Implementation**:
    - **Extension Registry**: The `extensions/registry.json` file serves as the central catalog of available extensions.
    - **Self-Contained Extensions**: Extension logic and resources are contained within their respective subdirectories in the `extensions/` directory.
    - **State Management**: The `.ollama-stack.json` file tracks the state of extensions (enabled/disabled).
    - **Lifecycle Management**: The CLI provides commands to manage the extension lifecycle (`list`, `enable`, `start`, etc.), orchestrating Docker Compose operations within each extension's context. 
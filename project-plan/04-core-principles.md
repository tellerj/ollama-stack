# 04: Core Principles and Behaviors

This document outlines the high-level principles that guide the design and behavior of the `ollama-stack` CLI tool and the stack it manages.

### 1. Platform-Aware Optimization

- **Principle**: The tool must be platform-agnostic at its core but adapt its configuration for optimal performance on the host system.
- **Implementation**:
    - The CLI will auto-detect the host environment, prioritizing `nvidia`, then `apple` silicon, and defaulting to `cpu`.
    - Platform-specific Docker Compose files (`docker-compose.nvidia.yml`, `docker-compose.apple.yml`) will be used as overrides to the base `docker-compose.yml`.
    - The user can always manually override the detected platform with the `--platform` flag.

### 2. State and Configuration Integrity

- **Principle**: Configuration must be explicit, transparent, and resilient, with a clear separation between environment configuration and CLI state.
- **Implementation**:
    - A `.env` file in the project's root directory is the single source of truth for Docker Compose environment variables (e.g., `PROJECT_NAME`, `WEBUI_SECRET_KEY`).
    - A `.ollama-stack.json` file stores the CLI's internal state, such as the list of enabled extensions.
    - The `PROJECT_NAME` variable is used to generate deterministic and unique names for all Docker resources (containers, volumes, networks), preventing conflicts.
    - All file-based configuration will be managed via dedicated libraries (`python-dotenv` for `.env`, Python's `json` module for JSON files) to ensure robustness.

### 3. Graceful Multi-Installation Management

- **Principle**: The tool must be aware of other `ollama-stack` installations on the same machine and help the user manage them to avoid conflicts.
- **Implementation**:
    - All Docker resources created by the tool will be labeled with their parent installation name (e.g., `ollama-stack.installation=<PROJECT_NAME>`).
    - Read-only commands like `status` will detect and warn the user about resources from other installations.
    - Destructive commands like `cleanup` and `uninstall` will be able to target specific installations or all of them, preventing accidental data loss.

### 4. User-Controlled Updates

- **Principle**: Updates to the underlying stack components (Ollama, WebUI) must be an explicit, user-initiated action. The tool should not perform automatic updates.
- **Implementation**:
    - The `ollama-stack update` command is the designated mechanism for pulling the latest Docker images.
    - The `ollama-stack start` command will only pull images if the `--update` flag is explicitly provided.

### 5. Robust Service Health Monitoring

- **Principle**: The tool's perception of the stack's status must be accurate and reliable.
- **Implementation**:
    - After starting services, the CLI will actively poll their public-facing API endpoints to confirm they are operational before reporting success.
    - The `status` command will rely on the Docker API for container status, providing a real-time view of the services.

### 6. User Data Preservation

- **Principle**: The tool must never delete user data unless explicitly instructed to do so.
- **Implementation**:
    - Standard `stop` commands will stop and remove containers but will **never** touch Docker volumes.
    - Commands that can delete volumes (`cleanup`, `uninstall`) require an explicit `--remove-volumes` flag.
    - When this flag is used, a prominent warning will be displayed, and user confirmation will be required.

### 7. Extensible Architecture

- **Principle**: The core architecture must be designed to accommodate a future ecosystem of extensions without requiring a major refactor.
- **Implementation**:
    - Extension logic and resources are self-contained within their respective subdirectories in the `extensions/` directory.
    - The `.ollama-stack.json` file serves as the central manifest for tracking the state of extensions (e.g., which are enabled).
    - The CLI provides commands to manage the extension lifecycle (`enable`, `start`, etc.), orchestrating Docker Compose operations within the context of each extension. 
# 00: Project Overview and Goals

This document provides a high-level overview of the Ollama Stack project and its unified Python CLI tool.

## 1. Project Status

**Current Version:** v0.2.0 (Mid-Implementation)

The `ollama-stack` CLI is a robust Python application that has successfully replaced the original parallel Bash and PowerShell scripts. **Core functionality is complete and production-ready**, but several advanced features remain to be implemented.

### 1.1. The Original Problem (Solved)
- **Dual Maintenance:** Required implementing and testing logic in two separate codebases
- **Fragility:** Scripts relied on parsing string output of shell commands
- **Inconsistent Behavior:** Divergence between scripts led to poor user experience

### 1.2. The Solution: Unified Python CLI (In Progress)
A single Python application provides a maintainable and robust foundation for managing the stack. It uses the official Docker SDK for API-driven interactions and is distributed via standard Python tooling (`pip` and `pyproject.toml`).

**Completed Achievements:**
- ✅ Core lifecycle commands (start, stop, restart)
- ✅ State and information commands (status, logs, check)
- ✅ Unified health check system with HTTP → TCP fallback
- ✅ Cross-platform installation scripts
- ✅ 296 comprehensive unit tests + 11 integration tests (100% pass rate)
- ✅ Complete MCP extension architecture foundation

**Remaining Work:**
- 🔄 Resource management commands (update, uninstall)
- 🔄 Backup and migration capabilities (backup, restore, migrate)
- 🔄 Extension management interface (list, enable, disable, start, stop)

---

## 2. The Ollama Stack Architecture

The Ollama Stack is an integrated, extensible environment for working with local Large Language Models. Its architecture consists of three layers:

1. **Core Services**: The foundational layer including `ollama`, `open-webui`, and `mcp-proxy`
2. **Model Context Protocol (MCP)**: A middleware layer that makes the stack extensible by routing and modifying requests between AI models and tools
3. **Extensions**: A modular ecosystem of tools that plug into the MCP to add specialized functionality (TTS, web search, file processing, etc.)

### 2.1. Platform Optimization
The stack automatically detects and optimizes for different hardware configurations:
- **Apple Silicon**: Uses native Ollama with Docker services
- **NVIDIA GPU**: Enables CUDA acceleration for model inference
- **CPU**: Standard Docker configuration for maximum compatibility

---

## 3. The CLI Tool's Role

The `ollama-stack` CLI is the primary interface for managing the entire stack lifecycle:

- **Lifecycle Management**: Start, stop, restart, and monitor core services ✅
- **Platform Awareness**: Automatic detection and optimization for hardware ✅
- **Health Monitoring**: Unified health checking across all service types ✅
- **Resource Management**: Update images, clean up resources, uninstall stack 🔄
- **Data Management**: Backup, restore, and migrate stack configurations 🔄
- **Extension Management**: Enable, disable, and control MCP extensions 🔄
- **User Experience**: Consistent, rich terminal output with clear error messages ✅

The tool abstracts complex Docker operations while providing specialized functionality for AI development workflows.

---

## 4. Distribution and Installation

- **Package Management**: Distributed as `ollama-stack-cli` Python package ✅
- **Installation**: Cross-platform scripts (`install-ollama-stack.sh`, `install-ollama-stack.ps1`) ✅
- **Requirements**: Python 3.8+, Docker, and platform-specific dependencies ✅
- **Documentation**: Comprehensive README with quick start guide ✅ 
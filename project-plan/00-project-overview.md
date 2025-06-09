# 00: Project Overview and Goals

This document provides a high-level overview of the Ollama Stack project, the motivation for its refactoring, and the goals of its new CLI tool.

## 1. The Refactoring Initiative

The initial `ollama-stack` tool consisted of parallel Bash and PowerShell scripts that were difficult to maintain and extend. This project replaces them with a single, robust, cross-platform CLI application written in Python.

### 1.1. The Core Problem
- **Dual Maintenance:** All logic had to be implemented and tested in two separate codebases.
- **Fragility:** The scripts relied on parsing the string output of shell commands, which is brittle.
- **Inconsistent Behavior:** Divergence between the scripts led to an inconsistent user experience.

### 1.2. The Solution: A Unified Python CLI
A single Python application provides a maintainable and robust foundation for managing the stack. It uses the official Docker SDK for API-driven interactions and is distributed via standard Python tooling (`pip` and `pyproject.toml`).

---

## 2. The Ollama Stack Architecture

The Ollama Stack is an integrated, extensible environment for working with local Large Language Models. Its architecture consists of three layers:

1.  **Core Services**: The foundational layer that includes `ollama` and `open-webui`.
2.  **Model Context Protocol (MCP)**: A middleware layer (`mcp-proxy`) that makes the stack extensible by routing and modifying requests.
3.  **Extensions**: A modular ecosystem of tools that plug into the MCP to add functionality.

## 3. The CLI Tool's Role

The `ollama-stack` CLI is the primary tool for managing the lifecycle of this entire stack.

-   It is a platform-aware tool designed to correctly configure, start, stop, and monitor the core services and the ecosystem of MCP extensions.
-   It provides a unified interface for complex operations, abstracting away the underlying Docker commands.
-   It is the user's entry point for managing the state of the stack, particularly for enabling, disabling, and interacting with MCP extensions. 
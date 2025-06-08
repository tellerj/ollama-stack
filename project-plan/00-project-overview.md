# 00: Project Overview

This document provides a high-level overview of the Ollama Stack project and the goals of its CLI tool.

## 1. The Ollama Stack Architecture

The Ollama Stack is an integrated, extensible environment for working with local Large Language Models. Its architecture consists of three layers:

1.  **Core Services**: The foundational layer that includes:
    -   `ollama`: The core LLM runtime.
    -   `open-webui`: A user-friendly, web-based interface for interacting with the models.

2.  **Model Context Protocol (MCP)**: The middleware layer that makes the stack extensible.
    -   `mcp-proxy`: A central proxy service that intelligently routes requests between the WebUI, Ollama, and various extensions. It allows for the dynamic modification of model context, enabling powerful new capabilities.

3.  **Extensions**: A modular ecosystem of tools that plug into the MCP.
    -   Each extension is a self-contained service (e.g., a Text-to-Speech engine, a document analysis tool) that can inspect and modify the context of a conversation, seamlessly integrating its functionality into the user's workflow.

## 2. The CLI Tool's Role

The `ollama-stack` CLI is the primary tool for managing the lifecycle of this entire stack on a developer's local machine.

-   **Its purpose is not just to run Docker Compose.** It is a platform-aware tool designed to correctly configure, start, stop, and monitor the core services and the ecosystem of MCP extensions.
-   It provides a unified and user-friendly interface for complex operations, abstracting away the underlying Docker commands and ensuring the stack runs correctly across CPU, NVIDIA, and Apple Silicon environments.
-   It is the user's entry point for managing the state of the stack, particularly for enabling, disabling, and interacting with MCP extensions. 
# Ollama Stack CLI Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## [Unreleased]

### Added
- Initial project structure for the `ollama-stack` CLI.
- `pyproject.toml` with dependencies and tool configuration.
- Basic CLI entry point in `main.py`. 
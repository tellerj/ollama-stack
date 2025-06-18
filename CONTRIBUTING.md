# Contributing to Ollama Stack

First off, thank you for considering contributing! This project is a community effort, and we welcome all forms of contributions. This document provides the guidelines for contributing to this project.

## Development Environment Setup

To get started, you'll need to have the following prerequisites installed:
- Python (version 3.10 or newer)
- Docker and Docker Compose

Once the prerequisites are met, follow these steps to set up your development environment:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-org/ollama-stack.git
    cd ollama-stack
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies in editable mode:**
    This command installs the `ollama-stack` CLI in a way that your changes to the source code will be immediately reflected. The `[dev]` flag also installs all development dependencies, such as `pytest`.
    ```bash
    pip install -e ".[dev]"
    ```

4.  **Verify the installation:**
    You should now be able to run the CLI and see its help text.
    ```bash
    ollama-stack --help
    ```

## Coding Standards

To ensure consistency and maintain high code quality, we use the following tools. All configuration is managed in the `pyproject.toml` file.

-   **Formatter (`black`):** We use `black` for uncompromising code formatting. Before committing, please format your code:
    ```bash
    black ollama_stack_cli/ tests/
    ```

-   **Linter (`ruff`):** We use `ruff` for linting. It's incredibly fast and helps catch a wide range of errors and style issues. To check your code, run:
    ```bash
    ruff check ollama_stack_cli/ tests/
    ```

We recommend using `pre-commit` hooks to automate this process.

## Running Tests

The project maintains a comprehensive test suite to ensure correctness and prevent regressions.

-   **Run all tests:**
    To run the complete suite of unit and integration tests, use `pytest`:
    ```bash
    pytest
    ```

## Definition of Done

For a contribution, especially a new feature or command, to be considered "done," it must meet the following criteria:

- [ ] The feature is implemented according to the project's architecture (`AppContext`, `display` module).
- [ ] New code is accompanied by passing unit tests with adequate coverage.
- [ ] New features include integration tests that validate the end-to-end functionality.
- [ ] User-facing strings and command help text are clear and free of typos.
- [ ] The code is formatted with `black` and passes all `ruff` linter checks.
- [ ] The contribution is documented in the `CHANGELOG.md` if it includes a user-facing change.

Thank you again for your contribution! 
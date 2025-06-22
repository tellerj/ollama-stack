# Comprehensive Testing Plan for Ollama Stack CLI

This document outlines the testing strategy and specific test cases required to ensure the `ollama-stack-cli` is robust, correct, and maintainable. It reflects the application's final architecture, centered around the `StackManager`.

### Core Testing Strategy

-   **Unit Tests**: Each module will be tested in isolation. We will use `pytest` for test structure and `pytest-mock` for mocking dependencies.
    -   **Commands (`test_commands.py`)**: Mock the `AppContext` and `StackManager` to ensure commands call the correct manager methods.
    -   **Orchestration (`test_stack_manager.py`)**: Mock the `DockerClient` and `OllamaApiClient` to test the platform-specific logic and orchestration flow.
    -   **Low-Level Clients (`test_docker_client.py`, `test_ollama_api_client.py`)**: Mock the underlying libraries (`docker` SDK, `urllib`) to simulate various responses and failures.
    -   **Display (`test_display.py`)**: Mock the `rich.console.Console` to verify that the correct output is being generated without printing to the screen.
-   **Integration Tests (`test_integration.py`)**: These tests will run against a live Docker daemon to verify end-to-end user workflows. They will be marked with `@pytest.mark.integration` and will not use mocks.

---

### 1. `tests/test_commands.py` (Requires Update)

**Objective**: Ensure CLI commands correctly parse arguments and delegate to the `StackManager`.

**Required Actions**:

1.  **Refactor All Tests**: Update every test function (`test_start_command`, `test_stop_command`, etc.) to mock the `stack_manager` instead of the `docker_client`.
    -   *Example*: The assertion `mock_app_context.docker_client.start_services.assert_called_once()` must become `mock_app_context.stack_manager.start_services.assert_called_once()`.
2.  **Verify All Commands**: Ensure the following commands have their calls to `stack_manager` tested: `start`, `stop`, `restart`, `status`, `logs`, `check`.
3.  **Add Edge Case Test for `logs`**: Add a test to verify that `logs` command correctly handles the case where `stream_logs` returns an empty iterator.

---

### 2. `tests/test_context.py` (Requires Update)

**Objective**: Ensure the `AppContext` initializes the correct services for the new architecture.

**Required Actions**:

1.  **Update `test_app_context_initialization`**:
    -   Remove the assertion for `MockDockerClient`.
    -   Add an assertion that `StackManager` is initialized correctly, being passed the `config` and `display` instances.
    -   `MockStackManager.assert_called_once_with(config=mock_load_config.return_value, display=MockDisplay.return_value)`
2.  **Update `test_app_context_init_failure`**: Change the test to check for a failure during `StackManager` initialization instead of `DockerClient`.

---

### 3. `tests/test_docker_client.py` (Requires Major Refactor)

**Objective**: Simplify the `DockerClient` to be a "dumb" wrapper around the Docker SDK and `docker-compose` commands. Its tests should reflect this simplification.

**Required Actions**:

1.  **Move Orchestration Tests**: The logic and corresponding tests for high-level operations must be moved to `test_stack_manager.py`. This includes tests for:
    -   `get_stack_status`
    -   `run_environment_checks`
    -   `start_services` / `stop_services` / `restart_services`
    -   `is_stack_running`
    -   `_perform_health_checks`
2.  **Simplify `get_container_status` Test**: The existing `test_get_status_core_services_running` should be refactored into a new `test_get_container_status`. This test should verify that the method takes a list of service names and returns a list of `ServiceStatus` objects based on the mocked `docker.client.containers.list` output.
3.  **Keep Low-Level Tests**: The following tests test the core responsibility of `DockerClient` and should be kept and updated if necessary:
    -   `test_detect_platform`
    -   `test_docker_client_init_raises_on_docker_error`
    -   `test_get_compose_file_*`
    -   `test_pull_images_calls_compose_pull`
    -   `test_run_compose_command_failure`

---

### 4. `tests/test_display.py` (Requires Expansion)

**Objective**: Ensure all user-facing output is correctly formatted.

**Required Actions**:

1.  **Add `test_display_status_renders_table`**:
    -   Create a sample `StackStatus` object with a mix of running, stopped, and unhealthy services.
    -   Call `display.status()` with this object.
    -   Assert that `console.print` was called with a `rich.table.Table` instance.
    -   Inspect the table's rows to verify the correct data and styling (e.g., green for "running", red for "stopped").
2.  **Add `test_display_status_empty_state`**:
    -   Call `display.status()` with an empty `StackStatus` object.
    -   Assert that `display.info()` was called with the "not running" message.
3.  **Add `test_display_check_report`**:
    -   Create a sample `CheckReport` with passing and failing checks.
    -   Call `display.check_report()` and assert that the output contains the correct `[PASSED]` and `[FAILED]` strings with appropriate coloring.
4.  **Add `test_display_log_message`**:
    -   Call `display.log_message()` with a sample log line.
    -   Assert that `console.print` was called with the exact line.

---

### 5. `tests/test_ollama_api_client.py` (New Test File)

**Objective**: Verify the client correctly queries the native Ollama API and handles different responses.

**Required Actions**:

1.  **Create Test File**: Create `tests/test_ollama_api_client.py`.
2.  **Strategy**: Mock `urllib.request.urlopen` to simulate various API responses.
3.  **Add Tests**:
    -   **`test_get_status_healthy`**: Mock a successful HTTP 200 response. Assert the returned `ServiceStatus` has `is_running=True`, `health='healthy'`, and a status string.
    -   **`test_get_status_connection_error`**: Mock `urlopen` to raise a `urllib.error.URLError`. Assert the returned `ServiceStatus` has `is_running=False` and `health='unhealthy'`.
    -   **`test_get_status_http_error`**: Mock a non-200 HTTP status response. Assert `is_running=False` and `health='unhealthy'`.
    -   **`test_get_status_timeout`**: Mock `urlopen` to raise a `socket.timeout`. Assert `is_running=False` and `health='unhealthy'`.

---

### 6. `tests/test_stack_manager.py` (New Test File)

**Objective**: Verify the `StackManager`'s orchestration logic and correct delegation to its clients.

**Required Actions**:

1.  **Create Test File**: Create `tests/test_stack_manager.py`.
2.  **Strategy**: Mock the `DockerClient` and `OllamaApiClient` instances passed into the `StackManager`.
3.  **Add Platform-Specific Tests**:
    -   **`test_get_stack_status_on_apple`**: Force platform to `apple`. Call `get_stack_status`. Assert `docker_client.get_container_status` is called for Docker services AND `ollama_api_client.get_status` is called for the native service. Verify the results are correctly combined.
    -   **`test_get_stack_status_on_linux`**: Force platform to `cpu`. Assert `docker_client.get_container_status` is called for all services and `ollama_api_client.get_status` is **not** called.
    -   **`test_stream_logs_for_native_ollama_on_apple`**: Force platform to `apple`. Call `stream_logs('ollama')`. Assert it does not call the `docker_client` and instead returns an informational message.
4.  **Add Orchestration Logic Tests**: Re-implement tests from the old docker-client.py file
    -   **`test_start_services`**: Test the logic flow: calls `pull_images` if `update=True`, calls `docker_client.run_compose_command`, calls `_perform_health_checks`.
    -   **`test_stop_services`**: Test that it calls `docker_client.run_compose_command` with 'down' and verifies all services are stopped by checking `is_stack_running`.
    -   **`test_restart_services`**: Use a `MagicMock` manager to assert that `self.stop_services` is called before `self.start_services`.
    -   **`test_run_environment_checks`**: Verify it calls the `docker_client` and returns the `CheckReport`.
    -   **`test_is_stack_running`**: Mock `get_stack_status` to return different combinations of running/stopped services. Assert it returns True only when all required services are running.
    -   **`test_perform_health_checks`**: Mock service statuses and verify it correctly identifies unhealthy services. Test timeout behavior when services don't become healthy within max retries.


### 7. `tests/test_integration.py` (Requires Expansion)

**Objective**: Verify end-to-end functionality for all user-facing commands.

**Required Actions**:

1.  **Add `test_status_command_integration`**:
    -   Start the stack.
    -   Run the `status` command.
    -   Assert the output contains the expected table structure and service names.
2.  **Add `test_check_command_integration`**:
    -   Run the `check` command (with the stack stopped).
    -   Assert the output contains the expected check descriptions (e.g., "Docker Daemon Running").
3.  **Add `test_logs_command_integration`**:
    -   Start the stack.
    -   Run the `logs` command for a specific service (e.g., `webui`) with `--tail=1`.
    -   Assert the output contains at least one log line.
import pytest
import docker
import platform
from typer.testing import CliRunner
from ollama_stack_cli.main import app

runner = CliRunner()

# --- Test Configuration ---

IS_APPLE_SILICON = platform.system() == "Darwin" and platform.machine() == "arm64"
# On Apple Silicon, 'ollama' runs natively, so it's not in our Docker stack.
EXPECTED_COMPONENTS = {"webui", "mcp_proxy"} if IS_APPLE_SILICON else {"ollama", "webui", "mcp_proxy"}


# --- Helper Functions ---

def get_running_stack_components() -> set:
    """
    Connects to Docker to find all running containers with the stack's component
    label and returns a set of the component names.
    """
    client = docker.from_env()
    containers = client.containers.list(filters={"label": "ollama-stack.component", "status": "running"})
    return {c.labels.get("ollama-stack.component") for c in containers}


# --- Test Fixtures ---

@pytest.fixture(autouse=True)
def clean_stack_between_tests():
    """
    A fixture that ensures the stack is stopped before and after each integration test,
    providing a clean, isolated environment.
    """
    runner.invoke(app, ["stop"])
    yield
    runner.invoke(app, ["stop"])


# --- Integration Tests ---

@pytest.mark.integration
def test_start_and_stop_lifecycle():
    """
    Verifies the most basic user workflow: start the stack, see that it's
    running, stop it, and see that it's stopped.
    """
    # 1. Start the stack
    result_start = runner.invoke(app, ["start"], catch_exceptions=False)
    assert result_start.exit_code == 0
    assert get_running_stack_components() == EXPECTED_COMPONENTS

    # 2. Stop the stack
    result_stop = runner.invoke(app, ["stop"], catch_exceptions=False)
    assert result_stop.exit_code == 0
    assert get_running_stack_components() == set()


@pytest.mark.integration
def test_start_when_already_running_is_idempotent():
    """
    Verifies that running 'start' on an already running stack has no
    negative side effects and informs the user.
    """
    runner.invoke(app, ["start"])
    initial_components = get_running_stack_components()
    assert initial_components == EXPECTED_COMPONENTS

    # Run start again
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    assert "already running" in result.stdout
    
    # Verify that the stack was not changed
    final_components = get_running_stack_components()
    assert final_components == initial_components


@pytest.mark.integration
def test_stop_when_already_stopped_is_idempotent():
    """
    Verifies that running 'stop' on an already stopped stack has no
    negative side effects and exits gracefully.
    """
    # The fixture ensures the stack is already stopped.
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0


@pytest.mark.integration
def test_restart_recreates_services():
    """
    Verifies that 'restart' correctly replaces the running containers
    with new ones.
    """
    runner.invoke(app, ["start"])
    client = docker.from_env()
    initial_containers = client.containers.list(filters={"label": "ollama-stack.component"})
    initial_ids = {c.id for c in initial_containers}
    
    # Restart the stack
    result = runner.invoke(app, ["restart"], catch_exceptions=False)
    assert result.exit_code == 0
    
    # Verify the correct services are running
    assert get_running_stack_components() == EXPECTED_COMPONENTS
    
    # Verify the new containers are different from the old ones
    final_containers = client.containers.list(filters={"label": "ollama-stack.component"})
    final_ids = {c.id for c in final_containers}
    assert not initial_ids.intersection(final_ids)


@pytest.mark.integration
def test_start_with_update_pulls_images():
    """
    Verifies that 'start --update' runs the image pull process before
    starting the services.
    """
    result = runner.invoke(app, ["start", "--update"], catch_exceptions=False)
    
    assert result.exit_code == 0
    assert "Pulling latest images" in result.stdout
    assert get_running_stack_components() == EXPECTED_COMPONENTS


@pytest.mark.integration
def test_status_command_integration():
    """
    Verifies the 'status' command runs and displays the expected services.
    """
    # 1. Test status when stack is down
    result_down = runner.invoke(app, ["status"])
    assert result_down.exit_code == 0
    assert "Ollama Stack is not running" in result_down.stdout

    # 2. Start the stack and test status
    runner.invoke(app, ["start"])
    result_up = runner.invoke(app, ["status"])
    assert result_up.exit_code == 0
    # Check that all expected components are listed in the output table
    for component in EXPECTED_COMPONENTS:
        assert component in result_up.stdout
    assert "Running" in result_up.stdout # Part of the status table


@pytest.mark.integration
def test_check_command_integration():
    """
    Verifies the 'check' command runs and displays the expected checks.
    """
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    assert "Docker Daemon Running" in result.stdout
    assert "Port 8080 Available" in result.stdout


@pytest.mark.integration
def test_logs_command_integration():
    """
    Verifies the 'logs' command can fetch logs from a running service.
    """
    # Start the stack so services are running
    runner.invoke(app, ["start"])

    # Fetch one line of logs from the webui service
    result = runner.invoke(app, ["logs", "webui", "--tail", "1"])
    assert result.exit_code == 0
    # A successful log command should produce some output
    assert len(result.stdout.strip()) > 0 
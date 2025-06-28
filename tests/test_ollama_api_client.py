import pytest
from unittest.mock import MagicMock, patch
import urllib.error
import socket
import json
import subprocess

from ollama_stack_cli.ollama_api_client import OllamaApiClient
from ollama_stack_cli.schemas import ServiceStatus

@pytest.fixture
def mock_display():
    """Fixture for a mocked Display object."""
    return MagicMock()

@pytest.fixture
def api_client(mock_display):
    """Fixture to create an OllamaApiClient with a mocked display."""
    return OllamaApiClient(display=mock_display)

@patch('shutil.which', return_value='/usr/local/bin/ollama')
@patch('subprocess.run')
@patch('urllib.request.urlopen')
def test_get_status_healthy_with_models(mock_urlopen, mock_subprocess, mock_which, api_client):
    """Tests a healthy response with models loaded via ollama ps command."""
    # Mock API response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    # Mock ollama ps command response
    mock_subprocess.return_value.returncode = 0
    mock_subprocess.return_value.stdout = "NAME\tID\t\nllama2:latest\t123\ncodellama:latest\t456\n"
    
    status = api_client.get_status()
    
    assert status.is_running is True
    assert status.health == "healthy"
    assert status.status == "Running (2 models)"
    mock_urlopen.assert_called_once()
    mock_subprocess.assert_called_once_with(["ollama", "ps"], capture_output=True, text=True, timeout=5)

@patch('shutil.which', return_value='/usr/local/bin/ollama')
@patch('subprocess.run')
@patch('urllib.request.urlopen')
def test_get_status_healthy_no_models(mock_urlopen, mock_subprocess, mock_which, api_client):
    """Tests a healthy response with no models loaded."""
    # Mock API response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    # Mock ollama ps command response (only header line)
    mock_subprocess.return_value.returncode = 0
    mock_subprocess.return_value.stdout = "NAME\tID\t\n"
    
    status = api_client.get_status()
    
    assert status.is_running is True
    assert status.health == "healthy"
    assert status.status == "Running (no models loaded)"

@patch('shutil.which', return_value=None)
def test_get_status_ollama_not_installed(mock_which, api_client):
    """Tests when ollama command is not installed."""
    status = api_client.get_status()
    
    assert status.is_running is False
    assert status.health == "unavailable"
    assert status.status == "Not installed"
    assert status.name == "ollama (Native)"

@patch('shutil.which', return_value='/usr/local/bin/ollama')
@patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Connection failed"))
def test_get_status_connection_error(mock_urlopen, mock_which, api_client):
    """Tests a URLError, indicating the service is not reachable."""
    status = api_client.get_status()
    
    assert status.is_running is False
    assert status.health == "unhealthy"

@patch('shutil.which', return_value='/usr/local/bin/ollama')
@patch('urllib.request.urlopen')
def test_get_status_http_error(mock_urlopen, mock_which, api_client):
    """Tests a non-200 HTTP status response."""
    mock_response = MagicMock()
    mock_response.status = 500
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    status = api_client.get_status()
    
    assert status.is_running is False
    assert status.health == "unhealthy"

@patch('shutil.which', return_value='/usr/local/bin/ollama')
@patch('urllib.request.urlopen', side_effect=socket.timeout("Request timed out"))
def test_get_status_timeout(mock_urlopen, mock_which, api_client):
    """Tests a socket.timeout, indicating the service is unresponsive."""
    status = api_client.get_status()
    
    assert status.is_running is False
    assert status.health == "unhealthy"

@patch('shutil.which', return_value='/usr/local/bin/ollama')
@patch('subprocess.run')
@patch('urllib.request.urlopen')
def test_get_status_ollama_ps_command_fails(mock_urlopen, mock_subprocess, mock_which, api_client):
    """Tests when ollama ps command fails but API is responsive."""
    # Mock API response (healthy)
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    # Mock ollama ps command failure
    mock_subprocess.return_value.returncode = 1
    
    status = api_client.get_status()
    
    assert status.is_running is True
    assert status.health == "healthy"
    assert status.status == "Running"  # Falls back to basic "Running"

@patch('shutil.which', return_value=None)
def test_is_service_running_not_installed(mock_which, api_client):
    """Tests is_service_running when ollama is not installed."""
    result = api_client.is_service_running()
    assert result is False

@patch('shutil.which', return_value='/usr/local/bin/ollama')
@patch('subprocess.run')
def test_is_service_running_process_found(mock_subprocess, mock_which, api_client):
    """Tests is_service_running when process is found via pgrep."""
    mock_subprocess.return_value.returncode = 0
    result = api_client.is_service_running()
    assert result is True
    mock_subprocess.assert_called_once_with(["pgrep", "-f", "ollama serve"], capture_output=True, text=True, timeout=3)

@patch('shutil.which', return_value='/usr/local/bin/ollama')
@patch('subprocess.run', side_effect=subprocess.TimeoutExpired('pgrep', 3))
@patch('urllib.request.urlopen')
def test_is_service_running_fallback_to_api(mock_urlopen, mock_subprocess, mock_which, api_client):
    """Tests fallback to API check when pgrep times out."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    result = api_client.is_service_running()
    assert result is True

@patch('shutil.which', return_value=None)
def test_start_service_not_installed(mock_which, api_client):
    """Tests start_service when ollama is not installed."""
    result = api_client.start_service()
    assert result is False

@patch('shutil.which', return_value='/usr/local/bin/ollama')
@patch.object(OllamaApiClient, 'is_service_running', return_value=True)
def test_start_service_already_running(mock_is_running, mock_which, api_client):
    """Tests start_service when service is already running."""
    result = api_client.start_service()
    assert result is True

@patch('shutil.which', return_value=None)
def test_stop_service_not_installed(mock_which, api_client):
    """Tests stop_service when ollama is not installed."""
    result = api_client.stop_service()
    assert result is True  # Consider success since service can't be running

@patch('shutil.which', return_value='/usr/local/bin/ollama')
@patch.object(OllamaApiClient, 'is_service_running', return_value=False)
def test_stop_service_not_running(mock_is_running, mock_which, api_client):
    """Tests stop_service when service is not running."""
    result = api_client.stop_service()
    assert result is True

@patch('shutil.which', return_value='/usr/local/bin/ollama')
@patch.object(OllamaApiClient, 'is_service_running', side_effect=[True, False])  # Running, then stopped
@patch('subprocess.run')
def test_stop_service_success(mock_subprocess, mock_is_running, mock_which, api_client):
    """Tests successful stop_service operation."""
    mock_subprocess.return_value.returncode = 0
    
    result = api_client.stop_service()
    assert result is True
    mock_subprocess.assert_called_once_with(["pkill", "-f", "ollama serve"], capture_output=True, text=True, timeout=10)

@patch('shutil.which', return_value='/usr/local/bin/ollama')
@patch.object(OllamaApiClient, 'is_service_running', return_value=True)
@patch('subprocess.run', side_effect=subprocess.TimeoutExpired('pkill', 10))
def test_stop_service_timeout(mock_subprocess, mock_is_running, mock_which, api_client):
    """Tests stop_service when pkill times out."""
    result = api_client.stop_service()
    assert result is False 
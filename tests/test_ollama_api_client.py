import pytest
from unittest.mock import MagicMock, patch
import urllib.error
import socket
import json

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

@patch('urllib.request.urlopen')
def test_get_status_healthy_with_models(mock_urlopen, api_client):
    """Tests a healthy 200 response with models loaded."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({"models": [{}, {}]}).encode()
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    status = api_client.get_status()
    
    assert status.is_running is True
    assert status.health == "healthy"
    assert status.status == "Loaded (2 models)"

@patch('urllib.request.urlopen')
def test_get_status_healthy_no_models(mock_urlopen, api_client):
    """Tests a healthy 200 response with no models loaded."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({"models": []}).encode()
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    status = api_client.get_status()
    
    assert status.is_running is True
    assert status.health == "healthy"
    assert status.status == "Running"

@patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Connection failed"))
def test_get_status_connection_error(mock_urlopen, api_client):
    """Tests a URLError, indicating the service is not reachable."""
    status = api_client.get_status()
    
    assert status.is_running is False
    assert status.health == "unhealthy"

@patch('urllib.request.urlopen')
def test_get_status_http_error(mock_urlopen, api_client):
    """Tests a non-200 HTTP status response."""
    mock_response = MagicMock()
    mock_response.status = 500
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    status = api_client.get_status()
    
    assert status.is_running is False
    assert status.health == "unhealthy"

@patch('urllib.request.urlopen', side_effect=socket.timeout("Request timed out"))
def test_get_status_timeout(mock_urlopen, api_client):
    """Tests a socket.timeout, indicating the service is unresponsive."""
    status = api_client.get_status()
    
    assert status.is_running is False
    assert status.health == "unhealthy"

@patch('urllib.request.urlopen')
def test_get_status_json_decode_error(mock_urlopen, api_client, mock_display):
    """Tests handling of a malformed JSON response."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b"this is not json"
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    status = api_client.get_status()
    
    assert status.health == "unhealthy"
    # Note: JSON decode error is now logged instead of displayed 
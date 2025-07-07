from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any, Literal
import uuid
from datetime import datetime
from pathlib import Path

class ServiceConfig(BaseModel):
    """Defines the configuration for a single service in the stack."""
    type: Literal["docker", "native-api", "remote-api"] = "docker"
    health_check_url: Optional[HttpUrl] = None

class PlatformConfig(BaseModel):
    compose_file: str

class ExtensionsConfig(BaseModel):
    enabled: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)

class AppConfig(BaseModel):
    project_name: str = Field(default_factory=lambda: f"ollama-stack-{uuid.uuid4().hex[:8]}")
    version: str = Field(default="0.2.0", description="Current stack version")
    services: Dict[str, ServiceConfig] = Field(default_factory=lambda: {
        "ollama": ServiceConfig(),
        "webui": ServiceConfig(),
        "mcp_proxy": ServiceConfig(),
    })
    docker_compose_file: str = "docker-compose.yml"
    data_directory: str = "~/.ollama-stack/data"
    backup_directory: str = "~/.ollama-stack/backups"
    webui_secret_key: str = Field(default_factory=lambda: uuid.uuid4().hex)
    platform: Dict[str, PlatformConfig] = Field(default_factory=dict)
    extensions: ExtensionsConfig = Field(default_factory=ExtensionsConfig)


class ResourceUsage(BaseModel):
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None


class ServiceStatus(BaseModel):
    name: str
    is_running: bool
    status: Optional[str] = None
    health: Optional[str] = None
    ports: Dict[str, Optional[int]] = Field(default_factory=dict)
    usage: ResourceUsage = Field(default_factory=ResourceUsage)


class ExtensionStatus(ServiceStatus):
    is_enabled: bool


class StackStatus(BaseModel):
    core_services: List[ServiceStatus]
    extensions: List[ExtensionStatus]


class EnvironmentCheck(BaseModel):
    name: str
    passed: bool
    details: Optional[str] = None
    suggestion: Optional[str] = None


class CheckReport(BaseModel):
    checks: List[EnvironmentCheck]


class BackupConfig(BaseModel):
    """Configuration for backup operations."""
    include_volumes: bool = True
    include_config: bool = True
    include_extensions: bool = True
    compression: bool = True
    encryption: bool = False
    exclude_patterns: List[str] = Field(default_factory=list)


class BackupManifest(BaseModel):
    """Metadata for a stack backup."""
    backup_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime = Field(default_factory=datetime.now)
    stack_version: str
    cli_version: str
    platform: str
    backup_config: BackupConfig
    volumes: List[str] = Field(default_factory=list)
    config_files: List[str] = Field(default_factory=list)
    extensions: List[str] = Field(default_factory=list)
    checksum: Optional[str] = None
    size_bytes: Optional[int] = None
    description: Optional[str] = None







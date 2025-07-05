import pytest
from datetime import datetime
from ollama_stack_cli.schemas import (
    ServiceConfig, 
    AppConfig, 
    ServiceStatus, 
    ResourceUsage, 
    StackStatus, 
    EnvironmentCheck, 
    CheckReport,
    BackupConfig,
    BackupManifest,
    MigrationInfo
)


def test_service_config_defaults():
    """Test ServiceConfig with default values."""
    config = ServiceConfig()
    assert config.type == "docker"
    assert config.health_check_url is None


def test_service_config_with_values():
    """Test ServiceConfig with explicit values."""
    config = ServiceConfig(
        type="native-api",
        health_check_url="http://localhost:8080/health"
    )
    assert config.type == "native-api"
    assert str(config.health_check_url) == "http://localhost:8080/health"


def test_app_config_defaults():
    """Test AppConfig with default values."""
    config = AppConfig()
    assert config.project_name.startswith("ollama-stack-")
    assert len(config.services) == 3
    assert "ollama" in config.services
    assert "webui" in config.services
    assert "mcp_proxy" in config.services


def test_resource_usage():
    """Test ResourceUsage model."""
    usage = ResourceUsage(cpu_percent=25.5, memory_mb=128.0)
    assert usage.cpu_percent == 25.5
    assert usage.memory_mb == 128.0


def test_service_status():
    """Test ServiceStatus model."""
    status = ServiceStatus(
        name="test-service",
        is_running=True,
        status="running",
        health="healthy"
    )
    assert status.name == "test-service"
    assert status.is_running is True
    assert status.status == "running"
    assert status.health == "healthy"


def test_stack_status():
    """Test StackStatus model."""
    service_status = ServiceStatus(
        name="test-service",
        is_running=True,
        status="running",
        health="healthy"
    )
    stack_status = StackStatus(
        core_services=[service_status],
        extensions=[]
    )
    assert len(stack_status.core_services) == 1
    assert len(stack_status.extensions) == 0


def test_environment_check():
    """Test EnvironmentCheck model."""
    check = EnvironmentCheck(
        name="Docker Running",
        passed=True,
        details="Docker is running properly"
    )
    assert check.name == "Docker Running"
    assert check.passed is True
    assert check.details == "Docker is running properly"


def test_check_report():
    """Test CheckReport model."""
    check = EnvironmentCheck(
        name="Test Check",
        passed=True
    )
    report = CheckReport(checks=[check])
    assert len(report.checks) == 1


def test_backup_config_defaults():
    """Test BackupConfig with default values."""
    config = BackupConfig()
    assert config.include_volumes is True
    assert config.include_config is True
    assert config.include_extensions is True
    assert config.compression is True
    assert config.encryption is False
    assert config.exclude_patterns == []


def test_backup_config_with_values():
    """Test BackupConfig with explicit values."""
    config = BackupConfig(
        include_volumes=False,
        include_config=True,
        include_extensions=False,
        compression=False,
        encryption=True,
        exclude_patterns=["*.tmp", "*.log"]
    )
    assert config.include_volumes is False
    assert config.include_config is True
    assert config.include_extensions is False
    assert config.compression is False
    assert config.encryption is True
    assert config.exclude_patterns == ["*.tmp", "*.log"]


def test_backup_manifest():
    """Test BackupManifest model."""
    backup_config = BackupConfig()
    manifest = BackupManifest(
        stack_version="0.2.0",
        cli_version="0.2.0",
        platform="linux",
        backup_config=backup_config,
        volumes=["vol1", "vol2"],
        config_files=[".env", ".config"],
        extensions=["ext1"],
        description="Test backup"
    )
    
    assert manifest.stack_version == "0.2.0"
    assert manifest.cli_version == "0.2.0"
    assert manifest.platform == "linux"
    assert manifest.backup_config == backup_config
    assert manifest.volumes == ["vol1", "vol2"]
    assert manifest.config_files == [".env", ".config"]
    assert manifest.extensions == ["ext1"]
    assert manifest.description == "Test backup"
    assert manifest.backup_id is not None  # Should be auto-generated
    assert isinstance(manifest.created_at, datetime)


def test_migration_info():
    """Test MigrationInfo model."""
    migration = MigrationInfo(
        from_version="0.2.0",
        to_version="0.3.0",
        migration_path=["0.2.1", "0.2.2"],
        backup_required=True,
        breaking_changes=["Config format changed"],
        migration_steps=["Update config", "Migrate data"],
        estimated_duration="5 minutes"
    )
    
    assert migration.from_version == "0.2.0"
    assert migration.to_version == "0.3.0"
    assert migration.migration_path == ["0.2.1", "0.2.2"]
    assert migration.backup_required is True
    assert migration.breaking_changes == ["Config format changed"]
    assert migration.migration_steps == ["Update config", "Migrate data"]
    assert migration.estimated_duration == "5 minutes"


def test_migration_info_defaults():
    """Test MigrationInfo with default values."""
    migration = MigrationInfo(
        from_version="0.2.0",
        to_version="0.3.0"
    )
    
    assert migration.from_version == "0.2.0"
    assert migration.to_version == "0.3.0"
    assert migration.migration_path == []
    assert migration.backup_required is True
    assert migration.breaking_changes == []
    assert migration.migration_steps == []
    assert migration.estimated_duration is None
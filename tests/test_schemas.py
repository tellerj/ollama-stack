import pytest
from datetime import datetime
from pydantic import ValidationError
from ollama_stack_cli.schemas import (
    ServiceConfig, 
    PlatformConfig,
    ExtensionsConfig,
    AppConfig, 
    ResourceUsage,
    ServiceStatus,
    ExtensionStatus,
    StackStatus, 
    EnvironmentCheck, 
    CheckReport,
    BackupConfig,
    BackupManifest,
    MigrationInfo
)


class TestServiceConfig:
    """Test ServiceConfig model."""
    
    def test_defaults(self):
        """Test ServiceConfig with default values."""
        config = ServiceConfig()
        assert config.type == "docker"
        assert config.health_check_url is None
    
    def test_valid_types(self):
        """Test all valid service types."""
        for service_type in ["docker", "native-api", "remote-api"]:
            config = ServiceConfig(type=service_type)
            assert config.type == service_type
    
    def test_invalid_type(self):
        """Test invalid service type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ServiceConfig(type="invalid-type")
        assert "Input should be 'docker', 'native-api' or 'remote-api'" in str(exc_info.value)
    
    def test_valid_health_check_url(self):
        """Test valid health check URLs."""
        valid_urls = [
            ("http://localhost:8080", "http://localhost:8080/"),
            ("https://example.com/health", "https://example.com/health"),
            ("http://127.0.0.1:9000/status", "http://127.0.0.1:9000/status")
        ]
        for url_input, expected_output in valid_urls:
            config = ServiceConfig(health_check_url=url_input)
            assert str(config.health_check_url) == expected_output
    
    def test_invalid_health_check_url(self):
        """Test invalid health check URLs raise ValidationError."""
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",
            "localhost:8080",  # Missing protocol
            ""
        ]
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                ServiceConfig(health_check_url=url)
    
    def test_serialization(self):
        """Test model serialization."""
        config = ServiceConfig(
            type="native-api",
            health_check_url="http://localhost:8080"
        )
        data = config.model_dump()
        assert data["type"] == "native-api"
        assert str(data["health_check_url"]) == "http://localhost:8080/"
    
    def test_from_dict(self):
        """Test creating ServiceConfig from dictionary."""
        data = {
            "type": "remote-api",
            "health_check_url": "https://api.example.com/health"
        }
        config = ServiceConfig(**data)
        assert config.type == "remote-api"
        assert str(config.health_check_url) == "https://api.example.com/health"


class TestPlatformConfig:
    """Test PlatformConfig model."""
    
    def test_basic_functionality(self):
        """Test basic PlatformConfig functionality."""
        config = PlatformConfig(compose_file="docker-compose.nvidia.yml")
        assert config.compose_file == "docker-compose.nvidia.yml"
    
    def test_empty_compose_file(self):
        """Test empty compose file."""
        config = PlatformConfig(compose_file="")
        assert config.compose_file == ""
    
    def test_missing_compose_file(self):
        """Test missing compose_file raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PlatformConfig()
        assert "Field required" in str(exc_info.value)
    
    def test_serialization(self):
        """Test PlatformConfig serialization."""
        config = PlatformConfig(compose_file="docker-compose.apple.yml")
        data = config.model_dump()
        assert data == {"compose_file": "docker-compose.apple.yml"}


class TestExtensionsConfig:
    """Test ExtensionsConfig model."""
    
    def test_defaults(self):
        """Test ExtensionsConfig default values."""
        config = ExtensionsConfig()
        assert config.enabled == []
        assert config.config == {}
    
    def test_with_values(self):
        """Test ExtensionsConfig with explicit values."""
        config = ExtensionsConfig(
            enabled=["ext1", "ext2"],
            config={"ext1": {"param": "value"}}
        )
        assert config.enabled == ["ext1", "ext2"]
        assert config.config == {"ext1": {"param": "value"}}
    
    def test_factory_independence(self):
        """Test that default factories create independent instances."""
        config1 = ExtensionsConfig()
        config2 = ExtensionsConfig()
        
        config1.enabled.append("ext1")
        config1.config["key"] = "value"
        
        assert config2.enabled == []
        assert config2.config == {}
    
    def test_serialization(self):
        """Test ExtensionsConfig serialization."""
        config = ExtensionsConfig(
            enabled=["extension1"],
            config={"ext_setting": True}
        )
        data = config.model_dump()
        assert data == {
            "enabled": ["extension1"],
            "config": {"ext_setting": True}
        }


class TestAppConfig:
    """Test AppConfig model."""
    
    def test_defaults(self):
        """Test AppConfig default values."""
        config = AppConfig()
        
        # Check project name generation
        assert config.project_name.startswith("ollama-stack-")
        assert len(config.project_name) == len("ollama-stack-") + 8  # 8 hex chars
        
        # Check default services
        assert len(config.services) == 3
        assert "ollama" in config.services
        assert "webui" in config.services
        assert "mcp_proxy" in config.services
        
        # Check other defaults
        assert config.docker_compose_file == "docker-compose.yml"
        assert config.data_directory == "~/.ollama-stack/data"
        assert config.backup_directory == "~/.ollama-stack/backups"
        assert len(config.webui_secret_key) == 32  # UUID hex is 32 chars
        assert config.platform == {}
        assert isinstance(config.extensions, ExtensionsConfig)
    
    def test_project_name_uniqueness(self):
        """Test that project names are unique across instances."""
        config1 = AppConfig()
        config2 = AppConfig()
        assert config1.project_name != config2.project_name
    
    def test_webui_secret_key_uniqueness(self):
        """Test that WebUI secret keys are unique across instances."""
        config1 = AppConfig()
        config2 = AppConfig()
        assert config1.webui_secret_key != config2.webui_secret_key
    
    def test_services_factory_independence(self):
        """Test that services dictionary is independent across instances."""
        config1 = AppConfig()
        config2 = AppConfig()
        
        config1.services["new_service"] = ServiceConfig(type="native-api")
        assert "new_service" not in config2.services
    
    def test_custom_values(self):
        """Test AppConfig with custom values."""
        custom_services = {
            "custom_service": ServiceConfig(type="remote-api")
        }
        custom_platform = {
            "custom": PlatformConfig(compose_file="custom.yml")
        }
        
        config = AppConfig(
            project_name="custom-project",
            services=custom_services,
            docker_compose_file="custom-compose.yml",
            data_directory="/custom/data",
            backup_directory="/custom/backups",
            webui_secret_key="custom-secret",
            platform=custom_platform
        )
        
        assert config.project_name == "custom-project"
        assert config.services == custom_services
        assert config.docker_compose_file == "custom-compose.yml"
        assert config.data_directory == "/custom/data"
        assert config.backup_directory == "/custom/backups"
        assert config.webui_secret_key == "custom-secret"
        assert config.platform == custom_platform
    
    def test_nested_model_validation(self):
        """Test validation of nested models."""
        with pytest.raises(ValidationError):
            AppConfig(services={"invalid": {"type": "invalid-type"}})
    
    def test_serialization_excludes_sensitive_data(self):
        """Test that serialization can exclude sensitive fields."""
        config = AppConfig(webui_secret_key="secret123")
        
        # Normal serialization includes all fields
        full_data = config.model_dump()
        assert "webui_secret_key" in full_data
        
        # Serialization with exclusions
        safe_data = config.model_dump(exclude={"webui_secret_key"})
        assert "webui_secret_key" not in safe_data


class TestResourceUsage:
    """Test ResourceUsage model."""
    
    def test_defaults(self):
        """Test ResourceUsage default values."""
        usage = ResourceUsage()
        assert usage.cpu_percent is None
        assert usage.memory_mb is None
    
    def test_with_values(self):
        """Test ResourceUsage with explicit values."""
        usage = ResourceUsage(cpu_percent=25.5, memory_mb=128.0)
        assert usage.cpu_percent == 25.5
        assert usage.memory_mb == 128.0
    
    def test_zero_values(self):
        """Test ResourceUsage with zero values."""
        usage = ResourceUsage(cpu_percent=0.0, memory_mb=0.0)
        assert usage.cpu_percent == 0.0
        assert usage.memory_mb == 0.0
    
    def test_negative_values(self):
        """Test ResourceUsage with negative values."""
        usage = ResourceUsage(cpu_percent=-1.0, memory_mb=-1.0)
        assert usage.cpu_percent == -1.0
        assert usage.memory_mb == -1.0
    
    def test_invalid_types(self):
        """Test ResourceUsage with invalid types."""
        with pytest.raises(ValidationError):
            ResourceUsage(cpu_percent="not-a-number")
        
        with pytest.raises(ValidationError):
            ResourceUsage(memory_mb="not-a-number")


class TestServiceStatus:
    """Test ServiceStatus model."""
    
    def test_minimal_required(self):
        """Test ServiceStatus with minimal required fields."""
        status = ServiceStatus(name="test-service", is_running=True)
        assert status.name == "test-service"
        assert status.is_running is True
        assert status.status is None
        assert status.health is None
        assert status.ports == {}
        assert isinstance(status.usage, ResourceUsage)
    
    def test_full_fields(self):
        """Test ServiceStatus with all fields."""
        usage = ResourceUsage(cpu_percent=50.0, memory_mb=256.0)
        ports = {"8080/tcp": 8080, "8443/tcp": 8443}
        
        status = ServiceStatus(
            name="full-service",
            is_running=True,
            status="running",
            health="healthy",
            ports=ports,
            usage=usage
        )
        
        assert status.name == "full-service"
        assert status.is_running is True
        assert status.status == "running"
        assert status.health == "healthy"
        assert status.ports == ports
        assert status.usage == usage
    
    def test_ports_with_none_values(self):
        """Test ServiceStatus with None values in ports."""
        ports = {"8080/tcp": 8080, "8443/tcp": None}
        status = ServiceStatus(name="test", is_running=True, ports=ports)
        assert status.ports == ports
    
    def test_usage_factory_default(self):
        """Test that usage field gets default ResourceUsage instance."""
        status = ServiceStatus(name="test", is_running=True)
        assert isinstance(status.usage, ResourceUsage)
        assert status.usage.cpu_percent is None
        assert status.usage.memory_mb is None
    
    def test_missing_required_fields(self):
        """Test ValidationError for missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ServiceStatus()
        assert "Field required" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            ServiceStatus(name="test")
        assert "Field required" in str(exc_info.value)


class TestExtensionStatus:
    """Test ExtensionStatus model (inherits from ServiceStatus)."""
    
    def test_inheritance(self):
        """Test ExtensionStatus inherits from ServiceStatus."""
        assert issubclass(ExtensionStatus, ServiceStatus)
    
    def test_minimal_required(self):
        """Test ExtensionStatus with minimal required fields."""
        status = ExtensionStatus(name="test-ext", is_running=True, is_enabled=True)
        assert status.name == "test-ext"
        assert status.is_running is True
        assert status.is_enabled is True
        assert isinstance(status.usage, ResourceUsage)
    
    def test_full_fields(self):
        """Test ExtensionStatus with all fields."""
        usage = ResourceUsage(cpu_percent=25.0, memory_mb=128.0)
        
        status = ExtensionStatus(
            name="full-ext",
            is_running=False,
            is_enabled=True,
            status="stopped",
            health="unhealthy",
            ports={"9000/tcp": 9000},
            usage=usage
        )
        
        assert status.name == "full-ext"
        assert status.is_running is False
        assert status.is_enabled is True
        assert status.status == "stopped"
        assert status.health == "unhealthy"
        assert status.ports == {"9000/tcp": 9000}
        assert status.usage == usage
    
    def test_missing_extension_specific_field(self):
        """Test ValidationError for missing is_enabled field."""
        with pytest.raises(ValidationError) as exc_info:
            ExtensionStatus(name="test", is_running=True)
        assert "Field required" in str(exc_info.value)


class TestStackStatus:
    """Test StackStatus model."""
    
    def test_empty_lists(self):
        """Test StackStatus with empty lists."""
        status = StackStatus(core_services=[], extensions=[])
        assert status.core_services == []
        assert status.extensions == []
    
    def test_with_services(self):
        """Test StackStatus with services and extensions."""
        service = ServiceStatus(name="service1", is_running=True)
        extension = ExtensionStatus(name="ext1", is_running=False, is_enabled=True)
        
        status = StackStatus(
            core_services=[service],
            extensions=[extension]
        )
        
        assert len(status.core_services) == 1
        assert len(status.extensions) == 1
        assert status.core_services[0] == service
        assert status.extensions[0] == extension
    
    def test_multiple_services(self):
        """Test StackStatus with multiple services."""
        services = [
            ServiceStatus(name="service1", is_running=True),
            ServiceStatus(name="service2", is_running=False)
        ]
        extensions = [
            ExtensionStatus(name="ext1", is_running=True, is_enabled=True),
            ExtensionStatus(name="ext2", is_running=False, is_enabled=False)
        ]
        
        status = StackStatus(core_services=services, extensions=extensions)
        assert len(status.core_services) == 2
        assert len(status.extensions) == 2
    
    def test_invalid_service_types(self):
        """Test StackStatus with invalid service types in lists."""
        with pytest.raises(ValidationError):
            StackStatus(core_services=["not-a-service"], extensions=[])
        
        with pytest.raises(ValidationError):
            StackStatus(core_services=[], extensions=["not-an-extension"])


class TestEnvironmentCheck:
    """Test EnvironmentCheck model."""
    
    def test_minimal_required(self):
        """Test EnvironmentCheck with minimal required fields."""
        check = EnvironmentCheck(name="Test Check", passed=True)
        assert check.name == "Test Check"
        assert check.passed is True
        assert check.details is None
        assert check.suggestion is None
    
    def test_full_fields(self):
        """Test EnvironmentCheck with all fields."""
        check = EnvironmentCheck(
            name="Docker Check",
            passed=False,
            details="Docker daemon is not running",
            suggestion="Start Docker Desktop"
        )
        
        assert check.name == "Docker Check"
        assert check.passed is False
        assert check.details == "Docker daemon is not running"
        assert check.suggestion == "Start Docker Desktop"
    
    def test_missing_required_fields(self):
        """Test ValidationError for missing required fields."""
        with pytest.raises(ValidationError):
            EnvironmentCheck()
        
        with pytest.raises(ValidationError):
            EnvironmentCheck(name="Test")
        
        with pytest.raises(ValidationError):
            EnvironmentCheck(passed=True)


class TestCheckReport:
    """Test CheckReport model."""
    
    def test_empty_checks(self):
        """Test CheckReport with empty checks list."""
        report = CheckReport(checks=[])
        assert report.checks == []
    
    def test_with_checks(self):
        """Test CheckReport with multiple checks."""
        checks = [
            EnvironmentCheck(name="Check 1", passed=True),
            EnvironmentCheck(name="Check 2", passed=False, details="Failed")
        ]
        
        report = CheckReport(checks=checks)
        assert len(report.checks) == 2
        assert report.checks == checks
    
    def test_invalid_check_types(self):
        """Test CheckReport with invalid check types."""
        with pytest.raises(ValidationError):
            CheckReport(checks=["not-a-check"])


class TestBackupConfig:
    """Test BackupConfig model."""
    
    def test_defaults(self):
        """Test BackupConfig default values."""
        config = BackupConfig()
        assert config.include_volumes is True
        assert config.include_config is True
        assert config.include_extensions is True
        assert config.compression is True
        assert config.encryption is False
        assert config.exclude_patterns == []
    
    def test_custom_values(self):
        """Test BackupConfig with custom values."""
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
    
    def test_factory_independence(self):
        """Test that exclude_patterns lists are independent."""
        config1 = BackupConfig()
        config2 = BackupConfig()
        
        config1.exclude_patterns.append("*.tmp")
        assert config2.exclude_patterns == []
    
    def test_all_boolean_combinations(self):
        """Test all combinations of boolean flags."""
        for include_volumes in [True, False]:
            for include_config in [True, False]:
                for include_extensions in [True, False]:
                    for compression in [True, False]:
                        for encryption in [True, False]:
                            config = BackupConfig(
                                include_volumes=include_volumes,
                                include_config=include_config,
                                include_extensions=include_extensions,
                                compression=compression,
                                encryption=encryption
                            )
                            assert config.include_volumes == include_volumes
                            assert config.include_config == include_config
                            assert config.include_extensions == include_extensions
                            assert config.compression == compression
                            assert config.encryption == encryption


class TestBackupManifest:
    """Test BackupManifest model."""
    
    def test_minimal_required(self):
        """Test BackupManifest with minimal required fields."""
        backup_config = BackupConfig()
        manifest = BackupManifest(
            stack_version="0.2.0",
            cli_version="0.2.0",
            platform="linux",
            backup_config=backup_config
        )
        
        assert manifest.stack_version == "0.2.0"
        assert manifest.cli_version == "0.2.0"
        assert manifest.platform == "linux"
        assert manifest.backup_config == backup_config
        assert isinstance(manifest.backup_id, str)
        assert len(manifest.backup_id) == 32  # UUID hex length
        assert isinstance(manifest.created_at, datetime)
        assert manifest.volumes == []
        assert manifest.config_files == []
        assert manifest.extensions == []
        assert manifest.checksum is None
        assert manifest.size_bytes is None
        assert manifest.description is None
    
    def test_full_fields(self):
        """Test BackupManifest with all fields."""
        backup_config = BackupConfig(compression=True, encryption=True)
        
        manifest = BackupManifest(
            stack_version="0.2.0",
            cli_version="0.2.0",
            platform="darwin",
            backup_config=backup_config,
            volumes=["vol1", "vol2"],
            config_files=[".env", ".config"],
            extensions=["ext1", "ext2"],
            checksum="abc123",
            size_bytes=1024,
            description="Test backup"
        )
        
        assert manifest.volumes == ["vol1", "vol2"]
        assert manifest.config_files == [".env", ".config"]
        assert manifest.extensions == ["ext1", "ext2"]
        assert manifest.checksum == "abc123"
        assert manifest.size_bytes == 1024
        assert manifest.description == "Test backup"
    
    def test_auto_generated_fields_uniqueness(self):
        """Test that auto-generated fields are unique."""
        backup_config = BackupConfig()
        
        manifest1 = BackupManifest(
            stack_version="0.2.0",
            cli_version="0.2.0",
            platform="linux",
            backup_config=backup_config
        )
        
        manifest2 = BackupManifest(
            stack_version="0.2.0",
            cli_version="0.2.0",
            platform="linux",
            backup_config=backup_config
        )
        
        assert manifest1.backup_id != manifest2.backup_id
        # created_at might be the same if created very quickly, but that's okay
    
    def test_factory_independence(self):
        """Test that list fields are independent across instances."""
        backup_config = BackupConfig()
        
        manifest1 = BackupManifest(
            stack_version="0.2.0",
            cli_version="0.2.0",
            platform="linux",
            backup_config=backup_config
        )
        
        manifest2 = BackupManifest(
            stack_version="0.2.0",
            cli_version="0.2.0",
            platform="linux",
            backup_config=backup_config
        )
        
        manifest1.volumes.append("vol1")
        manifest1.config_files.append(".env")
        manifest1.extensions.append("ext1")
        
        assert manifest2.volumes == []
        assert manifest2.config_files == []
        assert manifest2.extensions == []
    
    def test_missing_required_fields(self):
        """Test ValidationError for missing required fields."""
        with pytest.raises(ValidationError):
            BackupManifest()
        
        with pytest.raises(ValidationError):
            BackupManifest(stack_version="0.2.0")
    
    def test_nested_backup_config_validation(self):
        """Test validation of nested BackupConfig."""
        with pytest.raises(ValidationError):
            BackupManifest(
                stack_version="0.2.0",
                cli_version="0.2.0",
                platform="linux",
                backup_config="not-a-backup-config"
            )


class TestMigrationInfo:
    """Test MigrationInfo model."""
    
    def test_minimal_required(self):
        """Test MigrationInfo with minimal required fields."""
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
    
    def test_full_fields(self):
        """Test MigrationInfo with all fields."""
        migration = MigrationInfo(
            from_version="0.2.0",
            to_version="0.4.0",
            migration_path=["0.2.1", "0.3.0"],
            backup_required=False,
            breaking_changes=["Config format changed", "API changes"],
            migration_steps=["Update config", "Migrate data", "Restart services"],
            estimated_duration="10 minutes"
        )
        
        assert migration.from_version == "0.2.0"
        assert migration.to_version == "0.4.0"
        assert migration.migration_path == ["0.2.1", "0.3.0"]
        assert migration.backup_required is False
        assert migration.breaking_changes == ["Config format changed", "API changes"]
        assert migration.migration_steps == ["Update config", "Migrate data", "Restart services"]
        assert migration.estimated_duration == "10 minutes"
    
    def test_factory_independence(self):
        """Test that list fields are independent across instances."""
        migration1 = MigrationInfo(from_version="0.2.0", to_version="0.3.0")
        migration2 = MigrationInfo(from_version="0.2.0", to_version="0.3.0")
        
        migration1.migration_path.append("0.2.1")
        migration1.breaking_changes.append("Change 1")
        migration1.migration_steps.append("Step 1")
        
        assert migration2.migration_path == []
        assert migration2.breaking_changes == []
        assert migration2.migration_steps == []
    
    def test_missing_required_fields(self):
        """Test ValidationError for missing required fields."""
        with pytest.raises(ValidationError):
            MigrationInfo()
        
        with pytest.raises(ValidationError):
            MigrationInfo(from_version="0.2.0")
        
        with pytest.raises(ValidationError):
            MigrationInfo(to_version="0.3.0")
    
    def test_empty_lists(self):
        """Test MigrationInfo with explicitly empty lists."""
        migration = MigrationInfo(
            from_version="0.2.0",
            to_version="0.3.0",
            migration_path=[],
            breaking_changes=[],
            migration_steps=[]
        )
        
        assert migration.migration_path == []
        assert migration.breaking_changes == []
        assert migration.migration_steps == []


class TestSerialization:
    """Test serialization and deserialization of all models."""
    
    def test_round_trip_serialization(self):
        """Test that all models can be serialized and deserialized."""
        # Create a complex nested structure
        app_config = AppConfig(
            project_name="test-project",
            services={
                "service1": ServiceConfig(type="docker"),
                "service2": ServiceConfig(type="native-api", health_check_url="http://localhost:8080")
            },
            platform={
                "apple": PlatformConfig(compose_file="docker-compose.apple.yml")
            },
            extensions=ExtensionsConfig(
                enabled=["ext1"],
                config={"ext1": {"setting": "value"}}
            )
        )
        
        # Serialize to dict
        data = app_config.model_dump()
        
        # Deserialize back
        restored_config = AppConfig(**data)
        
        # Verify the data matches
        assert restored_config.project_name == app_config.project_name
        assert restored_config.services.keys() == app_config.services.keys()
        assert restored_config.platform.keys() == app_config.platform.keys()
        assert restored_config.extensions.enabled == app_config.extensions.enabled
    
    def test_json_serialization(self):
        """Test JSON serialization of models."""
        backup_config = BackupConfig(compression=True)
        manifest = BackupManifest(
            stack_version="0.2.0",
            cli_version="0.2.0",
            platform="linux",
            backup_config=backup_config,
            description="Test backup"
        )
        
        # Test JSON serialization
        json_str = manifest.model_dump_json()
        assert isinstance(json_str, str)
        assert "stack_version" in json_str
        assert "backup_config" in json_str
        
        # Test JSON deserialization
        import json
        data = json.loads(json_str)
        restored_manifest = BackupManifest(**data)
        assert restored_manifest.stack_version == manifest.stack_version
        assert restored_manifest.description == manifest.description


class TestValidationEdgeCases:
    """Test edge cases and validation scenarios."""
    
    def test_none_values_where_not_allowed(self):
        """Test that None values raise ValidationError where not allowed."""
        with pytest.raises(ValidationError):
            ServiceStatus(name=None, is_running=True)
        
        with pytest.raises(ValidationError):
            ServiceStatus(name="test", is_running=None)
    
    def test_empty_string_handling(self):
        """Test handling of empty strings."""
        # Empty strings should be allowed for optional string fields
        check = EnvironmentCheck(name="", passed=True, details="", suggestion="")
        assert check.name == ""
        assert check.details == ""
        assert check.suggestion == ""
    
    def test_type_coercion(self):
        """Test Pydantic type coercion."""
        # String to bool coercion
        status = ServiceStatus(name="test", is_running="true")
        assert status.is_running is True
        
        # Test that invalid type coercion raises ValidationError
        with pytest.raises(ValidationError):
            PlatformConfig(compose_file=123)
    
    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored by default."""
        data = {
            "name": "test",
            "is_running": True,
            "extra_field": "ignored"
        }
        status = ServiceStatus(**data)
        assert status.name == "test"
        assert status.is_running is True
        assert not hasattr(status, "extra_field")
    
    def test_deeply_nested_validation(self):
        """Test validation in deeply nested structures."""
        with pytest.raises(ValidationError):
            AppConfig(
                services={
                    "invalid": {
                        "type": "invalid-type",
                        "health_check_url": "not-a-url"
                    }
                }
            )
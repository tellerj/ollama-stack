# Integration Test Docker Image Sandbox

This directory contains a Docker image sandbox system that eliminates the need to download Docker images during every test run, significantly reducing integration test execution time.

## Overview

The sandbox system:
- **Saves** Docker images to local tar files after the first download
- **Loads** images from local cache for subsequent test runs
- **Manages** a persistent cache of images between test sessions
- **Eliminates** the 10-minute image download delays that were causing test timeouts

## Quick Start

### 1. Initial Setup (One-time)

```bash
# Download and cache all required images
python tools/setup_test_images.py setup
```

This will:
- Pull all required Docker images (`ghcr.io/open-webui/open-webui:main`, `traefik:v2.10`, `postgres:15`)
- Save them to local tar files in `/tmp/ollama-stack-test-images/`
- This step takes ~10 minutes but only needs to be done once

### 2. Before Running Tests

```bash
# Load cached images into Docker
python tools/setup_test_images.py load
```

This will:
- Load all cached images into Docker from tar files
- Takes ~30 seconds instead of 10 minutes
- Ensures all required images are available for tests

### 3. Running Integration Tests

```bash
# Run tests with sandboxed environment
pytest tests/integration/test_uninstall_integration.py::test_uninstall_preserves_images_by_default -v
```

Tests will use the `sandboxed_test_environment` fixture which automatically ensures images are loaded.

## Management Commands

### Check Status
```bash
python tools/setup_test_images.py status
```

### View Detailed Information
```bash
python tools/setup_test_images.py info
```

### Clean Cache (if needed)
```bash
python tools/setup_test_images.py clean
```

## How It Works

### Image Sandbox (`image_sandbox.py`)
- `DockerImageSandbox` class manages the local image cache
- Images are saved as tar files using `docker save`
- Images are loaded using `docker load`
- Cache is persistent across test sessions

### Test Fixtures (`conftest.py`)
- `docker_image_sandbox` (session-scoped): Sets up the sandbox for the entire test session
- `sandboxed_test_environment` (function-scoped): Ensures images are loaded for each test

### Updated Tests
- `test_uninstall_preserves_images_by_default`: Verifies images are preserved without `--remove-images`
- `test_uninstall_removes_images_with_flag`: Verifies images are removed with `--remove-images`
- `test_uninstall_all_flag_removes_images`: Verifies `--all` flag removes images

## Benefits

1. **Fast Test Execution**: No more 10-minute image downloads
2. **Reliable Tests**: Images are always available locally
3. **Bandwidth Savings**: Images downloaded once, reused many times
4. **Consistent Environment**: Same image versions across all test runs
5. **Offline Testing**: Can run tests without internet connection after initial setup

## File Structure

```
tests/integration/
├── image_sandbox.py          # Core sandbox implementation
├── conftest.py               # Test fixtures
├── test_uninstall_integration.py  # Updated tests
└── README.md                 # This file

tools/
└── setup_test_images.py      # CLI management tool
```

## Cache Location

- Default: `/tmp/ollama-stack-test-images/`
- Can be customized by setting `OLLAMA_STACK_TEST_CACHE_DIR` environment variable
- Images are stored as tar files in the `images/` subdirectory

## Troubleshooting

### Images Not Loading
```bash
# Check if images are cached
python tools/setup_test_images.py status

# Re-download if needed
python tools/setup_test_images.py setup --force
```

### Cache Issues
```bash
# Clean and rebuild cache
python tools/setup_test_images.py clean
python tools/setup_test_images.py setup
```

### Test Failures
- Ensure `docker` is running and accessible
- Check that images are loaded: `python tools/setup_test_images.py status`
- Verify cache directory permissions

## CI/CD Integration

For CI/CD pipelines, you can:
1. Cache the sandbox directory between builds
2. Use `setup --force` to ensure fresh images when needed
3. Use `load` as a fast preparation step before tests

```yaml
# Example GitHub Actions step
- name: Setup test images
  run: |
    python tools/setup_test_images.py setup
    python tools/setup_test_images.py load
``` 
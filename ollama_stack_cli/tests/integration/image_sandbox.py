"""
Docker Image Sandbox for Integration Tests

This module provides utilities for managing Docker images in a local sandbox
environment to avoid long download times during integration tests.
"""

import os
import shutil
import subprocess
import tempfile
import platform
from pathlib import Path
from typing import Dict, List, Optional, Set
import logging

log = logging.getLogger(__name__)

# Platform detection
IS_APPLE_SILICON = platform.system() == "Darwin" and platform.machine() == "arm64"

class DockerImageSandbox:
    """
    Manages Docker images in a sandboxed environment for integration tests.
    
    This class provides methods to:
    - Save Docker images to local tar files
    - Load images from local tar files
    - Create isolated test environments with pre-loaded images
    - Clean up sandbox environments
    """
    
    def __init__(self, sandbox_dir: Optional[Path] = None):
        """
        Initialize the Docker image sandbox.
        
        Args:
            sandbox_dir: Directory to store sandbox files. If None, uses system temp directory.
        """
        self.sandbox_dir = sandbox_dir or Path(tempfile.gettempdir()) / "ollama-stack-test-images"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.image_store = self.sandbox_dir / "images"
        self.image_store.mkdir(parents=True, exist_ok=True)
        
        # Standard images used by ollama-stack
        # On Apple Silicon, ollama runs natively, so we don't need the Docker image
        self.stack_images = {
            "ghcr.io/open-webui/open-webui:main": "open-webui-main.tar",
            "ghcr.io/open-webui/mcpo:main": "open-webui-mcpo-main.tar",
            "alpine:latest": "alpine-latest.tar"
        }
        
        # Add ollama Docker image only on non-Apple Silicon platforms
        if not IS_APPLE_SILICON:
            self.stack_images["ollama/ollama:latest"] = "ollama-latest.tar"
        
    def save_image(self, image_name: str, filename: Optional[str] = None) -> bool:
        """
        Save a Docker image to a tar file in the sandbox.
        
        Args:
            image_name: Name of the Docker image to save
            filename: Optional filename. If None, generates from image name
            
        Returns:
            True if successful, False otherwise
        """
        if filename is None:
            filename = self._get_image_filename(image_name)
            
        tar_path = self.image_store / filename
        
        try:
            log.info(f"Saving Docker image {image_name} to {tar_path}")
            
            # Check if image is already available locally
            if not self.is_image_loaded(image_name):
                log.info(f"Image {image_name} not found locally, pulling...")
                # Pull the image since it's not available locally
                result = subprocess.run(
                    ["docker", "pull", image_name],
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minutes timeout
                )
                
                if result.returncode != 0:
                    log.error(f"Failed to pull image {image_name}: {result.stderr}")
                    return False
            else:
                log.info(f"Image {image_name} already available locally, skipping pull")
            
            # Save the image to a tar file
            result = subprocess.run(
                ["docker", "save", "-o", str(tar_path), image_name],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode != 0:
                log.error(f"Failed to save image {image_name}: {result.stderr}")
                return False
                
            log.info(f"Successfully saved image {image_name} to {tar_path}")
            return True
            
        except subprocess.TimeoutExpired:
            log.error(f"Timeout saving image {image_name}")
            return False
        except Exception as e:
            log.error(f"Error saving image {image_name}: {e}")
            return False
    
    def load_image(self, image_name: str, filename: Optional[str] = None) -> bool:
        """
        Load a Docker image from a tar file in the sandbox.
        
        Args:
            image_name: Name of the Docker image to load
            filename: Optional filename. If None, generates from image name
            
        Returns:
            True if successful, False otherwise
        """
        if filename is None:
            filename = self._get_image_filename(image_name)
            
        tar_path = self.image_store / filename
        
        if not tar_path.exists():
            log.error(f"Image tar file not found: {tar_path}")
            return False
            
        try:
            log.info(f"Loading Docker image {image_name} from {tar_path}")
            
            result = subprocess.run(
                ["docker", "load", "-i", str(tar_path)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode != 0:
                log.error(f"Failed to load image {image_name}: {result.stderr}")
                return False
                
            log.info(f"Successfully loaded image {image_name}")
            return True
            
        except subprocess.TimeoutExpired:
            log.error(f"Timeout loading image {image_name}")
            return False
        except Exception as e:
            log.error(f"Error loading image {image_name}: {e}")
            return False
    
    def is_image_cached(self, image_name: str) -> bool:
        """
        Check if an image is cached in the sandbox.
        
        Args:
            image_name: Name of the Docker image
            
        Returns:
            True if image is cached, False otherwise
        """
        filename = self._get_image_filename(image_name)
        return (self.image_store / filename).exists()
    
    def is_image_loaded(self, image_name: str) -> bool:
        """
        Check if an image is loaded in Docker.
        
        Args:
            image_name: Name of the Docker image
            
        Returns:
            True if image is loaded in Docker, False otherwise
        """
        try:
            result = subprocess.run(
                ["docker", "images", "-q", image_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return result.returncode == 0 and bool(result.stdout.strip())
            
        except Exception:
            return False
    
    def setup_stack_images(self, force_pull: bool = False) -> bool:
        """
        Set up all standard ollama-stack images in the sandbox.
        
        Args:
            force_pull: If True, re-pulls and saves images even if cached
            
        Returns:
            True if all images were successfully set up, False otherwise
        """
        success = True
        
        for image_name, filename in self.stack_images.items():
            if force_pull or not self.is_image_cached(image_name):
                if not self.save_image(image_name, filename):
                    success = False
                    log.error(f"Failed to save image {image_name}")
            else:
                log.info(f"Image {image_name} already cached as {filename}")
                
        return success
    
    def load_stack_images(self) -> bool:
        """
        Load all standard ollama-stack images from the sandbox.
        
        Returns:
            True if all images were successfully loaded, False otherwise
        """
        success = True
        
        for image_name, filename in self.stack_images.items():
            if not self.is_image_loaded(image_name):
                if not self.load_image(image_name, filename):
                    success = False
                    log.error(f"Failed to load image {image_name}")
            else:
                log.info(f"Image {image_name} already loaded")
                
        return success
    
    def clean_sandbox(self) -> bool:
        """
        Clean up the sandbox directory.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.sandbox_dir.exists():
                shutil.rmtree(self.sandbox_dir)
                log.info(f"Cleaned up sandbox directory: {self.sandbox_dir}")
            return True
        except Exception as e:
            log.error(f"Error cleaning sandbox: {e}")
            return False
    
    def get_sandbox_info(self) -> Dict:
        """
        Get information about the current sandbox state.
        
        Returns:
            Dictionary with sandbox information
        """
        info = {
            "sandbox_dir": str(self.sandbox_dir),
            "image_store": str(self.image_store),
            "cached_images": [],
            "loaded_images": [],
            "total_cache_size": 0
        }
        
        for image_name, filename in self.stack_images.items():
            tar_path = self.image_store / filename
            
            if tar_path.exists():
                info["cached_images"].append({
                    "image": image_name,
                    "filename": filename,
                    "size": tar_path.stat().st_size
                })
                info["total_cache_size"] += tar_path.stat().st_size
                
            if self.is_image_loaded(image_name):
                info["loaded_images"].append(image_name)
                
        return info
    
    def _get_image_filename(self, image_name: str) -> str:
        """
        Generate a filename for an image tar file.
        
        Args:
            image_name: Name of the Docker image
            
        Returns:
            Filename for the tar file
        """
        if image_name in self.stack_images:
            return self.stack_images[image_name]
        
        # Generate filename from image name
        filename = image_name.replace(":", "-").replace("/", "-").replace(".", "-")
        return f"{filename}.tar"
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - optionally clean up."""
        # Don't auto-clean to preserve images between test runs
        pass


# Convenience functions for integration tests
def setup_test_images(force_pull: bool = False) -> bool:
    """
    Set up Docker images for integration tests.
    
    Args:
        force_pull: If True, re-pulls images even if cached
        
    Returns:
        True if successful, False otherwise
    """
    with DockerImageSandbox() as sandbox:
        return sandbox.setup_stack_images(force_pull=force_pull)


def load_test_images() -> bool:
    """
    Load Docker images for integration tests.
    
    Returns:
        True if successful, False otherwise
    """
    with DockerImageSandbox() as sandbox:
        return sandbox.load_stack_images()


def clean_test_images() -> bool:
    """
    Clean up test image cache.
    
    Returns:
        True if successful, False otherwise
    """
    with DockerImageSandbox() as sandbox:
        return sandbox.clean_sandbox()


def get_test_image_info() -> Dict:
    """
    Get information about test image cache.
    
    Returns:
        Dictionary with cache information
    """
    with DockerImageSandbox() as sandbox:
        return sandbox.get_sandbox_info() 
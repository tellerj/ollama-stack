#!/usr/bin/env python3
"""
Test Image Sandbox Management Tool

This tool helps manage Docker images for integration tests by providing
commands to setup, load, clean, and inspect the image sandbox.
"""

import argparse
import sys
import json
from pathlib import Path

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.integration.image_sandbox import (
    setup_test_images,
    load_test_images,
    clean_test_images,
    get_test_image_info,
    DockerImageSandbox
)


def format_size(size_bytes):
    """Format file size in human-readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def cmd_setup(args):
    """Set up Docker images for testing."""
    print("Setting up test images...")
    
    success = setup_test_images(force_pull=args.force)
    
    if success:
        print("✅ Test images setup completed successfully")
        return 0
    else:
        print("❌ Failed to setup test images")
        return 1


def cmd_load(args):
    """Load Docker images for testing."""
    print("Loading test images...")
    
    success = load_test_images()
    
    if success:
        print("✅ Test images loaded successfully")
        return 0
    else:
        print("❌ Failed to load test images")
        return 1


def cmd_clean(args):
    """Clean up test image cache."""
    print("Cleaning test image cache...")
    
    success = clean_test_images()
    
    if success:
        print("✅ Test image cache cleaned successfully")
        return 0
    else:
        print("❌ Failed to clean test image cache")
        return 1


def cmd_info(args):
    """Display information about the test image cache."""
    info = get_test_image_info()
    
    if args.json:
        print(json.dumps(info, indent=2))
        return 0
    
    print("🗂️  Test Image Sandbox Information")
    print("=" * 40)
    print(f"Sandbox Directory: {info['sandbox_dir']}")
    print(f"Image Store: {info['image_store']}")
    print(f"Total Cache Size: {format_size(info['total_cache_size'])}")
    print()
    
    print("📦 Cached Images:")
    if info['cached_images']:
        for img in info['cached_images']:
            print(f"  • {img['image']} ({format_size(img['size'])})")
    else:
        print("  None")
    print()
    
    print("🔄 Loaded Images:")
    if info['loaded_images']:
        for img in info['loaded_images']:
            print(f"  • {img}")
    else:
        print("  None")
    
    return 0


def cmd_status(args):
    """Check the status of the test image sandbox."""
    info = get_test_image_info()
    
    cached_count = len(info['cached_images'])
    loaded_count = len(info['loaded_images'])
    total_size = info['total_cache_size']
    
    print("🔍 Test Image Sandbox Status")
    print("=" * 30)
    
    if cached_count > 0:
        print(f"✅ {cached_count} images cached ({format_size(total_size)})")
    else:
        print("❌ No images cached")
    
    if loaded_count > 0:
        print(f"✅ {loaded_count} images loaded in Docker")
    else:
        print("❌ No images loaded in Docker")
    
    # Check if all required images are ready
    with DockerImageSandbox() as sandbox:
        required_images = list(sandbox.stack_images.keys())
        ready_images = [img for img in required_images if sandbox.is_image_loaded(img)]
        
        if len(ready_images) == len(required_images):
            print("✅ All required images are ready for testing")
        else:
            missing = len(required_images) - len(ready_images)
            print(f"⚠️  {missing} required images are not ready")
            print("   Run 'python tools/setup_test_images.py load' to load them")
    
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage Docker images for integration tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Set up test images (download and cache)
  python tools/setup_test_images.py setup
  
  # Load cached images into Docker
  python tools/setup_test_images.py load
  
  # Check status
  python tools/setup_test_images.py status
  
  # Show detailed information
  python tools/setup_test_images.py info
  
  # Clean up cache
  python tools/setup_test_images.py clean
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Set up test images')
    setup_parser.add_argument('--force', action='store_true',
                             help='Force re-download even if cached')
    setup_parser.set_defaults(func=cmd_setup)
    
    # Load command
    load_parser = subparsers.add_parser('load', help='Load test images')
    load_parser.set_defaults(func=cmd_load)
    
    # Clean command
    clean_parser = subparsers.add_parser('clean', help='Clean test image cache')
    clean_parser.set_defaults(func=cmd_clean)
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show sandbox information')
    info_parser.add_argument('--json', action='store_true',
                            help='Output in JSON format')
    info_parser.set_defaults(func=cmd_info)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Check sandbox status')
    status_parser.set_defaults(func=cmd_status)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main()) 
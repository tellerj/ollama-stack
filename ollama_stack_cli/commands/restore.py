"""
Restore command implementation for the Ollama Stack CLI.

This module handles restoring the stack from backups with comprehensive
validation and conflict resolution.
"""

import typer
import logging
from pathlib import Path
from typing_extensions import Annotated
from typing import Optional

from ..context import AppContext

log = logging.getLogger(__name__)


def restore_stack_logic(
    app_context: AppContext,
    backup_path: str,
    include_volumes: bool = True,
    validate_only: bool = False,
    force: bool = False
) -> bool:
    """Business logic for restoring stack from backup."""
    
    backup_dir = Path(backup_path).expanduser().resolve()
    
    # Validate backup directory exists
    if not backup_dir.exists():
        log.error(f"Backup directory not found: {backup_dir}")
        return False
    
    if not backup_dir.is_dir():
        log.error(f"Backup path is not a directory: {backup_dir}")
        return False
    
    # Check for backup manifest
    manifest_file = backup_dir / "backup_manifest.json"
    if not manifest_file.exists():
        log.error(f"Backup manifest not found: {manifest_file}")
        log.error("This does not appear to be a valid backup directory")
        return False
    
    # Validate the backup first
    log.info("Validating backup integrity...")
    
    try:
        # First run validation to check backup integrity
        validation_success = app_context.stack_manager.restore_from_backup(
            backup_dir=backup_dir,
            validate_only=True
        )
        
        if not validation_success:
            log.error("Backup validation failed - cannot proceed with restore")
            return False
        
        log.info("Backup validation passed")
        
        if validate_only:
            log.info("Validation-only mode - restore not performed")
            log.info(f"Backup: {backup_dir}")
            log.info("Status: Valid and ready for restore")
            log.info(f"To restore this backup, run: ollama-stack restore {backup_dir}")
            return True
        
        # Check if stack is currently running
        if app_context.stack_manager.is_stack_running():
            log.warning("Stack is currently running")
            
            if not force:
                log.warning("The stack must be stopped before restoring from backup")
                log.warning("This will temporarily interrupt any running services")
                log.info("Use --force to automatically stop services during restore")
                
                if not typer.confirm("Do you want to stop the stack and proceed with restore?"):
                    log.info("Restore cancelled by user")
                    return False
        
        # Check for existing configuration conflicts
        from ..config import get_default_config_file, get_default_env_file
        
        existing_config = []
        config_file = get_default_config_file()
        env_file = get_default_env_file()
        if config_file.exists():
            existing_config.append(".ollama-stack.json")
        if env_file.exists():
            existing_config.append(".env")
        
        if existing_config and not force:
            log.warning("Existing configuration detected")
            log.warning(f"Found existing files: {', '.join(existing_config)}")
            log.warning("These will be overwritten during restore")
            log.info("Use --force to skip this confirmation")
            
            if not typer.confirm("Do you want to overwrite existing configuration?"):
                log.info("Restore cancelled by user")
                return False
        
        # Show what will be restored
        restore_items = ["Configuration files"]
        if include_volumes:
            restore_items.append("Docker volumes (models, conversations)")
        
        log.info(f"Restore will include: {', '.join(restore_items)}")
        
        # Perform the actual restore
        log.info(f"Restoring from backup: {backup_dir}")
        log.info("Starting restore process...")
        
        success = app_context.stack_manager.restore_from_backup(
            backup_dir=backup_dir,
            validate_only=False
        )
        
        if success:
            log.info("Restore completed successfully!")
            log.info(f"From: {backup_dir}")
            log.info(f"Restored: {', '.join(restore_items)}")
            log.info("Next steps:")
            log.info("  • Run 'ollama-stack start' to start services")
            log.info("  • Run 'ollama-stack status' to check health")
            
            return True
        else:
            log.error("Restore failed - check logs for details")
            return False
            
    except Exception as e:
        log.error(f"Restore failed with error: {e}")
        return False


def restore(
    ctx: typer.Context,
    backup_path: Annotated[
        str,
        typer.Argument(
            help="Path to the backup directory to restore from.",
        ),
    ],
    include_volumes: Annotated[
        bool,
        typer.Option(
            "--include-volumes/--no-volumes",
            help="Include Docker volumes in restore (models, conversations, databases).",
        ),
    ] = True,
    validate_only: Annotated[
        bool,
        typer.Option(
            "--validate-only",
            help="Only validate the backup without performing restore.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Skip confirmation prompts and automatically stop services if needed.",
        ),
    ] = False,
):
    """Restore the stack from a backup.
    
    This command restores the stack from a previously created backup,
    including configuration files and optionally Docker volumes.
    The backup is validated before restoration begins.
    
    Examples:
        ollama-stack restore ./my-backup           # Restore from backup directory
        ollama-stack restore ./backup --validate-only  # Only validate backup
        ollama-stack restore ./backup --force     # Skip confirmation prompts
        ollama-stack restore ./backup --no-volumes # Restore without volume data
    """
    app_context: AppContext = ctx.obj
    
    success = restore_stack_logic(
        app_context=app_context,
        backup_path=backup_path,
        include_volumes=include_volumes,
        validate_only=validate_only,
        force=force
    )
    
    if not success:
        raise typer.Exit(1) 
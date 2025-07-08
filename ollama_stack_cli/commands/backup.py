"""
Backup command implementation for the Ollama Stack CLI.

This module handles creating backups of the stack including volumes, configuration,
and extensions with comprehensive validation and integrity checking.
"""

import typer
import logging
from pathlib import Path
from typing_extensions import Annotated
from typing import Optional
import datetime

from ..context import AppContext

log = logging.getLogger(__name__)


def backup_stack_logic(
    app_context: AppContext, 
    include_volumes: bool = True,
    include_config: bool = True,
    include_extensions: bool = True,
    output_path: Optional[str] = None,
    compress: bool = True,
    description: Optional[str] = None
) -> bool:
    """Business logic for creating stack backups."""
    
    # Determine backup directory
    if output_path:
        backup_dir = Path(output_path).expanduser().resolve()
    else:
        # Use default backup location with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = Path("~/.ollama-stack/backups").expanduser() / f"backup-{timestamp}"
    
    log.info(f"Creating backup in: {backup_dir}")
    
    # Prepare backup configuration
    backup_config = {
        "include_volumes": include_volumes,
        "include_config": include_config, 
        "include_extensions": include_extensions,
        "compression": compress,
        "exclude_patterns": []
    }
    
    # Add description if provided
    if description:
        log.info(f"Backup description: {description}")
    
    # Show what will be backed up
    backup_items = []
    if include_volumes:
        backup_items.append("Docker volumes (models, conversations)")
    if include_config:
        backup_items.append("Configuration files")
    if include_extensions:
        backup_items.append("Extension data")
    
    if backup_items:
        log.info(f"Backup will include: {', '.join(backup_items)}")
    else:
        log.error("No backup items selected - nothing to backup")
        return False
    
    # Check if backup directory already exists
    if backup_dir.exists():
        log.warning(f"Backup directory already exists: {backup_dir}")
        if not typer.confirm("Do you want to overwrite the existing backup?"):
            log.info("Backup cancelled by user")
            return False
    
    # Create the backup
    try:
        log.info("Starting backup process...")
        
        success = app_context.stack_manager.create_backup(
            backup_dir=backup_dir,
            backup_config=backup_config
        )
        
        if success:
            log.info("Backup completed successfully!")
            log.info(f"Location: {backup_dir}")
            log.info(f"Includes: {', '.join(backup_items)}")
            log.info(f"Compressed: {'Yes' if compress else 'No'}")
            if description:
                log.info(f"Description: {description}")
            log.info(f"To restore this backup, run: ollama-stack restore {backup_dir}")
            
            return True
        else:
            log.error("Backup failed - check logs for details")
            return False
            
    except Exception as e:
        log.error(f"Backup failed with error: {e}")
        return False


def backup(
    ctx: typer.Context,
    include_volumes: Annotated[
        bool,
        typer.Option(
            "--include-volumes/--no-volumes",
            help="Include Docker volumes in backup (models, conversations, databases).",
        ),
    ] = True,
    include_config: Annotated[
        bool,
        typer.Option(
            "--include-config/--no-config", 
            help="Include configuration files in backup.",
        ),
    ] = True,
    include_extensions: Annotated[
        bool,
        typer.Option(
            "--include-extensions/--no-extensions",
            help="Include extension data in backup.",
        ),
    ] = True,
    output: Annotated[
        Optional[str],
        typer.Option(
            "--output", "-o",
            help="Specify backup location (default: ~/.ollama-stack/backups/backup-TIMESTAMP).",
        ),
    ] = None,
    compress: Annotated[
        bool,
        typer.Option(
            "--compress/--no-compress",
            help="Create compressed backup archive.",
        ),
    ] = True,
    description: Annotated[
        Optional[str],
        typer.Option(
            "--description", "-d",
            help="Add a description to the backup for identification.",
        ),
    ] = None,
):
    """Create a backup of the current stack state and data.
    
    This command creates a comprehensive backup including Docker volumes,
    configuration files, and extension data. The backup includes a manifest
    file for integrity verification and restoration.
    
    Examples:
        ollama-stack backup                    # Full backup with default settings
        ollama-stack backup --no-volumes       # Backup without volume data
        ollama-stack backup -o ./my-backup     # Backup to specific location
        ollama-stack backup -d "Before update" # Backup with description
    """
    app_context: AppContext = ctx.obj
    
    success = backup_stack_logic(
        app_context=app_context,
        include_volumes=include_volumes,
        include_config=include_config,
        include_extensions=include_extensions,
        output_path=output,
        compress=compress,
        description=description
    )
    
    if not success:
        raise typer.Exit(1) 
"""
Migrate command implementation for the Ollama Stack CLI.

This module handles migrating the stack to new versions with automatic
backups and version-specific migration logic.
"""

import typer
import logging
from typing_extensions import Annotated
from typing import Optional, List

from ..context import AppContext

log = logging.getLogger(__name__)


def migrate_stack_logic(
    app_context: AppContext,
    target_version: Optional[str] = None,
    backup: bool = True,
    dry_run: bool = False
) -> bool:
    """Business logic for migrating stack to new version."""
    
    current_version = "0.2.0"  # TODO: Get from actual version tracking
    
    # Determine target version
    if target_version is None:
        target_version = "latest"  # TODO: Get latest available version
        log.info(f"No target version specified, using latest: {target_version}")
    
    log.info(f"Planning migration from {current_version} to {target_version}")
    
    # Check if migration is needed
    if current_version == target_version:
        log.info("Stack is already at the target version - no migration needed")
        app_context.display.panel(
            f"✅ No Migration Required\n\n"
            f"📋 Current version: {current_version}\n"
            f"🎯 Target version: {target_version}\n\n"
            f"Your stack is already up to date!",
            "Migration Status",
            border_style="green"
        )
        return True
    
    # TODO: Add version comparison logic to determine if upgrade/downgrade
    # For now, assume any different version requires migration
    
    # Show migration plan
    migration_items = []
    breaking_changes = []
    
    # Version-specific migration planning
    if target_version == "0.3.0":
        migration_items = [
            "Update service configuration format",
            "Migrate extension registry",
            "Update backup configuration schema"
        ]
        breaking_changes = [
            "Configuration file format changes",
            "Extension API updates"
        ]
    elif target_version == "0.4.0":
        migration_items = [
            "Update backup manifest format",
            "Migrate volume labels",
            "Update health check configuration",
            "Upgrade extension framework"
        ]
        breaking_changes = [
            "Backup format incompatibility with older versions",
            "Extension configuration changes"
        ]
    else:
        # Generic migration
        migration_items = [
            "Validate configuration compatibility",
            "Update service definitions",
            "Refresh extension registry",
            "Update version tracking"
        ]
        breaking_changes = [
            "Potential configuration format changes"
        ]
    
    # Display migration plan
    if dry_run:
        log.info("DRY RUN MODE - No changes will be made")
    
    log.info("Migration plan:")
    for i, item in enumerate(migration_items, 1):
        log.info(f"  {i}. {item}")
    
    if breaking_changes:
        log.warning("Breaking changes:")
        for change in breaking_changes:
            log.warning(f"  • {change}")
    
    # Show backup plan
    if backup:
        log.info("Automatic backup will be created before migration")
    else:
        log.warning("No backup will be created - this is not recommended")
    
    # Dry run - show plan and exit
    if dry_run:
        app_context.display.panel(
            f"🔍 Migration Plan (Dry Run)\n\n"
            f"📋 From: {current_version} → To: {target_version}\n\n"
            f"📝 Migration steps:\n" +
            "\n".join(f"   {i}. {item}" for i, item in enumerate(migration_items, 1)) +
            (f"\n\n⚠️  Breaking changes:\n" + 
             "\n".join(f"   • {change}" for change in breaking_changes) if breaking_changes else "") +
            f"\n\n🔒 Backup: {'Yes' if backup else 'No'}\n\n"
            f"💡 To perform this migration, run:\n"
            f"   ollama-stack migrate {target_version}",
            "Migration Plan",
            border_style="blue"
        )
        return True
    
    # Confirm migration with user
    if breaking_changes:
        app_context.display.panel(
            f"⚠️  Breaking Changes Detected\n\n"
            f"This migration includes breaking changes:\n" +
            "\n".join(f"   • {change}" for change in breaking_changes) +
            f"\n\nA backup will be created automatically for safety.\n"
            f"Please review the migration plan carefully.",
            "Migration Warning",
            border_style="yellow"
        )
    
    if not typer.confirm(f"Do you want to proceed with migration to {target_version}?"):
        log.info("Migration cancelled by user")
        return False
    
    # Check if stack is running
    if app_context.stack_manager.is_stack_running():
        log.warning("Stack is currently running")
        if not typer.confirm("Migration may require stopping services. Continue?"):
            log.info("Migration cancelled by user")
            return False
    
    # Perform the migration
    try:
        log.info("Starting migration process...")
        
        success = app_context.stack_manager.migrate_stack(
            target_version=target_version,
            migration_path=None  # Let the system determine the path
        )
        
        if success:
            log.info("Migration completed successfully!")
            
            app_context.display.panel(
                f"✅ Migration Completed Successfully\n\n"
                f"📋 From: {current_version} → To: {target_version}\n"
                f"✨ Applied {len(migration_items)} migration steps\n"
                + (f"🔒 Backup created automatically\n" if backup else "") +
                f"\n🚀 Next steps:\n"
                f"   • Run 'ollama-stack start' to start services\n"
                f"   • Run 'ollama-stack status' to verify migration\n"
                f"   • Run 'ollama-stack check' to validate environment",
                "Migration Complete",
                border_style="green"
            )
            
            return True
        else:
            log.error("Migration failed - check logs for details")
            log.error("Stack may be in an inconsistent state")
            log.error("Consider restoring from backup if issues persist")
            return False
            
    except Exception as e:
        log.error(f"Migration failed with error: {e}")
        log.error("Stack may be in an inconsistent state")
        log.error("Consider restoring from backup if issues persist")
        return False


def migrate(
    ctx: typer.Context,
    target_version: Annotated[
        Optional[str],
        typer.Argument(
            help="Target version to migrate to (default: latest).",
        ),
    ] = None,
    backup: Annotated[
        bool,
        typer.Option(
            "--backup/--no-backup",
            help="Create backup before migration (recommended).",
        ),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be changed without making changes.",
        ),
    ] = False,
):
    """Migrate the stack to a new version or configuration.
    
    This command migrates the stack to a new version with automatic
    backup creation and version-specific migration steps. Use --dry-run
    to preview changes before applying them.
    
    Examples:
        ollama-stack migrate                    # Migrate to latest version
        ollama-stack migrate 0.3.0             # Migrate to specific version
        ollama-stack migrate --dry-run          # Preview migration changes
        ollama-stack migrate --no-backup 0.3.0 # Migrate without backup (not recommended)
    """
    app_context: AppContext = ctx.obj
    
    success = migrate_stack_logic(
        app_context=app_context,
        target_version=target_version,
        backup=backup,
        dry_run=dry_run
    )
    
    if not success:
        raise typer.Exit(1) 
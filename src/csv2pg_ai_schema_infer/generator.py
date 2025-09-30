"""Configuration and script generation module."""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .config import PerformanceConfig
from .types import GenerationResult, TableSchema
from .utils.logger import logger


def get_templates_dir() -> Path:
    """Get templates directory path."""
    return Path(__file__).parent / "templates"


def generate_pgloader_config(
    schema: TableSchema,
    csv_path: Path,
    output_dir: Path,
    database_url: str,
    performance_config: PerformanceConfig | None = None,
    dry_run: bool = False,
) -> Path:
    """
    Generate pgloader configuration file.

    Args:
        schema: Table schema
        csv_path: Path to CSV file
        output_dir: Output directory
        database_url: PostgreSQL connection URL
        performance_config: Performance configuration (auto-detected if None)
        dry_run: If True, don't write file

    Returns:
        Path to generated config file
    """
    # Load template
    templates_dir = get_templates_dir()
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("pgloader.jinja2")

    # Auto-detect performance config if not provided
    if performance_config is None:
        file_size_gb = csv_path.stat().st_size / (1024**3) if csv_path.exists() else None
        performance_config = PerformanceConfig.auto_detect(file_size_gb)
        logger.info(
            f"Auto-detected performance config: workers={performance_config.workers}, "
            f"concurrency={performance_config.concurrency}"
        )

    # Prepare template variables
    cast_columns = [col for col in schema.columns if col.needs_cast]

    # Get delimiter from CSV (default to comma)
    delimiter = ","

    context = {
        "csv_path": str(csv_path.absolute()),
        "database_url": database_url,
        "table_name": schema.table_name,
        "delimiter": delimiter,
        "columns": schema.columns,
        "cast_columns": cast_columns if cast_columns else None,
        "primary_key": schema.primary_key,
        # Performance settings
        "workers": performance_config.workers,
        "concurrency": performance_config.concurrency,
        "batch_size": performance_config.batch_size,
        "prefetch_rows": performance_config.prefetch_rows,
        "work_mem": performance_config.work_mem,
        "maintenance_work_mem": performance_config.maintenance_work_mem,
    }

    # Render template
    config_content = template.render(**context)

    # Write to file
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = output_dir / f"{schema.table_name}.load"

    if not dry_run:
        with open(config_path, "w") as f:
            f.write(config_content)
        logger.info(f"Generated pgloader config: {config_path}")
    else:
        logger.info(f"[DRY RUN] Would generate: {config_path}")

    return config_path


def generate_import_script(
    config_path: Path,
    state_file: Path,
    log_file: Path,
    csv_path: Path,
    table_name: str,
    output_dir: Path,
    dry_run: bool = False,
) -> Path:
    """
    Generate bash import script.

    Args:
        config_path: Path to pgloader config
        state_file: Path to state file
        log_file: Path to log file
        csv_path: Path to CSV file
        table_name: Table name
        output_dir: Output directory
        dry_run: If True, don't write file

    Returns:
        Path to generated script
    """
    # Load template
    templates_dir = get_templates_dir()
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("import.sh.jinja2")

    # Prepare template variables
    context = {
        "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "csv_path": str(csv_path.absolute()),
        "table_name": table_name,
        "config_file": str(config_path.absolute()),
        "state_file": str(state_file.absolute()),
        "log_file": str(log_file.absolute()),
    }

    # Render template
    script_content = template.render(**context)

    # Write to file
    script_path = output_dir / f"{table_name}_import.sh"

    if not dry_run:
        with open(script_path, "w") as f:
            f.write(script_content)

        # Make executable
        script_path.chmod(0o755)

        logger.info(f"Generated import script: {script_path}")
    else:
        logger.info(f"[DRY RUN] Would generate: {script_path}")

    return script_path


def generate_all(
    schema: TableSchema,
    csv_path: Path,
    output_dir: Path,
    database_url: str,
    performance_config: PerformanceConfig | None = None,
    dry_run: bool = False,
) -> GenerationResult:
    """
    Generate all files (config, script, state, log placeholders).

    Args:
        schema: Table schema
        csv_path: Path to CSV file
        output_dir: Output directory
        database_url: PostgreSQL connection URL
        performance_config: Performance configuration (auto-detected if None)
        dry_run: If True, don't write files

    Returns:
        Generation result with file paths
    """
    logger.info("Generating configuration and scripts...")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate pgloader config
    config_path = generate_pgloader_config(
        schema, csv_path, output_dir, database_url, performance_config, dry_run
    )

    # Define file paths
    state_file = output_dir / f"{schema.table_name}_state.json"
    log_file = output_dir / f"{schema.table_name}_import.log"

    # Generate import script
    script_path = generate_import_script(
        config_path,
        state_file,
        log_file,
        csv_path,
        schema.table_name,
        output_dir,
        dry_run,
    )

    result = GenerationResult(
        pgloader_config_path=config_path,
        import_script_path=script_path,
        state_file_path=state_file,
        log_file_path=log_file,
    )

    if dry_run:
        logger.info("[DRY RUN] Generation complete (no files written)")
    else:
        logger.info("Generation complete")

    return result

"""Command-line interface for CSV2PG AI Schema Infer."""

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import __version__
from .config import load_config
from .generator import generate_all
from .inference import infer_schema_heuristic, infer_schema_sync
from .llm.gemini import GeminiProvider
from .sampler import sample_csv
from .state_manager import StateManager
from .types import ImportPhase
from .utils.logger import logger, setup_logger

app = typer.Typer(
    name="csv2pg-ai-schema-infer",
    help="Intelligent CSV to PostgreSQL import pipeline with AI-powered type inference",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"csv2pg-ai-schema-infer version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """CSV2PG AI Schema Infer - Intelligent CSV to PostgreSQL import pipeline."""
    pass


@app.command()
def import_csv(
    csv_path: Path = typer.Argument(..., help="Path to CSV file", exists=True),
    sample_rows: int = typer.Option(
        100, "--sample-rows", "-n", help="Number of rows to sample"
    ),
    chunk_size: int = typer.Option(
        20, "--chunk-size", "-c", help="Columns per chunk for LLM processing"
    ),
    db_url: str | None = typer.Option(
        None, "--db-url", "-d", help="PostgreSQL connection URL"
    ),
    table_name: str | None = typer.Option(
        None, "--table-name", "-t", help="Target table name (default: CSV filename)"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Output directory (default: ./output)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Generate configs without importing"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing files"
    ),
    no_llm: bool = typer.Option(
        False, "--no-llm", help="Skip LLM inference, use heuristics only"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Enable verbose logging"
    ),
) -> None:
    """Import CSV file into PostgreSQL with AI-powered schema inference."""
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logger(level=log_level)

    # Load configuration
    config = load_config()

    # Override config with CLI args
    if sample_rows:
        config.sampling.rows = sample_rows
    if chunk_size:
        config.chunking.columns_per_chunk = chunk_size
    if output_dir:
        config.output.directory = output_dir
    if dry_run:
        config.output.dry_run = True

    # Get database URL
    if db_url is None:
        db_url = config.database_url
        if not db_url:
            console.print(
                "[red]Error:[/red] Database URL not provided. "
                "Use --db-url or set DATABASE_URL environment variable."
            )
            raise typer.Exit(code=1)

    # Get table name
    if table_name is None:
        table_name = csv_path.stem.lower().replace("-", "_").replace(" ", "_")

    console.print("\n[bold]CSV2PG AI Schema Infer[/bold]\n")
    console.print(f"CSV File: [cyan]{csv_path}[/cyan]")
    console.print(f"Table Name: [cyan]{table_name}[/cyan]")
    console.print(f"Output Dir: [cyan]{config.output.directory}[/cyan]")
    if dry_run:
        console.print("[yellow]Mode: DRY RUN[/yellow]")
    console.print()

    try:
        # Initialize state manager
        state_file = config.output.directory / f"{table_name}_state.json"
        state_manager = StateManager(state_file)

        # Create initial state
        state = state_manager.create_initial_state(csv_path, table_name)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Sample CSV
            task = progress.add_task("Sampling CSV file...", total=None)
            sample = sample_csv(
                csv_path,
                n_rows=config.sampling.rows,
                encoding=config.sampling.encoding,
            )
            state = state_manager.mark_phase_complete(state, ImportPhase.SAMPLED)
            progress.update(
                task,
                description=f"✓ Sampled {sample.sample_size} rows, "
                f"{len(sample.headers)} columns",
            )
            progress.stop_task(task)

            # Step 2: Infer schema
            progress.update(task, description="Inferring PostgreSQL types...")

            if no_llm or not config.gemini_api_key:
                if not no_llm:
                    console.print(
                        "[yellow]Warning:[/yellow] Gemini API key not found. "
                        "Using heuristic inference only."
                    )
                schema = infer_schema_heuristic(sample)
            else:
                provider = GeminiProvider(
                    api_key=config.gemini_api_key,
                    model=config.llm.model,
                    timeout=config.llm.timeout,
                    retry_attempts=config.llm.retry_attempts,
                    retry_delay=config.llm.retry_delay,
                )
                schema = infer_schema_sync(
                    sample,
                    provider,
                    chunk_size=config.chunking.columns_per_chunk,
                )

            state = state_manager.mark_phase_complete(state, ImportPhase.INFERRED)
            progress.update(
                task,
                description=f"✓ Inferred types for {len(schema.columns)} columns",
            )

            # Step 3: Generate files
            progress.update(task, description="Generating configuration files...")
            result = generate_all(
                schema,
                csv_path,
                config.output.directory,
                db_url,
                dry_run=dry_run,
            )
            state = state_manager.mark_phase_complete(state, ImportPhase.GENERATED)
            progress.update(task, description="✓ Generated configuration files")

        # Display schema
        console.print("\n[bold]Inferred Schema:[/bold]\n")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Column")
        table.add_column("Type")
        table.add_column("Nullable")
        table.add_column("Constraints")

        for col in schema.columns:
            table.add_row(
                col.name,
                col.pg_type,
                "✓" if col.nullable else "✗",
                ", ".join(col.constraints) if col.constraints else "-",
            )

        console.print(table)

        # Display generated files
        console.print("\n[bold]Generated Files:[/bold]\n")
        console.print(f"  • pgloader config: [cyan]{result.pgloader_config_path}[/cyan]")
        console.print(f"  • Import script:   [cyan]{result.import_script_path}[/cyan]")
        console.print(f"  • State file:      [cyan]{result.state_file_path}[/cyan]")
        console.print(f"  • Log file:        [cyan]{result.log_file_path}[/cyan]")

        if not dry_run:
            console.print("\n[bold]Next Steps:[/bold]\n")
            console.print("  1. Review the generated files")
            console.print("  2. Verify the database connection URL")
            console.print(
                f"  3. Run the import: [cyan]bash {result.import_script_path}[/cyan]\n"
            )
        else:
            console.print(
                "\n[yellow]Dry run complete. No files were written.[/yellow]\n"
            )

        console.print("[green]✓ Import preparation complete![/green]\n")

    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}\n")
        logger.exception("Import failed")
        raise typer.Exit(code=1)


@app.command()
def validate(
    csv_path: Path = typer.Argument(..., help="Path to CSV file", exists=True),
    show_sample: bool = typer.Option(
        False, "--show-sample", "-s", help="Display sample data"
    ),
    check_encoding: bool = typer.Option(
        False, "--check-encoding", "-e", help="Detect encoding issues"
    ),
) -> None:
    """Validate CSV file structure and properties."""
    console.print(f"\n[bold]Validating CSV:[/bold] [cyan]{csv_path}[/cyan]\n")

    try:
        sample = sample_csv(csv_path, n_rows=10)

        console.print(f"✓ File encoding: [cyan]{sample.properties.encoding}[/cyan]")
        console.print(f"✓ Delimiter: [cyan]'{sample.properties.delimiter}'[/cyan]")
        console.print(f"✓ Columns: [cyan]{sample.properties.column_count}[/cyan]")
        if sample.properties.row_count:
            console.print(f"✓ Total rows: [cyan]{sample.properties.row_count:,}[/cyan]")

        console.print("\n[bold]Headers:[/bold]\n")
        for i, header in enumerate(sample.headers[:20], 1):
            console.print(f"  {i}. {header}")
        if len(sample.headers) > 20:
            console.print(f"  ... and {len(sample.headers) - 20} more")

        if show_sample:
            console.print("\n[bold]Sample Data (first 5 rows):[/bold]\n")
            table = Table(show_header=True, header_style="bold magenta")
            for header in sample.headers[:10]:  # Show first 10 columns
                table.add_column(header, overflow="fold", max_width=20)

            for row in sample.rows[:5]:
                values = [str(row.get(h, ""))[:50] for h in sample.headers[:10]]
                table.add_row(*values)

            console.print(table)
            if len(sample.headers) > 10:
                console.print(f"\n(Showing 10 of {len(sample.headers)} columns)")

        console.print("\n[green]✓ CSV validation complete![/green]\n")

    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}\n")
        raise typer.Exit(code=1)


@app.command()
def resume(
    state_file: Path = typer.Argument(..., help="Path to state file", exists=True),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force restart from beginning"
    ),
) -> None:
    """Resume a failed or interrupted import."""
    console.print(f"\n[bold]Resuming import from:[/bold] [cyan]{state_file}[/cyan]\n")

    try:
        state_manager = StateManager(state_file)
        state = state_manager.load_state()

        console.print(f"CSV: [cyan]{state.csv_path}[/cyan]")
        console.print(f"Table: [cyan]{state.table_name}[/cyan]")
        console.print(f"Status: [cyan]{state.status.value}[/cyan]")
        console.print(f"Phase: [cyan]{state.phase.value}[/cyan]")

        if not state.csv_path.exists():
            console.print(f"\n[red]Error:[/red] CSV file not found: {state.csv_path}")
            raise typer.Exit(code=1)

        can_resume, reason = state_manager.can_resume(state, state.csv_path)

        if not can_resume and not force:
            console.print(f"\n[yellow]Cannot resume:[/yellow] {reason}")
            console.print("Use --force to restart from beginning.")
            raise typer.Exit(code=1)

        if force:
            console.print("\n[yellow]Force restart requested.[/yellow]")
            console.print("This feature is not yet implemented.")
            console.print(
                "Please use the [cyan]import[/cyan] command to start a new import.\n"
            )
        else:
            console.print(f"\n[green]Resume possible:[/green] {reason}")
            console.print("This feature is not yet fully implemented.")
            console.print(
                "Please re-run the import command to continue from the saved state.\n"
            )

    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}\n")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

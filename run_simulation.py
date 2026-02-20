#!/usr/bin/env python3
"""
R&D Department Multi-Agent Simulation
======================================
Simulates how a real R&D department processes a strategic initiative
through a hierarchy of AI agents with distinct personalities.

Usage:
    python run_simulation.py --prompt "Your strategic initiative here"
    python run_simulation.py --prompt "..." --verbose
    python run_simulation.py --prompt "..." --live
    python run_simulation.py --list-runs
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from simulation.engine import SimulationEngine
from simulation.reporter import ReportGenerator
from simulation.agents import DEFAULT_MODEL_MAP


def slugify(text: str, max_words: int = 6) -> str:
    """Convert a prompt into a short, filesystem-safe slug."""
    text = re.sub(r"[^\w\s-]", "", text.lower().strip())
    words = text.split()[:max_words]
    return "-".join(words)


def create_run_directory(runs_dir: str, prompt: str) -> str:
    """Create a uniquely-named run directory: runs/YYYY-MM-DD_HH-MM_<slug>/"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    slug = slugify(prompt)
    run_name = f"{timestamp}_{slug}"
    run_dir = os.path.join(runs_dir, run_name)

    # Handle rare collision (same minute + same prompt)
    if os.path.exists(run_dir):
        run_dir += f"_{int(time.time()) % 1000}"

    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def save_run_metadata(run_dir: str, prompt: str, model: str, start_time: datetime):
    """Save run metadata for later listing/review."""
    metadata = {
        "prompt": prompt,
        "model": model,
        "started_at": start_time.isoformat(),
        "run_dir": run_dir,
    }
    with open(os.path.join(run_dir, "run_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def list_runs(runs_dir: str):
    """List all previous simulation runs."""
    console = Console()

    if not os.path.exists(runs_dir):
        console.print("[dim]No runs found. Run your first simulation![/dim]")
        return

    runs = []
    for entry in sorted(os.listdir(runs_dir), reverse=True):
        run_dir = os.path.join(runs_dir, entry)
        metadata_file = os.path.join(run_dir, "run_metadata.json")
        if os.path.isdir(run_dir) and os.path.exists(metadata_file):
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            metadata["folder"] = entry
            runs.append(metadata)

    if not runs:
        console.print("[dim]No runs found. Run your first simulation![/dim]")
        return

    table = Table(title="Past Simulation Runs", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Date", style="cyan", width=18)
    table.add_column("Prompt", style="white", max_width=60)
    table.add_column("Duration", style="green", width=10)
    table.add_column("Status", style="yellow", width=10)
    table.add_column("Folder", style="dim", max_width=50)

    for i, run in enumerate(runs, 1):
        date = run.get("started_at", "?")[:19].replace("T", " ")
        prompt = run.get("prompt", "?")
        if len(prompt) > 57:
            prompt = prompt[:57] + "..."
        duration = run.get("duration_seconds", "?")
        if isinstance(duration, (int, float)):
            duration = f"{duration:.1f}s"
        status = run.get("status", "unknown")
        table.add_row(str(i), date, prompt, str(duration), status, run["folder"])

    console.print()
    console.print(table)
    console.print(f"\n[dim]Runs directory: {runs_dir}[/dim]")
    console.print("[dim]Each folder contains: reports/, logs/, memory/, reflections/[/dim]")


def main():
    # Load .env file
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="R&D Department Multi-Agent Simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_simulation.py --prompt "Investigate adding AI-powered search to our document management product"
  python run_simulation.py --prompt "Evaluate building a recommendation engine" --verbose
  python run_simulation.py --list-runs
        """,
    )
    parser.add_argument(
        "--prompt",
        type=str,
        required=False,
        default=None,
        help="The strategic initiative prompt to process through the R&D department",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show full agent responses in terminal output",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-flash",
        help="Gemini model to use (default: gemini-2.5-flash)",
    )
    parser.add_argument(
        "--list-runs",
        action="store_true",
        default=False,
        help="List all previous simulation runs",
    )
    parser.add_argument(
        "--tiered-models",
        action="store_true",
        default=False,
        help="Use different models per hierarchy level (Pro for VP, Flash for rest)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Launch real-time dashboard in your browser (auto-opens http://127.0.0.1:8420)",
    )

    args = parser.parse_args()
    console = Console()

    # Set up paths
    project_dir = Path(__file__).parent
    config_dir = str(project_dir / "config")
    runs_dir = str(project_dir / "runs")

    # Handle --list-runs
    if args.list_runs:
        list_runs(runs_dir)
        return

    # Prompt is required for running a simulation
    if not args.prompt:
        console.print("[bold red]Error:[/bold red] --prompt is required (or use --list-runs)")
        sys.exit(1)

    # Create unique run directory
    run_dir = create_run_directory(runs_dir, args.prompt)

    # Verify config exists
    if not os.path.exists(os.path.join(config_dir, "org_structure.yaml")):
        console.print("[bold red]Error:[/bold red] Config files not found in ./config/")
        console.print("Make sure org_structure.yaml and agent_profiles.yaml exist.")
        sys.exit(1)

    # Check for API key
    if not os.environ.get("GOOGLE_API_KEY"):
        console.print(
            Panel(
                "[bold red]GOOGLE_API_KEY not set![/bold red]\n\n"
                "Add your key to the .env file:\n"
                "  [bold]GOOGLE_API_KEY=your-key-here[/bold]\n\n"
                "Get a key at: https://aistudio.google.com/apikey",
                title="Missing API Key",
                border_style="red",
            )
        )
        sys.exit(1)

    # Build model configuration
    model_map = None
    if args.tiered_models:
        model_map = DEFAULT_MODEL_MAP.copy()
        # Override with --model as the default for non-VP levels if specified
        if args.model != "gemini-2.5-flash":
            for level in [2, 3, 4]:
                model_map[level] = args.model

    # Build model display string
    if model_map:
        model_display = "\n".join(
            f"    L{level}: {model}" for level, model in sorted(model_map.items())
        )
    else:
        model_display = f"    All: {args.model}"

    # Determine display mode
    mode_display = "Live Dashboard" if args.live else ("Verbose" if args.verbose else "Standard")

    console.print()
    console.print(
        Panel(
            "[bold]R&D Department Multi-Agent Simulation[/bold]\n\n"
            f"[bold]Prompt:[/bold] {args.prompt}\n"
            f"[bold]Models:[/bold]\n{model_display}\n"
            f"[bold]Mode:[/bold] {mode_display}\n"
            f"[bold]Run saved to:[/bold] {run_dir}",
            border_style="bright_cyan",
            padding=(1, 2),
        )
    )
    console.print()

    # Run simulation
    try:
        start_time = datetime.now()
        save_run_metadata(run_dir, args.prompt, args.model, start_time)

        engine = SimulationEngine(
            config_dir=config_dir,
            workspace_dir=run_dir,
            model_name=args.model,
            model_map=model_map,
            verbose=args.verbose and not args.live,  # suppress verbose in live mode
            live=args.live,
        )

        t0 = time.time()
        engine.run(prompt=args.prompt)
        elapsed = time.time() - t0

        # Generate comprehensive report
        reporter = ReportGenerator(run_dir)
        report_path = reporter.generate(
            prompt=args.prompt,
            agents=engine.agents,
            round_outputs=engine.round_outputs,
            message_board=engine.message_board,
        )

        # Push report to live dashboard if running
        if engine.dashboard_state:
            try:
                with open(report_path, "r", encoding="utf-8") as f:
                    engine.dashboard_state.set_report(f.read())
            except Exception:
                pass  # Non-critical — report is still on disk

        # Update metadata with completion info
        meta_path = os.path.join(run_dir, "run_metadata.json")
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        metadata["completed_at"] = datetime.now().isoformat()
        metadata["duration_seconds"] = round(elapsed, 1)
        metadata["status"] = "completed"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        console.print()
        console.print(
            Panel(
                f"[bold green]Simulation complete![/bold green]\n\n"
                f"[bold]Duration:[/bold] {elapsed:.1f}s\n"
                f"[bold]Run folder:[/bold] {run_dir}\n\n"
                f"  Final report:  reports/final_synthesis.md\n"
                f"  Full report:   reports/simulation_report.md\n"
                f"  Activity log:  logs/activity_log.jsonl\n"
                f"  Comms log:     logs/communication_log.jsonl\n"
                f"  Agent memory:  memory/*.jsonl\n"
                f"  Reflections:   reflections/*.md\n\n"
                f"[dim]View all runs: python run_simulation.py --list-runs[/dim]",
                title="Output Files",
                border_style="bright_green",
                padding=(1, 2),
            )
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Simulation interrupted by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

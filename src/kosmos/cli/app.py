# SPDX-License-Identifier: Apache-2.0
"""KOSMOS CLI entry point — initialises the backend stack and launches the REPL."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from kosmos._dotenv import load_repo_dotenv
from kosmos.cli.config import CLIConfig
from kosmos.cli.renderer import EventRenderer
from kosmos.cli.repl import REPLLoop
from kosmos.config.guard import verify_startup
from kosmos.observability import setup_tracing

logger = logging.getLogger(__name__)

# KOSMOS version string
__version__ = "0.1.0"

# Typer application
_app = typer.Typer(
    name="kosmos",
    help="KOSMOS — Korean Public API Conversational Platform",
    add_completion=False,
)

# Sub-application: `kosmos session …`
_session_app = typer.Typer(
    name="session",
    help="Session management utilities.",
    add_completion=False,
)
_app.add_typer(_session_app, name="session")

_stderr_console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kosmos {__version__}")
        raise typer.Exit()


@_app.callback(invoke_without_command=True)
def _cli_command(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Enable debug logging."),
    ] = False,
    resume: Annotated[
        str | None,
        typer.Option(
            "--resume",
            "-r",
            help="Resume a previous session by its session ID.",
            metavar="SESSION_ID",
        ),
    ] = None,
    list_sessions: Annotated[
        bool,
        typer.Option(
            "--list-sessions",
            "-l",
            help="List recent sessions and exit.",
        ),
    ] = False,
    ipc: Annotated[
        str | None,
        typer.Option(
            "--ipc",
            help=(
                "IPC transport mode.  Pass 'stdio' to bypass the interactive Rich TUI "
                "and run a JSONL-over-stdio bridge suitable for the Ink/Bun TUI frontend. "
                "See docs/ipc-protocol.md for the frame schema."
            ),
            metavar="MODE",
        ),
    ] = None,
) -> None:
    """Launch the KOSMOS interactive CLI."""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    # IPC stdio mode: bypass interactive REPL, run JSONL bridge on stdin/stdout.
    if ipc is not None:
        if ipc != "stdio":
            _stderr_console.print(
                f"[red]Unknown --ipc mode:[/red] {ipc!r}. Only 'stdio' is supported."
            )
            sys.exit(1)
        _run_ipc_stdio()
        return

    if list_sessions:
        _run_list_sessions()
        return

    _run_repl(resume_session_id=resume)


def _run_ipc_stdio() -> None:
    """Run the asyncio JSONL stdio loop (no interactive Rich TUI).

    This is the entry point when the Bun/Ink TUI spawns the backend via
    ``Bun.spawn(['uv', 'run', 'kosmos', '--ipc', 'stdio'])``.

    The loop reads ``IPCFrame`` JSON lines from stdin, dispatches them to the
    query engine, and writes response frames to stdout.  A ``session_event
    {event='exit'}`` frame is emitted on clean shutdown.
    """
    from kosmos.ipc.stdio import run as _ipc_run  # noqa: PLC0415

    try:
        asyncio.run(_ipc_run())
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in IPC stdio loop: %s", exc)
        _stderr_console.print(f"[red]IPC stdio error:[/red] {escape(str(exc))}")
        sys.exit(1)


def _run_list_sessions() -> None:
    """Print recent sessions to stdout and exit."""
    import asyncio  # noqa: PLC0415

    from kosmos.session.store import list_sessions  # noqa: PLC0415

    console = Console()

    async def _list() -> None:
        sessions = await list_sessions()
        if not sessions:
            console.print("[dim]저장된 세션이 없습니다.[/dim]")
            return
        console.print("[bold]최근 세션 목록:[/bold]")
        for meta in sessions[:30]:
            title = meta.title or "(제목 없음)"
            updated = meta.updated_at.strftime("%Y-%m-%d %H:%M")
            console.print(
                f"  [cyan]{meta.session_id}[/cyan]  "
                f"{escape(title)}  "
                f"[dim]{updated}  메시지 {meta.message_count}개[/dim]"
            )

    asyncio.run(_list())


def _run_repl(resume_session_id: str | None = None) -> None:
    """Initialise the full backend stack and run the REPL.

    Wiring order (all share the same MetricsCollector / ObservabilityEventLogger):

        MetricsCollector ──┐
        EventLogger ───────┼──> RecoveryExecutor ──> ToolExecutor ──> QueryEngine
                           └──> SessionContext ──────────────────────────────────┘

    The REPL later calls ``engine.set_permission_session`` so that the
    session_id tracks the real REPL session rather than a placeholder.

    All initialisation errors are caught and printed as user-friendly messages.

    Args:
        resume_session_id: Optional session UUID to resume on startup.
    """
    import uuid  # noqa: PLC0415

    from kosmos.context.builder import ContextBuilder  # noqa: PLC0415
    from kosmos.engine.engine import QueryEngine  # noqa: PLC0415
    from kosmos.llm.client import LLMClient  # noqa: PLC0415
    from kosmos.llm.errors import ConfigurationError  # noqa: PLC0415
    from kosmos.observability import MetricsCollector, ObservabilityEventLogger  # noqa: PLC0415
    from kosmos.permissions.models import SessionContext  # noqa: PLC0415
    from kosmos.recovery.executor import RecoveryExecutor  # noqa: PLC0415
    from kosmos.tools.executor import ToolExecutor  # noqa: PLC0415
    from kosmos.tools.register_all import register_all_tools  # noqa: PLC0415
    from kosmos.tools.registry import ToolRegistry  # noqa: PLC0415

    console = Console()

    # --- Load CLI config ---
    try:
        config = CLIConfig()
    except Exception as exc:  # noqa: BLE001
        _stderr_console.print(f"[red]CLI 설정 오류:[/red] {escape(str(exc))}")
        sys.exit(1)

    # --- Initialise observability (shared single instance) ---
    metrics = MetricsCollector()
    event_logger = ObservabilityEventLogger()

    # --- Initialise LLM client ---
    try:
        llm_client = LLMClient(metrics=metrics, event_logger=event_logger)
    except ConfigurationError as exc:
        _stderr_console.print(
            f"[red]설정 오류:[/red] {escape(str(exc))}\n\n"
            "[dim]KOSMOS_FRIENDLI_TOKEN 환경 변수가 설정되어 있는지 확인하세요.[/dim]"
        )
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        _stderr_console.print(f"[red]LLM 클라이언트 초기화 오류:[/red] {escape(str(exc))}")
        sys.exit(1)

    # --- Initialise recovery executor (shared; owns circuit breakers + cache) ---
    recovery_executor = RecoveryExecutor(
        metrics=metrics,
        event_logger=event_logger,
    )

    # --- Initialise tool registry and executor (tool executor wires recovery) ---
    registry = ToolRegistry()
    executor = ToolExecutor(
        registry,
        recovery_executor=recovery_executor,
        metrics=metrics,
        event_logger=event_logger,
    )
    register_all_tools(registry, executor)

    # --- Bootstrap a SessionContext; REPL updates it with the real session id ---
    initial_session = SessionContext(session_id=str(uuid.uuid4()))

    # --- Initialise context builder ---
    context_builder = ContextBuilder(registry=registry)

    # --- Initialise query engine with session context injected ---
    engine = QueryEngine(
        llm_client=llm_client,
        tool_registry=registry,
        tool_executor=executor,
        context_builder=context_builder,
        permission_session=initial_session,
    )

    # --- Launch REPL ---
    # Enable streaming markdown only when stdout is a real terminal so that
    # Rich's Live display is not activated in piped or redirected output.
    is_tty = sys.stdout.isatty()
    renderer = EventRenderer(
        console,
        registry=registry,
        show_usage=config.show_usage,
        streaming_markdown=is_tty,
    )
    repl = REPLLoop(
        engine=engine,
        registry=registry,
        console=console,
        config=config,
        renderer=renderer,
        resume_session_id=resume_session_id,
        metrics=metrics,
    )

    try:
        asyncio.run(repl.run())
    except KeyboardInterrupt:
        console.print("\n[dim]종료합니다.[/dim]")
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in REPL: %s", exc)
        _stderr_console.print(f"[red]예상치 못한 오류:[/red] {escape(str(exc))}")
        sys.exit(1)


@_session_app.command("gc-stubs")
def _gc_stubs_command(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help=(
                "When --dry-run (default) list eligible stubs but do not delete them. "
                "Pass --no-dry-run to actually remove files."
            ),
        ),
    ] = True,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of eligible stubs to process.  Default: unlimited.",
            metavar="N",
        ),
    ] = None,
    older_than: Annotated[
        int | None,
        typer.Option(
            "--older-than",
            help=(
                "Only consider stubs whose created_at is older than this many days. "
                "Default: no age filter."
            ),
            metavar="DAYS",
        ),
    ] = None,
    session_dir: Annotated[
        str | None,
        typer.Option(
            "--session-dir",
            help=(
                "Override the session directory path. "
                "Defaults to KOSMOS_MEMDIR_USER/sessions or ~/.kosmos/memdir/user/sessions."
            ),
            hidden=True,
        ),
    ] = None,
) -> None:
    """Garbage-collect metadata-only stub JSONL files from the session store.

    A stub is a session file that contains exactly one JSON line with
    entry_type='metadata' and message_count=0 — these were created by an older
    version of KOSMOS at IPC boot before lazy session creation was introduced.

    Run with --dry-run first (the default) to preview eligible files, then
    re-run with --no-dry-run to delete them.

    Example::

        kosmos session gc-stubs --dry-run
        kosmos session gc-stubs --no-dry-run --older-than 7
    """
    import asyncio as _asyncio  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    from kosmos.session.store import gc_empty_stubs  # noqa: PLC0415

    console = Console()
    dir_override = Path(session_dir).expanduser() if session_dir else None

    async def _run() -> None:
        result = await gc_empty_stubs(
            session_dir=dir_override,
            dry_run=dry_run,
            limit=limit,
            older_than_days=older_than,
        )

        mode_label = "[yellow]DRY-RUN[/yellow]" if dry_run else "[green]LIVE[/green]"
        console.print(f"\n[bold]Session GC ({mode_label})[/bold]")
        console.print(f"  Scanned   : {result.scanned}")
        console.print(f"  Eligible  : {result.eligible}")
        if dry_run:
            console.print(
                f"  Would delete : {result.eligible} "
                "(pass --no-dry-run to actually remove)"
            )
        else:
            console.print(f"  Deleted   : {result.deleted}")
        console.print(f"  Skipped (has content): {result.skipped_with_content}")
        console.print(f"  Errors    : {result.errors}")

        if result.errors > 0:
            raise typer.Exit(code=1)

    _asyncio.run(_run())


def main() -> None:
    """Public entry point called by ``[project.scripts]`` and ``__main__.py``."""
    load_repo_dotenv()
    verify_startup()  # fail-fast guard — exits 78 if required KOSMOS_* vars missing
    setup_tracing()  # configure global TracerProvider once before any query dispatch

    # Bootstrap HMAC key + registry once before any ledger operation (P1-2/P1-3).
    # Idempotent: no-op when files already exist with correct permissions.
    # Fail-closed: HMACKeyFileModeError propagates and aborts startup.
    from kosmos.permissions.hmac_key import bootstrap_hmac_key  # noqa: PLC0415
    from kosmos.settings import settings as _kosmos_settings  # noqa: PLC0415

    bootstrap_hmac_key(
        key_path=_kosmos_settings.permission_key_path,
        key_registry_path=_kosmos_settings.permission_key_registry_path,
    )

    _app()

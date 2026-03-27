"""Shared utilities for pipeline stages."""

import logging
import subprocess

logger = logging.getLogger(__name__)


def run_command(args: list[str]) -> bytes:
    """Run a command and return its stdout. Raise RuntimeError on failure.

    This wrapper handles logging and standardizes error reporting.
    """
    cmd_str = " ".join(args)
    logger.info("Running command: %s", cmd_str)

    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
    )

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"Command failed (exit {result.returncode}): {cmd_str}\nStderr: {stderr}")

    return result.stdout

"""Terminal execution tool."""
import shlex
import subprocess
from pathlib import Path
from app.config import Config
from app.logger import logger
from app.tools.base import BaseTool
class TerminalTool(BaseTool):
    name = "terminal"
    description = "Run shell commands in the workspace."
    def __init__(self, root_dir=None):
        super().__init__()
        workspace_root = root_dir if root_dir else Config.WORKSPACE
        self.root_dir = Path(workspace_root).expanduser().resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
    def execute(self, *args, **kwargs):
        command = kwargs.pop("command", None)
        cwd = kwargs.pop("cwd", ".")
        timeout = kwargs.pop("timeout", 30)
        if command is None and args:
            command = args[0]
        if command is None:
            raise ValueError("Command is required.")
        cwd = self._resolve_path(cwd)
        if isinstance(command, str):
            command = shlex.split(command)
        try:
            result = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            return {
                "command": command,
                "cwd": str(cwd),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            logger.error("Terminal command timed out.")
            return {
                "error": "Command timed out."
            }
        except Exception:
            logger.exception("Terminal execution failed.")
            raise
    def _resolve_path(self, path):
        candidate = (self.root_dir / path).expanduser().resolve()
        try:
            candidate.relative_to(self.root_dir)
        except ValueError:
            raise ValueError("Path escapes workspace.")
        return candidate

"""Terminal execution tool."""
import re
import shlex
import subprocess
from pathlib import Path
from app.config import Config
from app.logger import logger
from app.tools.base import BaseTool

PROHIBITED_COMMAND_PATTERNS = [
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\s+(?:/|~|\*)(?:\s|$)"), # rm -rf /, rm -rf ~, rm -rf *
    re.compile(r"\b(mkfs|fdisk)\b|\bdd\s+if="),                       # disk wiping
    re.compile(r"\b(sudo|su)\b"),                                     # privilege escalation
    re.compile(r"\b(shutdown|reboot|poweroff)\b"),                   # system shutdown
    re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:"),                         # fork bomb
]

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
        if command is None or not str(command).strip():
            raise ValueError("Command is required.")

        cmd_str = command if isinstance(command, str) else " ".join(str(c) for c in command)
        if "\x00" in cmd_str:
            raise ValueError("Command contains invalid null byte.")

        for pat in PROHIBITED_COMMAND_PATTERNS:
            if pat.search(cmd_str):
                raise ValueError("Command rejected by security policy: destructive or disallowed system command.")

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
        if path is None or not str(path).strip():
            return self.root_dir
        if "\x00" in str(path):
            raise ValueError("Path contains invalid null byte.")
        try:
            candidate = (self.root_dir / path).expanduser().resolve()
            candidate.relative_to(self.root_dir)
        except ValueError:
            raise ValueError("Path escapes workspace.")
        return candidate


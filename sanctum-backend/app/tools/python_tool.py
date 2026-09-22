"""Python execution tool."""
import subprocess
import sys
from pathlib import Path
from app.config import Config
from app.logger import logger
from app.tools.base import BaseTool
class PythonTool(BaseTool):
    name = "python"
    description = "Run Python scripts."
    def __init__(self, root_dir=None):
        super().__init__()
        workspace_root = root_dir if root_dir else Config.WORKSPACE
        self.root_dir = Path(workspace_root).expanduser().resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.python_executable = sys.executable
    def execute(self, *args, **kwargs):
        code = kwargs.pop("code", None)
        script_path = kwargs.pop("script_path", None)
        cwd = kwargs.pop("cwd", ".")
        timeout = kwargs.pop("timeout", 30)
        cwd = self._resolve_path(cwd)
        if code is None and script_path is None:
            raise ValueError("Provide code or script_path.")
        if script_path:
            target = self._resolve_path(script_path)
            from app.sovereign_vault import is_file_locked, read_sovereign_text
            if is_file_locked(target):
                decrypted_code, _ = read_sovereign_text(target)
                command = [
                    self.python_executable,
                    "-c",
                    decrypted_code
                ]
            else:
                command = [
                    self.python_executable,
                    str(target)
                ]
        else:
            command = [
                self.python_executable,
                "-c",
                code
            ]
        try:
            result = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "command": command,
                "cwd": str(cwd),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            logger.error("Python execution timed out.")
            return {
                "error": "Execution timed out."
            }
        except Exception:
            logger.exception("Python execution failed.")
            raise
    def _resolve_path(self, path):
        if path is None or not str(path).strip():
            return self.root_dir
        if "\x00" in str(path):
            raise ValueError("Path contains invalid null byte.")
        candidate = (self.root_dir / path).expanduser().resolve()
        try:
            candidate.relative_to(self.root_dir)
        except ValueError:
            raise ValueError("Path escapes workspace.")
        return candidate

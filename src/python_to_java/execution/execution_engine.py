from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from ..models import ExecutionResult


class ExecutionEngine:
    PYTHON_PRELUDE = "\n".join(
        [
            "def sort(values):",
            "    values.sort()",
            "",
        ]
    )

    def __init__(self, timeout_seconds: int = 5) -> None:
        self.timeout_seconds = timeout_seconds

    def run_python(self, code: str) -> ExecutionResult:
        wrapped = f"{self.PYTHON_PRELUDE}\n{code}"
        return self._run_command(["python", "-c", wrapped])

    def run_java(self, code: str, class_name: str = "GeneratedProgram") -> ExecutionResult:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            java_file = temp_path / f"{class_name}.java"
            java_file.write_text(code, encoding="utf-8")

            compile_result = self._run_command(["javac", java_file.name], cwd=temp_path)
            if not compile_result.success:
                return compile_result

            return self._run_command(["java", class_name], cwd=temp_path)

    def _run_command(self, command: list[str], cwd: Path | None = None) -> ExecutionResult:
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(
                success=False,
                stdout=exc.stdout or "",
                stderr=f"Timed out after {self.timeout_seconds} seconds.",
                command=command,
            )

        return ExecutionResult(
            success=completed.returncode == 0,
            stdout=completed.stdout,
            stderr=completed.stderr,
            command=command,
        )

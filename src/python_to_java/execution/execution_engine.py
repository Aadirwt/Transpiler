from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

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
        self.temp_root = Path.cwd() / ".runtime"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.python_cmd = sys.executable
        self.java_cmd, self.javac_cmd = self._resolve_java_tools()

    def run_python(self, code: str) -> ExecutionResult:
        wrapped = f"{self.PYTHON_PRELUDE}\n{code}"
        return self._run_command([self.python_cmd, "-c", wrapped])

    def run_java(self, code: str, class_name: str = "GeneratedProgram") -> ExecutionResult:
        if not self.java_cmd or not self.javac_cmd:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Java toolchain not found. Install Java and ensure java/javac are available.",
                command=[],
            )

        temp_path = self.temp_root / f"java-run-{uuid4().hex}"
        temp_path.mkdir(parents=True, exist_ok=False)
        try:
            java_file = temp_path / f"{class_name}.java"
            java_file.write_text(code, encoding="utf-8")

            compile_result = self._run_command([self.javac_cmd, java_file.name], cwd=temp_path)
            if not compile_result.success:
                return compile_result

            return self._run_command([self.java_cmd, class_name], cwd=temp_path)
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

    def _resolve_java_tools(self) -> tuple[str | None, str | None]:
        java_cmd = shutil.which("java")
        javac_cmd = shutil.which("javac")
        if java_cmd and javac_cmd:
            return java_cmd, javac_cmd

        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            java_bin = Path(java_home) / "bin"
            java_candidate = java_bin / "java.exe"
            javac_candidate = java_bin / "javac.exe"
            if java_candidate.exists() and javac_candidate.exists():
                return str(java_candidate), str(javac_candidate)

        microsoft_root = Path("C:/Program Files/Microsoft")
        for install_dir in sorted(microsoft_root.glob("jdk-*"), reverse=True):
            java_candidate = install_dir / "bin" / "java.exe"
            javac_candidate = install_dir / "bin" / "javac.exe"
            if java_candidate.exists() and javac_candidate.exists():
                return str(java_candidate), str(javac_candidate)

        return None, None

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

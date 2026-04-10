from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.transpiler.core.ast_nodes import Program
from src.transpiler.core.tac import TACProgram


@dataclass
class ImportSpec:
    module: str
    names: list[str] = field(default_factory=list)


@dataclass
class PreprocessedInput:
    code: str
    imports: list[ImportSpec]


@dataclass
class ParsedPythonModule:
    source: str
    imports: list[ImportSpec]
    ast: Program


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str = ""
    command: list[str] = field(default_factory=list)


@dataclass
class TranslationResult:
    java_code: str
    tac: TACProgram
    python_output: str = ""
    java_output: str = ""
    semantic_match: Optional[bool] = None
    retries: int = 0
    logs_path: Optional[Path] = None
    correction_history: list[str] = field(default_factory=list)

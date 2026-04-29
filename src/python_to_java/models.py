from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.transpiler.core.tac import TACProgram


@dataclass
class ImportSpec:
    module: str
    names: list[str] = field(default_factory=list)


@dataclass
class PreprocessedInput:
    code: str
    imports: list[ImportSpec]
    warnings: list[str] = field(default_factory=list)

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
    diagnostics: list[str] = field(default_factory=list)
    symbol_table: str = ""
    typed_ast: str = ""

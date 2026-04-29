from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..models import TranslationResult


class Reporter:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.cwd()
        self.logs_dir = self.root / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def log(self, input_code: str, result: TranslationResult, status: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.logs_dir / f"translation-{timestamp}.json"
        payload = {
            "status": status,
            "input_code": input_code,
            "java_code": result.java_code,
            "python_output": result.python_output,
            "java_output": result.java_output,
            "semantic_match": result.semantic_match,
            "retries": result.retries,
            "corrections": result.correction_history,
            "diagnostics": result.diagnostics,
            "symbol_table": result.symbol_table,
            "typed_ast": result.typed_ast,
            "tac": result.tac.to_text(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

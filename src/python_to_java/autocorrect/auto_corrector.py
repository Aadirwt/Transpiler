from __future__ import annotations

from ..mapper import FunctionMapper


class AutoCorrector:
    def __init__(self) -> None:
        self.function_mapper = FunctionMapper()

    def fix(self, java_code: str, error: str) -> str:
        updated = self.function_mapper.missing_import_fix(java_code, error)
        if updated != java_code:
            return updated

        if "Scanner" in error and "import java.util.Scanner;" not in java_code:
            lines = java_code.splitlines()
            insert_at = 0
            while insert_at < len(lines) and lines[insert_at].startswith("import "):
                insert_at += 1
            lines.insert(insert_at, "import java.util.Scanner;")
            return "\n".join(lines)

        return java_code

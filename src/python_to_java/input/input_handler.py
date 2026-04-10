from __future__ import annotations

import re
from pathlib import Path

from ..models import ImportSpec, PreprocessedInput


class InputHandler:
    def read(self, path: str | Path) -> str:
        return Path(path).read_text(encoding="utf-8-sig")

    def preprocess(self, code: str) -> PreprocessedInput:
        normalized = code.replace("\r\n", "\n").replace("\r", "\n").strip()
        imports: list[ImportSpec] = []
        kept_lines: list[str] = []

        for raw_line in normalized.splitlines():
            line = raw_line.strip()
            import_match = re.fullmatch(r"import\s+([A-Za-z_][A-Za-z0-9_]*)", line)
            from_match = re.fullmatch(
                r"from\s+([A-Za-z_][A-Za-z0-9_]*)\s+import\s+([A-Za-z0-9_,\s]+)",
                line,
            )

            if import_match:
                imports.append(ImportSpec(module=import_match.group(1)))
                continue

            if from_match:
                names = [name.strip() for name in from_match.group(2).split(",") if name.strip()]
                imports.append(ImportSpec(module=from_match.group(1), names=names))
                continue

            kept_lines.append(raw_line)

        return PreprocessedInput(code="\n".join(kept_lines).strip(), imports=imports)

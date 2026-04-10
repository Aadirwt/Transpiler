from __future__ import annotations

from ..models import ImportSpec


class LibraryMapper:
    JAVA_IMPORTS = {
        "math": [],
        "random": ["import java.util.Random;"],
    }

    def map_imports(self, imports: list[ImportSpec]) -> list[str]:
        java_imports: set[str] = set()
        for item in imports:
            for mapped in self.JAVA_IMPORTS.get(item.module, []):
                java_imports.add(mapped)
        return sorted(java_imports)

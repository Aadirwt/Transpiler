from __future__ import annotations

from ..models import ImportSpec


class LibraryMapper:
    JAVA_IMPORTS = {
        "math": [],
        "random": ["import java.util.Random;"],
        "typing": [],
        "collections": ["import java.util.*;"],
    }

    SUPPORTED_MODULES = set(JAVA_IMPORTS)

    def map_imports(self, imports: list[ImportSpec]) -> list[str]:
        java_imports: set[str] = set()
        for item in imports:
            for mapped in self.JAVA_IMPORTS.get(item.module, []):
                java_imports.add(mapped)
        return sorted(java_imports)

    def warnings_for(self, imports: list[ImportSpec]) -> list[str]:
        warnings = []
        for item in imports:
            if item.module not in self.SUPPORTED_MODULES:
                warnings.append(
                    f"Import '{item.module}' has no Java mapping and is ignored."
                )
        return warnings

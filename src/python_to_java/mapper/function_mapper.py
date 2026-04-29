from __future__ import annotations


class FunctionMapper:
    BUILTIN_RETURNS = {
        "len": "int",
        "sum": "int",
        "min": "int",
        "max": "int",
        "input": "String",
    }

    def method_mapping(self, method_name: str) -> str | None:
        return {
            "append": "add",
            "sort": "sort",
        }.get(method_name)

    def builtin_return_type(self, name: str) -> str | None:
        return self.BUILTIN_RETURNS.get(name)

    def missing_import_fix(self, java_code: str, error_text: str) -> str:
        required_imports: list[str] = []
        if "Collections" in error_text:
            required_imports.append("import java.util.Collections;")
        if "Arrays" in error_text:
            required_imports.append("import java.util.Arrays;")
        if "ArrayList" in error_text:
            required_imports.append("import java.util.ArrayList;")

        if not required_imports:
            return java_code

        lines = java_code.splitlines()
        existing = {line.strip() for line in lines if line.strip().startswith("import ")}
        insert_at = 0
        while insert_at < len(lines) and lines[insert_at].startswith("import "):
            insert_at += 1

        additions = [item for item in required_imports if item not in existing]
        if not additions:
            return java_code

        updated = lines[:insert_at] + sorted(additions) + lines[insert_at:]
        return "\n".join(updated)

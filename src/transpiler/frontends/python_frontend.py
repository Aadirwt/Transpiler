from __future__ import annotations

import re

from ..core.ast_nodes import Program
from ..core.common_parser import CommonParser
from ..core.errors import FrontendError


class PythonFrontend:
    def __init__(self) -> None:
        self.parser = CommonParser()

    def parse(self, source: str) -> Program:
        normalized = self._normalize(source)
        return self.parser.parse(normalized)

    def _normalize(self, source: str) -> str:
        lines = source.splitlines()
        out: list[str] = []
        indent_stack = [0]
        expect_indent = False

        for line_no, raw in enumerate(lines, start=1):
            expanded = raw.replace("\t", "    ")
            code = expanded.split("#", 1)[0].rstrip()
            if not code.strip():
                continue

            indent = len(code) - len(code.lstrip(" "))
            stripped = code.strip()

            if expect_indent:
                if indent <= indent_stack[-1]:
                    raise FrontendError(
                        f"Expected indented block after line {line_no - 1}."
                    )
                out.append("{")
                indent_stack.append(indent)
                expect_indent = False
            else:
                while indent < indent_stack[-1]:
                    out.append("}")
                    indent_stack.pop()
                if indent > indent_stack[-1]:
                    raise FrontendError(f"Unexpected indentation at line {line_no}.")

            converted, opens_block = self._convert_line(stripped, line_no)
            out.append(converted)
            if opens_block:
                expect_indent = True

        if expect_indent:
            raise FrontendError("Source ended before expected indented block.")

        while len(indent_stack) > 1:
            out.append("}")
            indent_stack.pop()

        return "\n".join(out)

    def _convert_line(self, stripped: str, line_no: int) -> tuple[str, bool]:
        if stripped.startswith("class "):
            match = re.match(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*:$", stripped)
            if not match:
                raise FrontendError(f"Invalid class definition at line {line_no}.")
            return f"class {match.group(1)}", True

        if stripped.startswith("def "):
            match = re.match(r"def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)\s*:$", stripped)
            if not match:
                raise FrontendError(f"Invalid function definition at line {line_no}.")
            name = match.group(1)
            params = match.group(2).strip()
            return f"function {name}({params})", True

        if stripped.startswith("if ") and stripped.endswith(":"):
            condition = self._normalize_expr(stripped[3:-1].strip())
            return f"if ({condition})", True

        if stripped.startswith("elif ") and stripped.endswith(":"):
            condition = self._normalize_expr(stripped[5:-1].strip())
            return f"else if ({condition})", True

        if stripped == "else:":
            return "else", True

        if stripped.startswith("while ") and stripped.endswith(":"):
            condition = self._normalize_expr(stripped[6:-1].strip())
            return f"while ({condition})", True

        if stripped.startswith("for ") and stripped.endswith(":"):
            return self._convert_for_line(stripped, line_no), True

        if stripped == "break":
            return "break;", False

        if stripped == "continue":
            return "continue;", False

        if stripped.startswith("return"):
            expr = stripped[6:].strip()
            if not expr:
                return "return;", False
            return f"return {self._normalize_expr(expr)};", False

        if stripped.startswith("print(") and stripped.endswith(")"):
            inner = stripped[6:-1].strip()
            return self._convert_print_line(inner, line_no), False

        if stripped.startswith("print "):
            inner = stripped[6:].strip()
            return self._convert_print_line(inner, line_no, bare=True), False

        if stripped.endswith(":"):
            raise FrontendError(f"Unsupported block statement at line {line_no}.")

        parts = [part.strip() for part in self._split_args(stripped)]
        if len(parts) > 1 and all(self._is_simple_assignment_segment(part) for part in parts):
            converted_parts: list[str] = []
            for part in parts:
                converted, opens_block = self._convert_line(part, line_no)
                if opens_block:
                    raise FrontendError(f"Unsupported comma-separated block statement at line {line_no}.")
                converted_parts.append(converted)
            return "\n".join(converted_parts), False

        assign_match = re.match(
            r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*=\s*(.+)$",
            stripped,
        )
        if assign_match:
            left = assign_match.group(1)
            right = self._normalize_expr(assign_match.group(2).strip())
            return f"{left} = {right};", False

        expr = self._normalize_expr(stripped)
        if not expr.endswith(";"):
            expr += ";"
        return expr, False

    def _convert_for_line(self, stripped: str, line_no: int) -> str:
        match = re.match(
            r"for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+range\s*\((.*)\)\s*:$", stripped
        )
        if not match:
            raise FrontendError(
                f"Unsupported for-loop at line {line_no}. Only range(...) is supported."
            )

        var = match.group(1)
        args = [self._normalize_expr(part.strip()) for part in self._split_args(match.group(2))]

        if len(args) == 1:
            start, end, step = "0", args[0], "1"
        elif len(args) == 2:
            start, end, step = args[0], args[1], "1"
        elif len(args) == 3:
            start, end, step = args[0], args[1], args[2]
        else:
            raise FrontendError(
                f"range() at line {line_no} supports 1 to 3 arguments only."
            )

        cmp = ">" if self._looks_negative(step) else "<"
        init = f"{var} = {start}"
        condition = f"{var} {cmp} ({end})"
        increment = f"{var} = {var} + ({step})"
        return f"for ({init}; {condition}; {increment})"

    def _normalize_expr(self, expr: str) -> str:
        expr = re.sub(
            r"\b([A-Za-z_][A-Za-z0-9_]*)\.append\s*\((.*)\)$",
            r"append(\1, \2)",
            expr,
        )
        expr = re.sub(
            r"\b([A-Za-z_][A-Za-z0-9_]*)\.sort\s*\(\s*\)$",
            r"sort(\1)",
            expr,
        )
        expr = re.sub(r"\bTrue\b", "true", expr)
        expr = re.sub(r"\bFalse\b", "false", expr)
        expr = re.sub(r"\band\b", "&&", expr)
        expr = re.sub(r"\bor\b", "||", expr)
        expr = re.sub(r"\bnot\b", "!", expr)
        return expr

    def _convert_print_line(self, inner: str, line_no: int, bare: bool = False) -> str:
        if bare:
            return f"print({self._normalize_expr(inner)});"

        parts = [part.strip() for part in self._split_args(inner)]
        newline = True

        if parts:
            end_match = re.match(r"^end\s*=\s*(.+)$", parts[-1])
            if end_match:
                end_value = end_match.group(1).strip()
                if end_value not in {'""', "''"}:
                    raise FrontendError(
                        f"Only print(..., end=\"\") is supported at line {line_no}."
                    )
                newline = False
                parts = parts[:-1]

        normalized_parts = [self._normalize_expr(part) for part in parts if part]
        callee = "print" if newline else "print_inline"
        return f"{callee}({', '.join(normalized_parts)});"

    def _split_args(self, arg_text: str) -> list[str]:
        if not arg_text.strip():
            return []
        parts: list[str] = []
        depth = 0
        current: list[str] = []
        for ch in arg_text:
            if ch == "," and depth == 0:
                parts.append("".join(current))
                current = []
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            current.append(ch)
        if current:
            parts.append("".join(current))
        return parts

    def _is_simple_assignment_segment(self, text: str) -> bool:
        return re.match(
            r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\s*=\s*.+$",
            text,
        ) is not None

    def _looks_negative(self, value: str) -> bool:
        stripped = value.strip()
        return stripped.startswith("-")

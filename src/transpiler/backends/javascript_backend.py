from __future__ import annotations

import re

from ..core.tac import TACClass, TACFunction, TACInstruction, TACProgram


class JavaScriptBackend:
    def generate(self, program: TACProgram) -> str:
        self.class_names = {cls.name for cls in program.classes}
        lines: list[str] = []

        for cls in program.classes:
            lines.extend(self._emit_class(cls))
            lines.append("")

        for fn in program.functions:
            lines.extend(self._emit_function(fn))
            lines.append("")

        lines.extend(self._emit_main(program.main))
        lines.append("")
        return "\n".join(lines)

    def _emit_class(self, cls: TACClass) -> list[str]:
        lines = [f"class {cls.name} {{"]
        ctor = self._find_constructor(cls)
        methods = [method for method in cls.methods if method.name != "__init__"]

        if ctor is not None:
            params = ", ".join(self._user_params(ctor))
            ctor_inits = self._declaration_initializers(ctor)
            lines.append(f"    constructor({params}) {{")
            lines.extend(self._emit_decls(ctor, 2))
            lines.extend(
                self._emit_body(
                    ctor.instructions,
                    2,
                    in_constructor=True,
                    skip_indexes={index for _, index in ctor_inits.values()},
                )
            )
            lines.append("    }")

        if not methods and ctor is None:
            lines.append("}")
            return lines

        for method in methods:
            is_instance = self._is_instance_method(method)
            params = self._user_params(method) if is_instance else method.params
            method_inits = self._declaration_initializers(method)
            static_kw = "" if is_instance else "static "
            lines.append(f"    {static_kw}{method.name}({', '.join(params)}) {{")
            lines.extend(self._emit_decls(method, 2))
            lines.extend(
                self._emit_body(
                    method.instructions,
                    2,
                    skip_indexes={index for _, index in method_inits.values()},
                )
            )
            lines.append("    }")
        lines.append("}")
        return lines

    def _emit_function(self, fn: TACFunction) -> list[str]:
        params = ", ".join(fn.params)
        decl_inits = self._declaration_initializers(fn)
        lines = [f"function {fn.name}({params}) {{"]
        lines.extend(self._emit_decls(fn, 1))
        lines.extend(
            self._emit_body(
                fn.instructions,
                1,
                skip_indexes={index for _, index in decl_inits.values()},
            )
        )
        lines.append("}")
        return lines

    def _emit_main(self, main: TACFunction) -> list[str]:
        decl_inits = self._declaration_initializers(main)
        lines: list[str] = []
        lines.extend(self._emit_decls(main, 0))
        lines.extend(
            self._emit_body(
                main.instructions,
                0,
                skip_indexes={index for _, index in decl_inits.values()},
            )
        )
        return lines

    def _emit_decls(self, fn: TACFunction, indent: int) -> list[str]:
        params = set(fn.params)
        decl_inits = self._declaration_initializers(fn)
        plain_decls: list[str] = []
        lines: list[str] = []

        for name in self._ordered_locals(fn, params):
            if name in decl_inits:
                lines.append(self._pad(indent) + f"let {name} = {self._expr(decl_inits[name][0])};")
            else:
                plain_decls.append(name)

        if plain_decls:
            lines.append(self._pad(indent) + f"let {', '.join(plain_decls)};")

        return lines

    def _emit_body(
        self,
        instructions: list[TACInstruction],
        base_indent: int,
        in_constructor: bool = False,
        skip_indexes: set[int] | None = None,
    ) -> list[str]:
        lines: list[str] = []
        indent = base_indent
        skip_indexes = skip_indexes or set()

        for index, inst in enumerate(instructions):
            if index in skip_indexes:
                continue
            if inst.kind == "if_begin":
                lines.append(self._pad(indent) + f"if ({self._expr(inst.condition)}) {{")
                indent += 1
            elif inst.kind == "else_begin":
                indent -= 1
                lines.append(self._pad(indent) + "} else {")
                indent += 1
            elif inst.kind == "if_end":
                indent -= 1
                lines.append(self._pad(indent) + "}")
            elif inst.kind == "while_begin":
                lines.append(self._pad(indent) + f"while ({self._expr(inst.condition)}) {{")
                indent += 1
            elif inst.kind == "while_end":
                indent -= 1
                lines.append(self._pad(indent) + "}")
            elif inst.kind == "assign":
                lines.append(self._pad(indent) + f"{inst.target} = {self._expr(inst.value)};")
            elif inst.kind == "member_assign":
                lines.append(
                    self._pad(indent)
                    + f"{self._expr(inst.object_ref)}.{inst.member} = {self._expr(inst.value)};"
                )
            elif inst.kind == "binop":
                lines.append(
                    self._pad(indent)
                    + f"{inst.target} = {self._binary_expr(inst.op or '', inst.left, inst.right)};"
                )
            elif inst.kind == "unop":
                lines.append(
                    self._pad(indent) + f"{inst.target} = {inst.op}{self._expr(inst.value)};"
                )
            elif inst.kind == "call":
                args = ", ".join(self._expr(arg) for arg in inst.args)
                callee = self._expr(inst.name)
                if inst.target:
                    if callee in self.class_names:
                        lines.append(self._pad(indent) + f"{inst.target} = new {callee}({args});")
                    else:
                        lines.append(self._pad(indent) + f"{inst.target} = {callee}({args});")
                else:
                    lines.append(self._pad(indent) + f"{callee}({args});")
            elif inst.kind == "print":
                lines.append(self._pad(indent) + self._print_line(inst.args))
            elif inst.kind == "print_inline":
                lines.append(self._pad(indent) + self._print_inline(inst.args))
            elif inst.kind == "return":
                if inst.value is None:
                    lines.append(self._pad(indent) + "return;")
                else:
                    if in_constructor:
                        lines.append(self._pad(indent) + "return;")
                    else:
                        lines.append(self._pad(indent) + f"return {self._expr(inst.value)};")
            elif inst.kind == "break":
                lines.append(self._pad(indent) + "break;")
            elif inst.kind == "continue":
                lines.append(self._pad(indent) + "continue;")
            elif inst.kind == "nop":
                lines.append(self._pad(indent) + ";")

        return lines

    def _expr(self, text: str | None) -> str:
        if text is None:
            return ""
        return re.sub(r"\bself\b", "this", text)

    def _binary_expr(self, op: str, left: str | None, right: str | None) -> str:
        left_expr = self._expr(left)
        right_expr = self._expr(right)

        if op == "*":
            if self._is_string_literal(left):
                return f"{left_expr}.repeat({right_expr})"
            if self._is_string_literal(right):
                return f"{right_expr}.repeat({left_expr})"

        return f"{left_expr} {op} {right_expr}"

    def _print_line(self, args: list[str]) -> str:
        if not args:
            return "console.log();"
        rendered = ", ".join(self._expr(arg) for arg in args)
        return f"console.log({rendered});"

    def _print_inline(self, args: list[str]) -> str:
        if not args:
            return 'process.stdout.write("");'
        if len(args) == 1:
            return f"process.stdout.write(String({self._expr(args[0])}));"
        joined = ", ".join(self._expr(arg) for arg in args)
        return f'process.stdout.write([{joined}].map(v => String(v)).join(" "));'

    def _pad(self, indent: int) -> str:
        return " " * (4 * indent)

    def _is_string_literal(self, text: str | None) -> bool:
        if not text:
            return False
        stripped = text.strip()
        return (
            (stripped.startswith('"') and stripped.endswith('"'))
            or (stripped.startswith("'") and stripped.endswith("'"))
        )

    def _find_constructor(self, cls: TACClass) -> TACFunction | None:
        for method in cls.methods:
            if method.name == "__init__":
                return method
        return None

    def _is_instance_method(self, method: TACFunction) -> bool:
        return bool(method.params) and method.params[0] == "self"

    def _user_params(self, method: TACFunction) -> list[str]:
        if self._is_instance_method(method):
            return method.params[1:]
        return method.params

    def _ordered_locals(self, fn: TACFunction, params: set[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()

        for inst in fn.instructions:
            if inst.kind in {"assign", "binop", "unop", "call"} and inst.target:
                if inst.target in fn.locals and inst.target not in params and inst.target not in seen:
                    ordered.append(inst.target)
                    seen.add(inst.target)

        for name in sorted(var for var in fn.locals if var not in params and var not in seen):
            ordered.append(name)

        return ordered

    def _declaration_initializers(self, fn: TACFunction) -> dict[str, tuple[str, int]]:
        params = set(fn.params)
        candidates = fn.locals - params
        if not candidates:
            return {}

        resolved: dict[str, tuple[str, int] | None] = {}
        depth = 0

        for index, inst in enumerate(fn.instructions):
            for name in self._instruction_reads(inst):
                if name in candidates and name not in resolved:
                    resolved[name] = None

            target = inst.target if inst.kind in {"assign", "binop", "unop", "call"} else None
            if target in candidates and target not in resolved:
                if depth == 0 and inst.kind == "assign" and self._is_literal_value(inst.value):
                    resolved[target] = (inst.value or "", index)
                else:
                    resolved[target] = None

            if inst.kind in {"if_begin", "while_begin"}:
                depth += 1
            elif inst.kind in {"else_begin", "if_end", "while_end"}:
                depth = max(0, depth - 1)
                if inst.kind == "else_begin":
                    depth += 1

        return {name: data for name, data in resolved.items() if data is not None}

    def _instruction_reads(self, inst: TACInstruction) -> set[str]:
        reads: set[str] = set()
        for text in (inst.value, inst.left, inst.right, inst.condition, inst.name, inst.object_ref):
            reads.update(self._names_in_text(text))
        for arg in inst.args:
            reads.update(self._names_in_text(arg))
        return reads

    def _names_in_text(self, text: str | None) -> set[str]:
        if not text:
            return set()
        return {
            name
            for name in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
            if name not in {"true", "false", "this", "self"}
        }

    def _is_literal_value(self, text: str | None) -> bool:
        if text is None:
            return False
        stripped = text.strip()
        if stripped in {"true", "false"}:
            return True
        if re.fullmatch(r"-?\d+", stripped):
            return True
        if re.fullmatch(r"-?\d+\.\d+", stripped):
            return True
        return (
            (stripped.startswith('"') and stripped.endswith('"'))
            or (stripped.startswith("'") and stripped.endswith("'"))
        )

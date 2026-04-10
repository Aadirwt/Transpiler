from __future__ import annotations

import re

from ..core.tac import TACClass, TACFunction, TACInstruction, TACProgram


class CppBackend:
    def generate(self, program: TACProgram) -> str:
        self.class_names = {cls.name for cls in program.classes}
        self.class_field_types: dict[str, dict[str, str]] = {}
        self.function_types: dict[str, dict[str, str]] = {}
        self.method_types: dict[str, dict[str, str]] = {}
        self.function_return_types: dict[str, str] = {}
        self.method_return_types: dict[str, str] = {}
        self.uses_string_repeat = False
        self.uses_std_string = False

        for cls in program.classes:
            field_types = self._infer_class_field_types(cls)
            self.class_field_types[cls.name] = field_types
            if "string" in field_types.values():
                self.uses_std_string = True
            for method in cls.methods:
                types = self._infer_types(method, self._seed_method_types(field_types))
                self.method_types[f"{cls.name}.{method.name}"] = types
                if "string" in types.values():
                    self.uses_std_string = True
                if self._instructions_use_string_repeat(method.instructions, types):
                    self.uses_string_repeat = True
                    self.uses_std_string = True
                if method.name != "__init__":
                    return_type = self._infer_return_type(method, types)
                    self.method_return_types[f"{cls.name}.{method.name}"] = return_type
                    if return_type == "std::string":
                        self.uses_std_string = True

        for fn in program.functions:
            types = self._infer_types(fn)
            self.function_types[fn.name] = types
            if "string" in types.values():
                self.uses_std_string = True
            if self._instructions_use_string_repeat(fn.instructions, types):
                self.uses_string_repeat = True
                self.uses_std_string = True
            return_type = self._infer_return_type(fn, types)
            self.function_return_types[fn.name] = return_type
            if return_type == "std::string":
                self.uses_std_string = True

        main_types = self._infer_types(program.main)
        if "string" in main_types.values():
            self.uses_std_string = True
        if self._instructions_use_string_repeat(program.main.instructions, main_types):
            self.uses_string_repeat = True
            self.uses_std_string = True

        lines = ["#include <iostream>"]
        if self.uses_std_string:
            lines.append("#include <string>")
        lines.append("")
        if self.uses_string_repeat:
            lines.extend(
                [
                    "static std::string repeat_string(const std::string& text, int count) {",
                    "    std::string out = \"\";",
                    "    for (int i = 0; i < count; ++i) {",
                    "        out += text;",
                    "    }",
                    "    return out;",
                    "}",
                    "",
                ]
            )

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
        ctor = self._find_constructor(cls)
        regular_methods = [method for method in cls.methods if method.name != "__init__"]
        field_types = dict(self.class_field_types.get(cls.name, {}))
        seed_types = self._seed_method_types(field_types)
        method_types = {
            method.name: self.method_types.get(
                f"{cls.name}.{method.name}", self._infer_types(method, seed_types)
            )
            for method in cls.methods
        }

        lines = [f"class {cls.name} {{", "public:"]

        for field, typ in sorted(field_types.items()):
            ctype = self._cpp_type(typ)
            init = self._default_value(typ)
            lines.append(self._pad(1) + f"{ctype} {field} = {init};")

        if ctor is not None:
            ctor_params = self._user_params(ctor)
            if ctor_params:
                lines.append(self._pad(1) + f"{cls.name}() = default;")
            ctor_types = method_types[ctor.name]
            ctor_inits = self._declaration_initializers(ctor)
            param_text = ", ".join(self._param_decl(param, ctor_types) for param in ctor_params)
            lines.append(self._pad(1) + f"{cls.name}({param_text}) {{")
            lines.extend(self._emit_decls(ctor, 2, ctor_types))
            lines.extend(
                self._emit_body(
                    ctor.instructions,
                    2,
                    ctor_types,
                    in_constructor=True,
                    skip_indexes={index for _, index in ctor_inits.values()},
                )
            )
            lines.append(self._pad(1) + "}")

        for method in regular_methods:
            is_instance = self._is_instance_method(method)
            params = self._user_params(method) if is_instance else method.params
            types = method_types.get(method.name, {})
            method_inits = self._declaration_initializers(method)
            param_text = ", ".join(self._param_decl(param, types) for param in params)
            static_kw = "" if is_instance else "static "
            return_type = self._infer_return_type(method, types)
            lines.append(
                self._pad(1) + f"{static_kw}{return_type} {method.name}({param_text}) {{"
            )
            lines.extend(self._emit_decls(method, 2, types))
            lines.extend(
                self._emit_body(
                    method.instructions,
                    2,
                    types,
                    skip_indexes={index for _, index in method_inits.values()},
                )
            )
            if not self._has_return(method.instructions):
                lines.append(self._pad(2) + "return 0;")
            lines.append(self._pad(1) + "}")

        if len(lines) == 2:
            lines.append(self._pad(1) + f"{cls.name}() = default;")

        lines.append("};")
        return lines

    def _emit_function(self, fn: TACFunction) -> list[str]:
        types = self.function_types.get(fn.name, self._infer_types(fn))
        decl_inits = self._declaration_initializers(fn)
        params = ", ".join(self._param_decl(param, types) for param in fn.params)
        return_type = self._infer_return_type(fn, types)
        lines = [f"{return_type} {fn.name}({params}) {{"]
        lines.extend(self._emit_decls(fn, 1, types))
        lines.extend(
            self._emit_body(
                fn.instructions,
                1,
                types,
                skip_indexes={index for _, index in decl_inits.values()},
            )
        )
        if not self._has_return(fn.instructions):
            lines.append(self._pad(1) + "return 0;")
        lines.append("}")
        return lines

    def _emit_main(self, main: TACFunction) -> list[str]:
        types = self._infer_types(main)
        decl_inits = self._declaration_initializers(main)
        lines = ["int main() {"]
        lines.extend(self._emit_decls(main, 1, types))
        lines.extend(
            self._emit_body(
                main.instructions,
                1,
                types,
                skip_indexes={index for _, index in decl_inits.values()},
            )
        )
        if not self._has_return(main.instructions):
            lines.append(self._pad(1) + "return 0;")
        lines.append("}")
        return lines

    def _emit_decls(self, fn: TACFunction, indent: int, types: dict[str, str]) -> list[str]:
        params = set(fn.params)
        omit_init = self._omit_initializer_vars(fn)
        decl_inits = self._declaration_initializers(fn)
        lines: list[str] = []
        for name in self._ordered_locals(fn, params):
            typ = types.get(name, "int")
            ctype = self._cpp_type(typ)
            if name in decl_inits:
                lines.append(
                    self._pad(indent)
                    + f"{ctype} {name} = {self._expr(decl_inits[name][0])};"
                )
            elif name in omit_init:
                lines.append(self._pad(indent) + f"{ctype} {name};")
            else:
                init = self._default_value(typ)
                lines.append(self._pad(indent) + f"{ctype} {name} = {init};")
        return lines

    def _emit_body(
        self,
        instructions: list[TACInstruction],
        base_indent: int,
        types: dict[str, str],
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
                obj = self._expr(inst.object_ref)
                lhs = f"this->{inst.member}" if obj in {"self", "this"} else f"{obj}.{inst.member}"
                lines.append(self._pad(indent) + f"{lhs} = {self._expr(inst.value)};")
            elif inst.kind == "binop":
                lines.append(
                    self._pad(indent)
                    + f"{inst.target} = {self._binary_expr(inst.op or '', inst.left, inst.right, types)};"
                )
            elif inst.kind == "unop":
                lines.append(
                    self._pad(indent) + f"{inst.target} = {inst.op}{self._expr(inst.value)};"
                )
            elif inst.kind == "call":
                args = ", ".join(self._expr(arg) for arg in inst.args)
                callee = self._call_name(inst.name or "")
                line = f"{callee}({args});"
                if inst.target:
                    line = f"{inst.target} = {callee}({args});"
                lines.append(self._pad(indent) + line)
            elif inst.kind == "print":
                lines.append(self._pad(indent) + self._print_line(inst.args))
            elif inst.kind == "print_inline":
                lines.append(self._pad(indent) + self._print_inline(inst.args))
            elif inst.kind == "return":
                if inst.value is None:
                    lines.append(self._pad(indent) + ("return;" if in_constructor else "return 0;"))
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

    def _infer_class_field_types(self, cls: TACClass) -> dict[str, str]:
        field_types: dict[str, str] = {}

        for _ in range(max(1, len(cls.methods) + 1)):
            changed = False
            seed_types = self._seed_method_types(field_types)
            for method in cls.methods:
                types = self._infer_types(method, seed_types)
                for inst in method.instructions:
                    if inst.kind == "member_assign" and inst.object_ref in {"self", "this"}:
                        field_type = self._infer_expr_type(inst.value, types)
                        if self._merge_type(field_types, inst.member or "", field_type):
                            changed = True
            if not changed:
                break

        return field_types

    def _infer_types(
        self, fn: TACFunction, seed_types: dict[str, str] | None = None
    ) -> dict[str, str]:
        types = dict(seed_types or {})

        for inst in fn.instructions:
            if inst.kind == "assign" and inst.target:
                typ = self._infer_expr_type(inst.value, types)
                self._merge_type(types, inst.target, typ)
            elif inst.kind == "member_assign" and inst.member:
                typ = self._infer_expr_type(inst.value, types)
                if inst.object_ref in {"self", "this"}:
                    self._merge_type(types, f"self.{inst.member}", typ)
                    self._merge_type(types, f"this->{inst.member}", typ)
                else:
                    self._merge_type(types, f"{inst.object_ref}.{inst.member}", typ)
            elif inst.kind == "binop" and inst.target:
                left_type = self._infer_expr_type(inst.left, types)
                right_type = self._infer_expr_type(inst.right, types)
                op = inst.op or ""
                if op == "+":
                    self._promote_operand_types(
                        inst.left, inst.right, left_type, right_type, types, "string"
                    )
                elif op in {"-", "*", "/"}:
                    self._promote_operand_types(
                        inst.left, inst.right, left_type, right_type, types, "double"
                    )
                if op in {"==", "!=", "<", "<=", ">", ">=", "&&", "||"}:
                    typ = "bool"
                elif op == "*" and ("string" in {left_type, right_type}):
                    typ = "string"
                elif op == "+" and ("string" in {left_type, right_type}):
                    typ = "string"
                elif "double" in {left_type, right_type}:
                    typ = "double"
                else:
                    typ = "int"
                self._merge_type(types, inst.target, typ)
            elif inst.kind == "unop" and inst.target:
                value_type = self._infer_expr_type(inst.value, types)
                typ = "bool" if inst.op == "!" else value_type
                self._merge_type(types, inst.target, typ)
            elif inst.kind == "call" and inst.target:
                call_name = (inst.name or "").strip()
                if call_name in self.class_names:
                    self._merge_type(types, inst.target, call_name)
                elif call_name in self.function_return_types:
                    self._merge_type(
                        types,
                        inst.target,
                        self._cpp_to_internal(self.function_return_types[call_name]),
                    )
                elif call_name in self.method_return_types:
                    self._merge_type(
                        types,
                        inst.target,
                        self._cpp_to_internal(self.method_return_types[call_name]),
                    )
                elif "." in call_name:
                    obj, method = call_name.split(".", 1)
                    cls_name = types.get(obj)
                    if cls_name and f"{cls_name}.{method}" in self.method_return_types:
                        self._merge_type(
                            types,
                            inst.target,
                            self._cpp_to_internal(
                                self.method_return_types[f"{cls_name}.{method}"]
                            ),
                        )
                else:
                    self._merge_type(types, inst.target, "int")

        return types

    def _infer_return_type(self, fn: TACFunction, types: dict[str, str] | None = None) -> str:
        known = types or self._infer_types(fn)
        seen: set[str] = set()
        for inst in fn.instructions:
            if inst.kind == "return" and inst.value is not None:
                seen.add(self._infer_expr_type(inst.value, known))

        if not seen:
            return "int"
        if "string" in seen:
            return "std::string"
        if "double" in seen:
            return "double"
        if "bool" in seen:
            return "bool"
        return "int"

    def _infer_expr_type(self, text: str | None, known: dict[str, str]) -> str:
        if text is None:
            return "int"
        stripped = text.strip()
        if stripped in known:
            return known[stripped]
        member_match = re.fullmatch(r"(self\.|this->)([A-Za-z_]\w*)", stripped)
        if member_match:
            field = member_match.group(2)
            if f"self.{field}" in known:
                return known[f"self.{field}"]
        if stripped in {"true", "false"}:
            return "bool"
        if re.fullmatch(r"-?\d+", stripped):
            return "int"
        if re.fullmatch(r"-?\d+\.\d+", stripped):
            return "double"
        if (
            (stripped.startswith('"') and stripped.endswith('"'))
            or (stripped.startswith("'") and stripped.endswith("'"))
        ):
            return "string"
        return "int"

    def _merge_type(self, types: dict[str, str], name: str, new_type: str) -> bool:
        old = types.get(name)
        if old is None:
            types[name] = new_type
            return True
        if old == new_type:
            return False
        if {old, new_type} <= {"int", "double"}:
            types[name] = "double"
            return old != "double"
        if old == "int" and new_type in {"string", "bool"}:
            types[name] = new_type
            return True
        return False

    def _seed_method_types(self, field_types: dict[str, str]) -> dict[str, str]:
        seeded: dict[str, str] = {}
        for field, typ in field_types.items():
            seeded[f"self.{field}"] = typ
            seeded[f"this->{field}"] = typ
        return seeded

    def _call_name(self, name: str) -> str:
        if re.fullmatch(r"[A-Z]\w*\.\w+", name):
            cls_name, method = name.split(".", 1)
            return f"{cls_name}::{method}"
        return self._expr(name)

    def _binary_expr(
        self,
        op: str,
        left: str | None,
        right: str | None,
        types: dict[str, str],
    ) -> str:
        left_expr = self._expr(left)
        right_expr = self._expr(right)
        left_type = self._infer_expr_type(left, types)
        right_type = self._infer_expr_type(right, types)

        if op == "*" and left_type == "string":
            return f"repeat_string({left_expr}, {right_expr})"
        if op == "*" and right_type == "string":
            return f"repeat_string({right_expr}, {left_expr})"

        return f"{left_expr} {op} {right_expr}"

    def _print_line(self, args: list[str]) -> str:
        if not args:
            return "std::cout << std::endl;"
        parts = ["std::cout"]
        for index, arg in enumerate(args):
            if index > 0:
                parts.append('<< " "')
            parts.append(f"<< {self._expr(arg)}")
        parts.append("<< std::endl;")
        return " ".join(parts)

    def _print_inline(self, args: list[str]) -> str:
        if not args:
            return 'std::cout << "";'
        parts = ["std::cout"]
        for index, arg in enumerate(args):
            if index > 0:
                parts.append('<< " "')
            parts.append(f"<< {self._expr(arg)}")
        parts.append(";")
        return " ".join(parts)

    def _expr(self, text: str | None) -> str:
        if text is None:
            return ""
        out = re.sub(r"\btrue\b", "true", text)
        out = re.sub(r"\bfalse\b", "false", out)
        out = re.sub(r"\bself\.", "this->", out)
        out = re.sub(r"\bself\b", "this", out)
        return out

    def _has_return(self, instructions: list[TACInstruction]) -> bool:
        return any(inst.kind == "return" for inst in instructions)

    def _pad(self, indent: int) -> str:
        return " " * (4 * indent)

    def _cpp_type(self, typ: str) -> str:
        if typ == "string":
            return "std::string"
        return typ

    def _default_value(self, typ: str) -> str:
        return {
            "int": "0",
            "double": "0.0",
            "bool": "false",
            "string": '""',
        }.get(typ, "{}")

    def _param_decl(self, name: str, types: dict[str, str]) -> str:
        typ = types.get(name, "int")
        if typ == "string":
            return f"const std::string& {name}"
        return f"{self._cpp_type(typ)} {name}"

    def _promote_operand_types(
        self,
        left: str | None,
        right: str | None,
        left_type: str,
        right_type: str,
        types: dict[str, str],
        preferred: str,
    ) -> None:
        for text, current, other in (
            (left, left_type, right_type),
            (right, right_type, left_type),
        ):
            if text and re.fullmatch(r"[A-Za-z_]\w*", text):
                if text not in types:
                    if preferred == "string" and ("string" in {current, other}):
                        types[text] = "string"
                    elif preferred == "double" and ("double" in {current, other}):
                        types[text] = "double"

    def _cpp_to_internal(self, cpp_type: str) -> str:
        if cpp_type == "std::string":
            return "string"
        return cpp_type

    def _instructions_use_string_repeat(
        self, instructions: list[TACInstruction], types: dict[str, str]
    ) -> bool:
        for inst in instructions:
            if inst.kind != "binop" or inst.op != "*":
                continue
            left_type = self._infer_expr_type(inst.left, types)
            right_type = self._infer_expr_type(inst.right, types)
            if "string" in {left_type, right_type}:
                return True
        return False

    def _omit_initializer_vars(self, fn: TACFunction) -> set[str]:
        candidates = fn.locals - set(fn.params)
        if not candidates:
            return set()

        resolved: dict[str, bool] = {}
        depth = 0

        for inst in fn.instructions:
            for name in self._instruction_reads(inst):
                if name in candidates and name not in resolved:
                    resolved[name] = False

            target = self._instruction_target(inst)
            if target in candidates and target not in resolved:
                resolved[target] = depth == 0

            if inst.kind in {"if_begin", "while_begin"}:
                depth += 1
            elif inst.kind in {"else_begin", "if_end", "while_end"}:
                depth = max(0, depth - 1)
                if inst.kind == "else_begin":
                    depth += 1

        return {name for name, ok in resolved.items() if ok}

    def _ordered_locals(self, fn: TACFunction, params: set[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()

        for inst in fn.instructions:
            target = self._instruction_target(inst)
            if target and target in fn.locals and target not in params and target not in seen:
                ordered.append(target)
                seen.add(target)

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

            target = self._instruction_target(inst)
            if target in candidates and target not in resolved:
                if (
                    depth == 0
                    and inst.kind == "assign"
                    and self._is_literal_value(inst.value)
                ):
                    resolved[target] = (inst.value or "", index)
                else:
                    resolved[target] = None

            if inst.kind in {"if_begin", "while_begin"}:
                depth += 1
            elif inst.kind in {"else_begin", "if_end", "while_end"}:
                depth = max(0, depth - 1)
                if inst.kind == "else_begin":
                    depth += 1

        return {
            name: data
            for name, data in resolved.items()
            if data is not None
        }

    def _instruction_reads(self, inst: TACInstruction) -> set[str]:
        reads: set[str] = set()
        for text in (inst.value, inst.left, inst.right, inst.condition, inst.name, inst.object_ref):
            reads.update(self._names_in_text(text))
        for arg in inst.args:
            reads.update(self._names_in_text(arg))
        return reads

    def _instruction_target(self, inst: TACInstruction) -> str | None:
        if inst.kind in {"assign", "binop", "unop", "call"}:
            return inst.target
        return None

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

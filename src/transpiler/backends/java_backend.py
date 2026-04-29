from __future__ import annotations

import re
from typing import Optional

from src.python_to_java.mapper import LibraryMapper
from src.python_to_java.models import ImportSpec

from ..core.tac import TACClass, TACFunction, TACInstruction, TACProgram
from .base_backend import BaseBackend


class JavaBackend(BaseBackend):
    def __init__(
        self,
        library_mapper: LibraryMapper | None = None,
    ) -> None:
        self.library_mapper = library_mapper or LibraryMapper()
        self.source_imports: list[ImportSpec] = []
        self.imports: set[str] = set()
        self.helpers: set[str] = set()
        self.wrapper_name = "GeneratedProgram"

    def set_source_imports(self, imports: list[ImportSpec]) -> None:
        self.source_imports = imports

    def generate(self, program: TACProgram) -> str:
        self.imports = set(self.library_mapper.map_imports(self.source_imports))
        self.helpers = set()
        self._prepare_program(program)
        main_types = self._infer_types(program.main)

        lines = [f"public class {self.wrapper_name} {{"]

        for cls in program.classes:
            lines.extend(self._emit_class(cls))
            lines.append("")

        for fn in program.functions:
            lines.extend(self._emit_function(fn))
            lines.append("")

        lines.extend(self._emit_main(program.main, main_types))

        if self.helpers:
            lines.append("")
            for helper in sorted(self.helpers):
                lines.extend(self._helper_lines(helper))
                lines.append("")

        if lines[-1] == "":
            lines.pop()
        lines.append("}")

        import_lines = [item for item in sorted(self.imports)]
        if import_lines:
            return "\n".join(import_lines + [""] + lines)
        return "\n".join(lines)

    def _emit_class(self, cls: TACClass) -> list[str]:
        field_types = self.class_field_types.get(cls.name, {})
        lines = [f"    static class {cls.name} {{"]

        for field, typ in sorted(field_types.items()):
            lines.append(
                f"        {self._java_type(typ)} {field} = {self._default_value(typ)};"
            )

        ctor = self._find_constructor(cls)
        if ctor is not None:
            ctor_types = self.method_types.get(f"{cls.name}.{ctor.name}", {})
            ctor_params = self._user_params(ctor)
            lines.append(
                f"        {cls.name}({', '.join(self._param_decl(name, ctor_types) for name in ctor_params)}) {{"
            )
            lines.extend(self._emit_decls(ctor, 3, ctor_types, omit_self=True))
            lines.extend(self._emit_body(ctor.instructions, 3, ctor_types, in_constructor=True))
            lines.append("        }")

        for method in cls.methods:
            if method.name == "__init__":
                continue
            types = self.method_types.get(f"{cls.name}.{method.name}", {})
            params = self._user_params(method) if self._is_instance_method(method) else method.params
            return_type_obj = self._infer_return_type(method, types)
            return_type = self._java_type(return_type_obj)
            static_kw = "" if self._is_instance_method(method) else "static "
            lines.append(
                f"        {static_kw}{return_type} {method.name}({', '.join(self._param_decl(name, types) for name in params)}) {{"
            )
            lines.extend(self._emit_decls(method, 3, types, omit_self=True))
            lines.extend(self._emit_body(method.instructions, 3, types, return_type=return_type))
            if return_type != "void" and not self._has_return(method.instructions):
                lines.append(self._default_return_line(return_type, 3))
            lines.append("        }")

        lines.append("    }")
        return lines

    def _emit_function(self, fn: TACFunction) -> list[str]:
        types = self.function_types.get(fn.name, self._infer_types(fn))
        return_type_obj = self._infer_return_type(fn, types)
        return_type = self._java_type(return_type_obj)
        lines = [
            f"    static {return_type} {fn.name}({', '.join(self._param_decl(name, types) for name in fn.params)}) {{"
        ]
        lines.extend(self._emit_decls(fn, 2, types))
        lines.extend(self._emit_body(fn.instructions, 2, types, return_type=return_type))
        if return_type != "void" and not self._has_return(fn.instructions):
            lines.append(self._default_return_line(return_type, 2))
        lines.append("    }")
        return lines

    def _emit_main(self, main: TACFunction, types: dict[str, str]) -> list[str]:
        lines = ["    public static void main(String[] args) {"] 
        lines.extend(self._emit_decls(main, 2, types))
        lines.extend(self._emit_body(main.instructions, 2, types, return_type="void"))
        lines.append("    }")
        return lines

    def _emit_decls(
        self,
        fn: TACFunction,
        indent: int,
        types: dict[str, str],
        omit_self: bool = False,
    ) -> list[str]:
        params = set(fn.params)
        if omit_self:
            params.add("self")
        lines: list[str] = []
        for name in self._ordered_locals(fn, params):
            typ = types.get(name, "int")
            java_type = self._java_type(typ)
            if java_type == "void":
                continue
            lines.append(f"{self._pad(indent)}{java_type} {name} = {self._default_value(typ)};")
        return lines

    def _emit_body(
        self,
        instructions: list[TACInstruction],
        base_indent: int,
        types: dict[str, object],
        in_constructor: bool = False,
        return_type: str = "int",
    ) -> list[str]:
        lines: list[str] = []
        indent = base_indent

        for inst in instructions:
            if inst.kind == "if_begin":
                lines.append(f"{self._pad(indent)}if ({self._expr(inst.condition)}) {{")
                indent += 1
            elif inst.kind == "else_begin":
                indent -= 1
                lines.append(f"{self._pad(indent)}}} else {{")
                indent += 1
            elif inst.kind == "if_end":
                indent -= 1
                lines.append(f"{self._pad(indent)}}}")
            elif inst.kind == "while_begin":
                lines.append(f"{self._pad(indent)}while ({self._expr(inst.condition)}) {{")
                indent += 1
            elif inst.kind == "while_end":
                indent -= 1
                lines.append(f"{self._pad(indent)}}}")
            elif inst.kind == "assign":
                lines.append(f"{self._pad(indent)}{inst.target} = {self._expr(inst.value)};")
            elif inst.kind == "member_assign":
                target = "this" if inst.object_ref in {"self", "this"} else self._expr(inst.object_ref)
                lines.append(
                    f"{self._pad(indent)}{target}.{inst.member} = {self._expr(inst.value)};"
                )
            elif inst.kind == "binop":
                lines.append(
                    f"{self._pad(indent)}{inst.target} = {self._binary_expr(inst.op or '', inst.left, inst.right, types)};"
                )
            elif inst.kind == "unop":
                lines.append(
                    f"{self._pad(indent)}{inst.target} = {inst.op}{self._expr(inst.value)};"
                )
            elif inst.kind == "call":
                call_line = self._call_line(inst, types)
                if call_line:
                    lines.append(f"{self._pad(indent)}{call_line}")
            elif inst.kind == "print":
                lines.append(f"{self._pad(indent)}System.out.println({self._print_expr(inst.args)});")
            elif inst.kind == "print_inline":
                lines.append(f"{self._pad(indent)}System.out.print({self._print_expr(inst.args)});")
            elif inst.kind == "return":
                if in_constructor:
                    lines.append(f"{self._pad(indent)}return;")
                elif inst.value is None:
                    if return_type == "void":
                        lines.append(f"{self._pad(indent)}return;")
                    else:
                        lines.append(self._default_return_line(return_type, indent))
                else:
                    lines.append(f"{self._pad(indent)}return {self._expr(inst.value)};")
            elif inst.kind == "break":
                lines.append(f"{self._pad(indent)}break;")
            elif inst.kind == "continue":
                lines.append(f"{self._pad(indent)}continue;")
            elif inst.kind == "nop":
                lines.append(f"{self._pad(indent)};")

        return lines

    def _call_line(self, inst: TACInstruction, types: dict[str, object]) -> str:
        name = (inst.name or "").strip()
        args = [self._expr(arg) for arg in inst.args]

        if name == "len" and inst.target and args:
            arg_type = self._infer_expr_type(inst.args[0] if inst.args else None, types)
            arg_name = self._internal_type_name(arg_type)
            if arg_name == "string":
                return f"{inst.target} = {args[0]}.length();"
            if self._java_type(arg_type).endswith("[]"):
                return f"{inst.target} = {args[0]}.length;"
            return f"{inst.target} = {args[0]}.size();"

        if name == "append" and len(args) == 2:
            return f"{args[0]}.add({args[1]});"

        if name == "sum" and inst.target and args:
            self.helpers.add("sumHelper")
            return f"{inst.target} = sumHelper({args[0]});"

        if name in {"min", "max"} and inst.target and args:
            self.imports.add("import java.util.Collections;")
            return f"{inst.target} = Collections.{name}({args[0]});"

        if name == "abs" and inst.target and args:
            self.imports.add("import java.lang.Math;")
            return f"{inst.target} = Math.abs({args[0]});"

        if name == "round" and inst.target and args:
            self.imports.add("import java.lang.Math;")
            return f"{inst.target} = (int) Math.round({args[0]});"

        if name == "input" and inst.target:
            self.helpers.add("inputHelper")
            self.imports.add("import java.util.Scanner;")
            return f"{inst.target} = inputHelper();"

        if name in self.class_names:
            call = f"new {name}({', '.join(args)})"
            return f"{inst.target} = {call};" if inst.target else f"{call};"

        if name.endswith(".append") and len(args) == 1:
            owner = self._expr(name.rsplit(".", 1)[0])
            return f"{owner}.add({args[0]});"

        if name == "sort" and args:
            self.imports.add("import java.util.Collections;")
            return f"Collections.sort({args[0]});"

        if name.endswith(".sort"):
            self.imports.add("import java.util.Collections;")
            owner = self._expr(name.rsplit(".", 1)[0])
            return f"Collections.sort({owner});"

        if name.startswith("math."):
            mapped = self._map_math_call(name)
            call = f"{mapped}({', '.join(args)})"
            self.imports.add("import java.lang.Math;")
            return f"{inst.target} = {call};" if inst.target else f"{call};"

        if name.startswith("random."):
            self.helpers.add("randomIntHelper")
            self.imports.add("import java.util.Random;")
            if name.endswith("randint") and len(args) == 2 and inst.target:
                return f"{inst.target} = randomIntHelper({args[0]}, {args[1]});"

        call = f"{self._expr(name)}({', '.join(args)})"
        return f"{inst.target} = {call};" if inst.target else f"{call};"

    def _map_math_call(self, name: str) -> str:
        return {
            "math.sqrt": "Math.sqrt",
            "math.pow": "Math.pow",
            "math.floor": "Math.floor",
            "math.ceil": "Math.ceil",
            "math.sin": "Math.sin",
            "math.cos": "Math.cos",
            "math.tan": "Math.tan",
            "math.log": "Math.log",
            "math.exp": "Math.exp",
            "math.fabs": "Math.abs",
        }.get(name, name.replace("math.", "Math."))

    def _print_expr(self, args: list[str]) -> str:
        if not args:
            return '""'
        parts = [f"String.valueOf({self._expr(arg)})" for arg in args]
        return " + \" \" + ".join(parts)

    def _helper_lines(self, name: str) -> list[str]:
        if name == "inputHelper":
            return [
                "    static String inputHelper() {",
                "        Scanner scanner = new Scanner(System.in);",
                "        return scanner.nextLine();",
                "    }",
            ]
        if name == "sumHelper":
            self.imports.add("import java.util.ArrayList;")
            return [
                "    static int sumHelper(ArrayList<Integer> values) {",
                "        int sum = 0;",
                "        for (int value : values) {",
                "            sum += value;",
                "        }",
                "        return sum;",
                "    }",
            ]
        if name == "randomIntHelper":
            return [
                "    static int randomIntHelper(int start, int end) {",
                "        Random random = new Random();",
                "        return random.nextInt(end - start + 1) + start;",
                "    }",
            ]
        return []

    def _infer_types(
        self,
        fn: TACFunction,
        seed_types: dict[str, object] | None = None,
    ) -> dict[str, object]:
        types = super()._infer_types(fn, seed_types)
        for inst in fn.instructions:
            if inst.kind != "call" or not inst.target:
                continue
            if inst.java_type is not None:
                types[inst.target] = inst.java_type
                continue
            name = (inst.name or "").strip()
            if name == "len":
                types[inst.target] = "int"
            elif name in {"sum", "min", "max"}:
                types[inst.target] = "int"
            elif name.startswith("math."):
                types[inst.target] = "double"
            elif name.startswith("random."):
                types[inst.target] = "int"
            elif name == "input":
                types[inst.target] = "string"
        return types

    def _external_type_to_internal(self, external_type: object) -> object:
        if not isinstance(external_type, str):
            return external_type
        return {
            "String": "string",
            "boolean": "bool",
            "ArrayList<Integer>": "list",
        }.get(external_type, external_type)

    def _infer_return_type(self, fn: TACFunction, types: Optional[dict[str, object]] = None) -> object:
        if getattr(fn, "return_type", None) is not None:
            return fn.return_type
        known = types or self._infer_types(fn)
        seen: set[str] = set()
        for inst in fn.instructions:
            if inst.kind == "return" and inst.value is not None:
                seen.add(self._internal_type_name(self._infer_expr_type(inst.value, known)))

        if not seen:
            return "int"
        if "list" in seen:
            return "ArrayList<Integer>"
        if "string" in seen:
            return "String"
        if "double" in seen:
            return "double"
        if "bool" in seen:
            return "boolean"
        return "int"

    def _infer_expr_type(self, text: str | None, known: dict[str, object]) -> object:
        if text and text.strip().startswith("__list__("):
            return "list"
        return super()._infer_expr_type(text, known)

    def _binary_expr(
        self,
        op: str,
        left: str | None,
        right: str | None,
        types: dict[str, object],
    ) -> str:
        left_expr = self._expr(left)
        right_expr = self._expr(right)
        left_type = self._infer_expr_type(left, types)
        right_type = self._infer_expr_type(right, types)

        left_name = self._internal_type_name(left_type)
        right_name = self._internal_type_name(right_type)

        if op == "*" and left_name == "string":
            return f"{left_expr}.repeat({right_expr})"
        if op == "*" and right_name == "string":
            return f"{right_expr}.repeat({left_expr})"
        if op in {"==", "!="} and "string" in {left_name, right_name}:
            equals = f"{left_expr}.equals({right_expr})"
            return equals if op == "==" else f"!{equals}"
        return f"{left_expr} {op} {right_expr}"

    def _expr(self, text: str | None) -> str:
        if text is None:
            return ""
        stripped = text.strip()
        if stripped.startswith("__list__(") and stripped.endswith(")"):
            self.imports.add("import java.util.ArrayList;")
            self.imports.add("import java.util.Arrays;")
            inner = stripped[len("__list__("):-1].strip()
            if not inner:
                return "new ArrayList<>()"
            return f"new ArrayList<>(Arrays.asList({inner}))"
        out = stripped
        out = re.sub(r"\bself\.", "this.", out)
        out = re.sub(r"\bself\b", "this", out)
        return out

    def _internal_type_name(self, typ: object) -> str:
        name = getattr(typ, "name", str(typ))
        return {
            "String": "string",
            "boolean": "bool",
            "ArrayList": "list",
            "HashMap": "map",
            "HashSet": "set",
        }.get(name, name)

    def _java_type(self, typ: object) -> str:
        if typ is None:
            return "Object"
        name = getattr(typ, "name", None)
        if name is not None:
            if getattr(typ, "is_array", False):
                return f"{self._java_type(name)}[]"
            generics = getattr(typ, "generics", [])
            if name in {"ArrayList", "HashMap", "HashSet", "Map.Entry"}:
                package = "java.util." + name.split(".", 1)[0]
                self.imports.add(f"import {package};")
            if generics:
                params = ", ".join(self._boxed_java_type(item) for item in generics)
                return f"{name}<{params}>"
            return {
                "null": "Object",
                "None": "void",
            }.get(name, name)
        return {
            "string": "String",
            "bool": "boolean",
            "list": self._java_type_from_named_collection("ArrayList<Integer>", "ArrayList"),
            "map": self._java_type_from_named_collection("HashMap<Object, Object>", "HashMap"),
            "set": self._java_type_from_named_collection("HashSet<Object>", "HashSet"),
        }.get(typ, typ)

    def _java_type_from_named_collection(self, rendered: str, collection: str) -> str:
        self.imports.add(f"import java.util.{collection};")
        return rendered

    def _boxed_java_type(self, typ: object) -> str:
        boxed = {
            "int": "Integer",
            "long": "Long",
            "double": "Double",
            "boolean": "Boolean",
            "char": "Character",
            "void": "Object",
        }
        rendered = self._java_type(typ)
        return boxed.get(rendered, rendered)

    def _default_value(self, typ: object) -> str:
        name = getattr(typ, "name", str(typ))
        return {
            "int": "0",
            "long": "0L",
            "double": "0.0",
            "boolean": "false",
            "bool": "false",
            "String": '""',
            "string": '""',
            "ArrayList": "new ArrayList<>()",
            "list": "new ArrayList<>()",
            "HashMap": "new HashMap<>()",
            "HashSet": "new HashSet<>()",
            "void": "",
        }.get(name, "null")

    def _param_decl(self, name: str, types: dict[str, object]) -> str:
        return f"{self._java_type(types.get(name, 'int'))} {name}"

    def _default_return_line(self, return_type: str, indent: int) -> str:
        defaults = {
            "int": "0",
            "double": "0.0",
            "boolean": "false",
            "String": '""',
            "ArrayList<Integer>": "new ArrayList<>()",
        }
        return f"{self._pad(indent)}return {defaults.get(return_type, 'null')};"

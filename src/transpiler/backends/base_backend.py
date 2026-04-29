from __future__ import annotations

import re

from ..core.tac import TACClass, TACFunction, TACInstruction, TACProgram


class BaseBackend:
    def _prepare_program(self, program: TACProgram) -> None:
        self.class_names = {cls.name for cls in program.classes}
        self.class_field_types: dict[str, dict[str, object]] = {}
        self.function_types: dict[str, dict[str, object]] = {}
        self.method_types: dict[str, dict[str, object]] = {}
        self.function_return_types: dict[str, object] = {}
        self.method_return_types: dict[str, object] = {}

        for cls in program.classes:
            field_types = self._infer_class_field_types(cls)
            self.class_field_types[cls.name] = field_types
            seed_types = self._seed_method_types(field_types)
            for method in cls.methods:
                types = self._infer_types(method, seed_types)
                self.method_types[f"{cls.name}.{method.name}"] = types
                if method.name != "__init__":
                    self.method_return_types[f"{cls.name}.{method.name}"] = self._infer_return_type(
                        method,
                        types,
                    )

        for fn in program.functions:
            types = self._infer_types(fn)
            self.function_types[fn.name] = types
            self.function_return_types[fn.name] = self._infer_return_type(fn, types)

    def _infer_class_field_types(self, cls: TACClass) -> dict[str, object]:
        field_types: dict[str, object] = {}

        for _ in range(max(1, len(cls.methods) + 1)):
            changed = False
            seed_types = self._seed_method_types(field_types)
            for method in cls.methods:
                types = self._infer_types(method, seed_types)
                for inst in method.instructions:
                    if inst.kind == "member_assign" and inst.object_ref in {"self", "this"}:
                        field_type = inst.java_type or self._infer_expr_type(inst.value, types)
                        if self._merge_type(field_types, inst.member or "", field_type):
                            changed = True
            if not changed:
                break

        return field_types

    def _infer_types(
        self,
        fn: TACFunction,
        seed_types: dict[str, object] | None = None,
    ) -> dict[str, object]:
        types: dict[str, object] = dict(seed_types or {})
        types.update(getattr(fn, "param_types", {}))
        types.update(getattr(fn, "local_types", {}))

        for inst in fn.instructions:
            if inst.kind == "assign" and inst.target:
                self._merge_type(types, inst.target, inst.java_type or self._infer_expr_type(inst.value, types))
            elif inst.kind == "member_assign" and inst.member:
                typ = self._infer_expr_type(inst.value, types)
                if inst.object_ref in {"self", "this"}:
                    self._merge_type(types, f"self.{inst.member}", typ)
                    self._merge_type(types, f"this.{inst.member}", typ)
                else:
                    self._merge_type(types, f"{inst.object_ref}.{inst.member}", typ)
            elif inst.kind == "binop" and inst.target:
                if inst.java_type is not None:
                    self._merge_type(types, inst.target, inst.java_type)
                    continue
                left_type = self._infer_expr_type(inst.left, types)
                right_type = self._infer_expr_type(inst.right, types)
                left_name = self._type_name(left_type)
                right_name = self._type_name(right_type)
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
                elif op == "*" and "string" in {left_name, right_name}:
                    typ = "string"
                elif op == "+" and "string" in {left_name, right_name}:
                    typ = "string"
                elif "double" in {left_name, right_name}:
                    typ = "double"
                else:
                    typ = "int"
                self._merge_type(types, inst.target, typ)
            elif inst.kind == "unop" and inst.target:
                if inst.java_type is not None:
                    self._merge_type(types, inst.target, inst.java_type)
                    continue
                value_type = self._infer_expr_type(inst.value, types)
                self._merge_type(types, inst.target, "bool" if inst.op == "!" else value_type)
            elif inst.kind == "call" and inst.target:
                if inst.java_type is not None:
                    self._merge_type(types, inst.target, inst.java_type)
                    continue
                call_name = (inst.name or "").strip()
                if call_name in self.class_names:
                    self._merge_type(types, inst.target, call_name)
                elif call_name in self.function_return_types:
                    self._merge_type(
                        types,
                        inst.target,
                        self._external_type_to_internal(self.function_return_types[call_name]),
                    )
                elif call_name in self.method_return_types:
                    self._merge_type(
                        types,
                        inst.target,
                        self._external_type_to_internal(self.method_return_types[call_name]),
                    )
                elif "." in call_name:
                    obj, method = call_name.split(".", 1)
                    cls_name = types.get(obj)
                    if cls_name and f"{cls_name}.{method}" in self.method_return_types:
                        self._merge_type(
                            types,
                            inst.target,
                            self._external_type_to_internal(
                                self.method_return_types[f"{cls_name}.{method}"]
                            ),
                        )
                else:
                    self._merge_type(types, inst.target, "int")

        return types

    def _infer_return_type(
        self,
        fn: TACFunction,
        types: dict[str, object] | None = None,
    ) -> object:
        if getattr(fn, "return_type", None) is not None:
            return fn.return_type
        known = types or self._infer_types(fn)
        seen: set[str] = set()
        for inst in fn.instructions:
            if inst.kind == "return" and inst.value is not None:
                seen.add(self._type_name(self._infer_expr_type(inst.value, known)))

        if not seen:
            return "int"
        if "list" in seen:
            return "list"
        if "string" in seen:
            return "string"
        if "double" in seen:
            return "double"
        if "bool" in seen:
            return "bool"
        return "int"

    def _infer_expr_type(self, text: str | None, known: dict[str, object]) -> object:
        if text is None:
            return "int"
        stripped = text.strip()
        if stripped in known:
            return known[stripped]
        member_match = re.fullmatch(r"(self\.|this\.)([A-Za-z_]\w*)", stripped)
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

    def _type_name(self, typ: object) -> str:
        return getattr(typ, "name", str(typ))

    def _merge_type(self, types: dict[str, object], name: str, new_type: object) -> bool:
        old = types.get(name)
        if old is None:
            types[name] = new_type
            return True
        if old == new_type:
            return False
        old_name = self._type_name(old)
        new_name = self._type_name(new_type)
        if old_name == new_name:
            return False
        if {old_name, new_name} <= {"int", "double"}:
            types[name] = "double"
            return old != "double"
        if old_name == "int" and new_name in {"string", "bool", "list", "String", "boolean", "ArrayList"}:
            types[name] = new_type
            return True
        return False

    def _seed_method_types(self, field_types: dict[str, object]) -> dict[str, object]:
        seeded: dict[str, object] = {}
        for field, typ in field_types.items():
            seeded[f"self.{field}"] = typ
            seeded[f"this.{field}"] = typ
        return seeded

    def _external_type_to_internal(self, external_type: str) -> str:
        return external_type

    def _has_return(self, instructions: list[TACInstruction]) -> bool:
        return any(inst.kind == "return" for inst in instructions)

    def _pad(self, indent: int) -> str:
        return " " * (4 * indent)

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
                    if preferred == "string" and "string" in {current, other}:
                        types[text] = "string"
                    elif preferred == "double" and "double" in {current, other}:
                        types[text] = "double"

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

    def _instruction_target(self, inst: TACInstruction) -> str | None:
        if inst.kind in {"assign", "binop", "unop", "call"}:
            return inst.target
        return None

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

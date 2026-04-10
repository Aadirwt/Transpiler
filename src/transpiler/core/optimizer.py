from __future__ import annotations

import ast
import json
import re
from dataclasses import replace

from .tac import TACFunction, TACInstruction, TACProgram


_TEMP_RE = re.compile(r"^_t\d+$")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MEMBER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_NAME_IN_TEXT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_MISSING = object()
_CONTROL_BARRIERS = {
    "if_begin",
    "else_begin",
    "if_end",
    "while_begin",
    "while_end",
    "break",
    "continue",
    "return",
}


class TACOptimizer:
    def optimize(self, program: TACProgram) -> TACProgram:
        self._optimize_function(program.main)
        for fn in program.functions:
            self._optimize_function(fn)
        for cls in program.classes:
            for method in cls.methods:
                self._optimize_function(method)
        return program

    def _optimize_function(self, fn: TACFunction) -> None:
        instructions = fn.instructions
        instructions = self._collapse_temp_assignments(instructions)
        instructions = self._fold_and_propagate(instructions)
        instructions = self._prune_constant_control_flow(instructions)
        instructions = self._remove_redundant_writes(instructions)
        instructions = self._inline_single_use_temps(instructions)
        instructions = self._fold_and_propagate(instructions)
        instructions = self._remove_dead_temps(instructions)
        instructions = self._remove_redundant_self_assignments(instructions)
        instructions = self._collapse_temp_assignments(instructions)
        fn.instructions = instructions
        fn.locals = self._recompute_locals(fn)

    def _collapse_temp_assignments(
        self, instructions: list[TACInstruction]
    ) -> list[TACInstruction]:
        uses = self._count_name_uses(instructions)
        collapsed: list[TACInstruction] = []
        index = 0

        while index < len(instructions):
            inst = instructions[index]
            if (
                index + 1 < len(instructions)
                and inst.target
                and _TEMP_RE.fullmatch(inst.target)
                and inst.kind in {"assign", "binop", "unop", "call"}
                and uses.get(inst.target, 0) == 1
            ):
                nxt = instructions[index + 1]
                if nxt.kind == "assign" and nxt.value == inst.target and nxt.target:
                    collapsed.append(replace(inst, target=nxt.target))
                    index += 2
                    continue

            collapsed.append(inst)
            index += 1

        return collapsed

    def _inline_single_use_temps(
        self, instructions: list[TACInstruction]
    ) -> list[TACInstruction]:
        uses = self._count_name_uses(instructions)
        optimized: list[TACInstruction] = []
        index = 0

        while index < len(instructions):
            inst = instructions[index]
            if (
                index + 1 < len(instructions)
                and inst.target
                and _TEMP_RE.fullmatch(inst.target)
                and uses.get(inst.target, 0) == 1
            ):
                expr = self._inline_expr_for(inst)
                if expr is not None:
                    replaced = self._replace_temp_in_instruction(
                        instructions[index + 1], inst.target, expr
                    )
                    if replaced is not None:
                        optimized.append(replaced)
                        index += 2
                        continue

            optimized.append(inst)
            index += 1

        return optimized

    def _fold_and_propagate(self, instructions: list[TACInstruction]) -> list[TACInstruction]:
        env: dict[str, str] = {}
        optimized: list[TACInstruction] = []

        for inst in instructions:
            if inst.kind in {"if_begin", "while_begin"}:
                condition = self._resolve_atom(inst.condition, env)
                optimized.append(replace(inst, condition=condition))
                env.clear()
                continue

            if inst.kind == "return":
                value = self._resolve_atom(inst.value, env)
                optimized.append(replace(inst, value=value))
                env.clear()
                continue

            if inst.kind in {"else_begin", "if_end", "while_end", "break", "continue"}:
                optimized.append(inst)
                env.clear()
                continue

            if inst.kind == "assign":
                value = self._resolve_atom(inst.value, env)
                optimized.append(replace(inst, value=value))
                self._write_env(env, inst.target, value)
                continue

            if inst.kind == "binop":
                left = self._resolve_atom(inst.left, env)
                right = self._resolve_atom(inst.right, env)
                folded = self._fold_binop(inst.op or "", left, right)
                if folded is not _MISSING:
                    value = self._literal_text(folded)
                    optimized.append(
                        TACInstruction(kind="assign", target=inst.target, value=value)
                    )
                    self._write_env(env, inst.target, value)
                    continue

                simplified = self._simplify_binop(inst.op or "", left, right)
                if simplified is not None:
                    optimized.append(
                        TACInstruction(kind="assign", target=inst.target, value=simplified)
                    )
                    self._write_env(env, inst.target, simplified)
                    continue

                optimized.append(replace(inst, left=left, right=right))
                self._write_env(env, inst.target, None)
                continue

            if inst.kind == "unop":
                value = self._resolve_atom(inst.value, env)
                folded = self._fold_unop(inst.op or "", value)
                if folded is not _MISSING:
                    text = self._literal_text(folded)
                    optimized.append(
                        TACInstruction(kind="assign", target=inst.target, value=text)
                    )
                    self._write_env(env, inst.target, text)
                    continue

                optimized.append(replace(inst, value=value))
                self._write_env(env, inst.target, None)
                continue

            if inst.kind == "call":
                args = [self._resolve_atom(arg, env) for arg in inst.args]
                name = self._resolve_atom(inst.name, env)
                optimized.append(replace(inst, args=args, name=name))
                self._write_env(env, inst.target, None)
                continue

            if inst.kind == "member_assign":
                value = self._resolve_atom(inst.value, env)
                optimized.append(replace(inst, value=value))
                self._clear_aliases(env, inst.object_ref)
                continue

            if inst.kind in {"print", "print_inline"}:
                args = [self._resolve_atom(arg, env) for arg in inst.args]
                optimized.append(replace(inst, args=args))
                continue

            optimized.append(inst)

        return optimized

    def _prune_constant_control_flow(
        self, instructions: list[TACInstruction]
    ) -> list[TACInstruction]:
        pruned: list[TACInstruction] = []
        index = 0

        while index < len(instructions):
            inst = instructions[index]

            if inst.kind == "if_begin":
                then_block, else_block, next_index = self._extract_if_blocks(
                    instructions, index
                )
                then_block = self._prune_constant_control_flow(then_block)
                else_block = (
                    self._prune_constant_control_flow(else_block)
                    if else_block is not None
                    else None
                )
                condition = (inst.condition or "").strip()

                if condition == "true":
                    pruned.extend(then_block)
                elif condition == "false":
                    if else_block is not None:
                        pruned.extend(else_block)
                else:
                    pruned.append(inst)
                    pruned.extend(then_block)
                    if else_block is not None:
                        pruned.append(TACInstruction(kind="else_begin"))
                        pruned.extend(else_block)
                    pruned.append(TACInstruction(kind="if_end"))

                index = next_index
                continue

            if inst.kind == "while_begin":
                body, next_index = self._extract_while_body(instructions, index)
                body = self._prune_constant_control_flow(body)
                condition = (inst.condition or "").strip()

                if condition != "false":
                    pruned.append(inst)
                    pruned.extend(body)
                    pruned.append(TACInstruction(kind="while_end"))

                index = next_index
                continue

            pruned.append(inst)
            index += 1

        return pruned

    def _remove_redundant_writes(
        self, instructions: list[TACInstruction]
    ) -> list[TACInstruction]:
        keep = [True] * len(instructions)
        pending_writes: dict[str, int] = {}

        for index, inst in enumerate(instructions):
            if inst.kind in _CONTROL_BARRIERS:
                pending_writes.clear()
                continue

            for name in self._referenced_names(inst):
                pending_writes.pop(name, None)

            target = self._instruction_target(inst)
            if target:
                previous = pending_writes.pop(target, None)
                if previous is not None:
                    keep[previous] = False

                if inst.kind in {"assign", "binop", "unop"}:
                    pending_writes[target] = index

        return [inst for inst, keep_inst in zip(instructions, keep) if keep_inst]

    def _remove_dead_temps(self, instructions: list[TACInstruction]) -> list[TACInstruction]:
        uses = self._count_name_uses(instructions)
        kept: list[TACInstruction] = []

        for inst in instructions:
            if (
                inst.target
                and _TEMP_RE.fullmatch(inst.target)
                and inst.kind in {"assign", "binop", "unop"}
                and uses.get(inst.target, 0) == 0
            ):
                continue
            kept.append(inst)

        return kept

    def _remove_redundant_self_assignments(
        self, instructions: list[TACInstruction]
    ) -> list[TACInstruction]:
        return [
            inst
            for inst in instructions
            if not (
                inst.kind == "assign"
                and inst.target is not None
                and inst.value is not None
                and inst.target == inst.value.strip()
            )
        ]

    def _inline_expr_for(self, inst: TACInstruction) -> str | None:
        if inst.kind == "assign" and inst.value is not None:
            return inst.value
        if inst.kind == "binop" and inst.left is not None and inst.right is not None:
            if inst.op == "*" and (
                self._is_string_literal(inst.left) or self._is_string_literal(inst.right)
            ):
                return None
            return f"({inst.left} {inst.op} {inst.right})"
        if inst.kind == "unop" and inst.value is not None:
            return f"({inst.op}{inst.value})"
        return None

    def _replace_temp_in_instruction(
        self, inst: TACInstruction, temp_name: str, expr: str
    ) -> TACInstruction | None:
        changed = False

        def swap(text: str | None) -> str | None:
            nonlocal changed
            if text is None:
                return None
            pattern = rf"\b{re.escape(temp_name)}\b"
            updated, count = re.subn(pattern, lambda _: expr, text)
            if count:
                changed = True
            return updated

        updated_args = [swap(arg) for arg in inst.args]
        updated = replace(
            inst,
            value=swap(inst.value),
            left=swap(inst.left),
            right=swap(inst.right),
            condition=swap(inst.condition),
            name=swap(inst.name),
            object_ref=swap(inst.object_ref),
            args=updated_args,
        )
        return updated if changed else None

    def _recompute_locals(self, fn: TACFunction) -> set[str]:
        locals_set = set(fn.params)
        for inst in fn.instructions:
            if inst.kind in {"assign", "binop", "unop", "call"} and inst.target:
                locals_set.add(inst.target)
        return locals_set

    def _write_env(self, env: dict[str, str], target: str | None, value: str | None) -> None:
        if not target:
            return
        self._clear_aliases(env, target)
        if value and self._is_simple_value(value):
            env[target] = value

    def _clear_aliases(self, env: dict[str, str], changed_name: str | None) -> None:
        if not changed_name:
            return
        env.pop(changed_name, None)
        stale = [name for name, value in env.items() if value == changed_name]
        for name in stale:
            env.pop(name, None)

    def _resolve_atom(self, text: str | None, env: dict[str, str]) -> str | None:
        if text is None:
            return None
        stripped = text.strip()
        return env.get(stripped, text)

    def _count_name_uses(self, instructions: list[TACInstruction]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for inst in instructions:
            for name in self._referenced_names(inst):
                counts[name] = counts.get(name, 0) + 1
        return counts

    def _extract_if_blocks(
        self, instructions: list[TACInstruction], start_index: int
    ) -> tuple[list[TACInstruction], list[TACInstruction] | None, int]:
        then_block: list[TACInstruction] = []
        else_block: list[TACInstruction] | None = None
        current = then_block
        if_depth = 0
        while_depth = 0
        index = start_index + 1

        while index < len(instructions):
            inst = instructions[index]

            if inst.kind == "if_begin":
                if_depth += 1
                current.append(inst)
            elif inst.kind == "while_begin":
                while_depth += 1
                current.append(inst)
            elif inst.kind == "while_end":
                if while_depth > 0:
                    while_depth -= 1
                current.append(inst)
            elif inst.kind == "else_begin" and if_depth == 0 and while_depth == 0:
                else_block = []
                current = else_block
            elif inst.kind == "if_end" and if_depth == 0 and while_depth == 0:
                return then_block, else_block, index + 1
            elif inst.kind == "if_end":
                if_depth -= 1
                current.append(inst)
            else:
                current.append(inst)

            index += 1

        raise ValueError("Unmatched if_begin in TAC instructions")

    def _extract_while_body(
        self, instructions: list[TACInstruction], start_index: int
    ) -> tuple[list[TACInstruction], int]:
        body: list[TACInstruction] = []
        if_depth = 0
        while_depth = 0
        index = start_index + 1

        while index < len(instructions):
            inst = instructions[index]

            if inst.kind == "if_begin":
                if_depth += 1
                body.append(inst)
            elif inst.kind == "while_begin":
                while_depth += 1
                body.append(inst)
            elif inst.kind == "if_end":
                if if_depth > 0:
                    if_depth -= 1
                body.append(inst)
            elif inst.kind == "while_end" and if_depth == 0 and while_depth == 0:
                return body, index + 1
            elif inst.kind == "while_end":
                while_depth -= 1
                body.append(inst)
            else:
                body.append(inst)

            index += 1

        raise ValueError("Unmatched while_begin in TAC instructions")

    def _referenced_names(self, inst: TACInstruction) -> list[str]:
        refs: list[str] = []

        for field in (
            inst.value,
            inst.left,
            inst.right,
            inst.condition,
            inst.name,
            inst.object_ref,
        ):
            refs.extend(self._names_in_text(field))

        for arg in inst.args:
            refs.extend(self._names_in_text(arg))

        return refs

    def _instruction_target(self, inst: TACInstruction) -> str | None:
        if inst.kind in {"assign", "binop", "unop", "call"}:
            return inst.target
        return None

    def _names_in_text(self, text: str | None) -> list[str]:
        if not text:
            return []
        return _NAME_IN_TEXT_RE.findall(text)

    def _is_simple_value(self, text: str) -> bool:
        return (
            self._parse_literal(text) is not _MISSING
            or _IDENT_RE.fullmatch(text) is not None
            or _MEMBER_RE.fullmatch(text) is not None
        )

    def _parse_literal(self, text: str | None) -> object:
        if text is None:
            return _MISSING
        stripped = text.strip()
        if stripped == "true":
            return True
        if stripped == "false":
            return False
        if re.fullmatch(r"-?\d+", stripped):
            return int(stripped)
        if re.fullmatch(r"-?\d+\.\d+", stripped):
            return float(stripped)
        if (
            (stripped.startswith('"') and stripped.endswith('"'))
            or (stripped.startswith("'") and stripped.endswith("'"))
        ):
            try:
                return ast.literal_eval(stripped)
            except (SyntaxError, ValueError):
                return _MISSING
        return _MISSING

    def _is_string_literal(self, text: str | None) -> bool:
        return isinstance(self._parse_literal(text), str)

    def _literal_text(self, value: object) -> str:
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, str):
            return json.dumps(value)
        return str(value)

    def _fold_binop(self, op: str, left: str | None, right: str | None) -> object:
        left_value = self._parse_literal(left)
        right_value = self._parse_literal(right)
        if left_value is _MISSING or right_value is _MISSING:
            return _MISSING

        try:
            if op == "+":
                return left_value + right_value
            if op == "-":
                return left_value - right_value
            if op == "*":
                return left_value * right_value
            if op == "/":
                return left_value / right_value
            if op == "==":
                return left_value == right_value
            if op == "!=":
                return left_value != right_value
            if op == "<":
                return left_value < right_value
            if op == "<=":
                return left_value <= right_value
            if op == ">":
                return left_value > right_value
            if op == ">=":
                return left_value >= right_value
            if op == "&&":
                return bool(left_value) and bool(right_value)
            if op == "||":
                return bool(left_value) or bool(right_value)
        except Exception:
            return _MISSING

        return _MISSING

    def _fold_unop(self, op: str, value: str | None) -> object:
        literal = self._parse_literal(value)
        if literal is _MISSING:
            return _MISSING
        if op == "!":
            return not bool(literal)
        if op == "-":
            return -literal
        return _MISSING

    def _simplify_binop(self, op: str, left: str | None, right: str | None) -> str | None:
        if left is None or right is None:
            return None

        if op == "+" and right == "0":
            return left
        if op == "+" and left == "0":
            return right
        if op == "-" and right == "0":
            return left
        if op == "*" and right == "1":
            return left
        if op == "*" and left == "1":
            return right
        if op == "/" and right == "1":
            return left
        if op == "&&" and right == "true":
            return left
        if op == "&&" and left == "true":
            return right
        if op == "||" and right == "false":
            return left
        if op == "||" and left == "false":
            return right
        return None

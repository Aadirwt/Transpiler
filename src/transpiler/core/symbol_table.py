from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ast_nodes import (
    AnnAssign, Arg, Assign, Attribute, ClassDef, For, FuncDef, Identifier,
    Program, Tuple_,
)


@dataclass
class Symbol:
    name: str
    kind: str
    scope: str
    type_name: str


class SymbolTableBuilder:
    def __init__(self) -> None:
        self.symbols: list[Symbol] = []
        self.scope_stack = ["global"]
        self._seen: set[int] = set()

    def build(self, program: Program) -> list[Symbol]:
        self.visit_program(program)
        return self.symbols

    def to_text(self) -> str:
        if not self.symbols:
            return "(empty)"
        lines = ["name | kind | scope | type", "---- | ---- | ----- | ----"]
        for sym in self.symbols:
            lines.append(f"{sym.name} | {sym.kind} | {sym.scope} | {sym.type_name}")
        return "\n".join(lines)

    def visit_program(self, node: Program) -> None:
        for stmt in node.statements:
            self.visit(stmt)

    def visit(self, node: Any) -> None:
        node_id = id(node)
        if node_id in self._seen:
            return
        self._seen.add(node_id)
        method = getattr(self, f"visit_{type(node).__name__}", self.visit_default)
        method(node)

    def visit_default(self, node: Any) -> None:
        for key, value in getattr(node, "__dict__", {}).items():
            if key.startswith("_"):
                continue
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, tuple):
                        for part in item:
                            self._visit_maybe(part)
                    else:
                        self._visit_maybe(item)
            elif isinstance(value, tuple):
                for item in value:
                    self._visit_maybe(item)
            else:
                self._visit_maybe(value)

    def _visit_maybe(self, value: Any) -> None:
        if value is None or isinstance(value, (str, int, float, bool)):
            return
        module = type(value).__module__
        if module.endswith(".ast_nodes"):
            self.visit(value)

    def visit_FuncDef(self, node: FuncDef) -> None:
        self.add(node.name, "function", getattr(node, "_java_return_type", None))
        self.scope_stack.append(node.name)
        for arg in node.args:
            self.visit_Arg(arg)
        if node.vararg:
            self.visit_Arg(node.vararg)
        if node.kwarg:
            self.visit_Arg(node.kwarg)
        for stmt in node.body:
            self.visit(stmt)
        self.scope_stack.pop()

    def visit_ClassDef(self, node: ClassDef) -> None:
        self.add(node.name, "class", getattr(node, "_java_type", None))
        self.scope_stack.append(node.name)
        for stmt in node.body:
            self.visit(stmt)
        self.scope_stack.pop()

    def visit_Arg(self, node: Arg) -> None:
        self.add(node.name, "parameter", getattr(node, "_java_type", None))

    def visit_Assign(self, node: Assign) -> None:
        for target in node.targets:
            self.add_target(target, "variable")
        self.visit(node.value)

    def visit_AnnAssign(self, node: AnnAssign) -> None:
        self.add_target(node.target, "variable")
        if node.value:
            self.visit(node.value)

    def visit_For(self, node: For) -> None:
        self.add_target(node.target, "loop-variable")
        self.visit(node.iterable)
        self.scope_stack.append("for")
        for stmt in node.body:
            self.visit(stmt)
        self.scope_stack.pop()

    def add_target(self, target: Any, kind: str) -> None:
        if isinstance(target, Identifier):
            self.add(target.name, kind, getattr(target, "_java_type", None))
        elif isinstance(target, Attribute):
            self.add(target.attr, "field", getattr(target, "_java_type", None))
        elif isinstance(target, Tuple_):
            for item in target.elements:
                self.add_target(item, kind)

    def add(self, name: str, kind: str, type_obj: Any) -> None:
        self.symbols.append(
            Symbol(
                name=name,
                kind=kind,
                scope=".".join(self.scope_stack),
                type_name=self.type_name(type_obj),
            )
        )

    def type_name(self, type_obj: Any) -> str:
        if type_obj is None:
            return "unknown"
        return str(type_obj)

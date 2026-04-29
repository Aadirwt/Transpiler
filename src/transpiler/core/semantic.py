from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .ast_nodes import (
    AnnAssign, Assign, Attribute, AugAssign, BinaryOp, BoolOp, Break, Call,
    ClassDef, Compare, Continue, Delete, Dict_, For, FuncDef, Global,
    Identifier, If, Import, ImportFrom, List_, Nonlocal, Program, Return, Set_,
    Subscript, Try, Tuple_, UnaryOp, While, With,
)
from .errors import SemanticError


@dataclass
class FunctionInfo:
    arity: int


@dataclass
class ClassInfo:
    methods: dict[str, FunctionInfo] = field(default_factory=dict)
    constructor_arity: int | None = None


class SemanticAnalyzer:
    BUILTIN_FUNCTIONS = {
        "print", "len", "range", "append", "sort", "sum", "min", "max", "input",
        "int", "float", "str", "bool", "list", "dict", "set", "abs", "round",
    }
    BUILTIN_MODULES = {"math", "random"}

    def __init__(self, source_language: str) -> None:
        self.source_language = source_language
        self.scopes: list[set[str]] = [set()]
        self.functions: dict[str, FunctionInfo] = {}
        self.classes: dict[str, ClassInfo] = {}
        self.in_function = 0
        self.loop_depth = 0
        self.call_stack: list[str] = []

    def analyze(self, program: Program) -> None:
        for stmt in program.statements:
            if isinstance(stmt, FuncDef):
                self.functions[stmt.name] = FunctionInfo(arity=len(stmt.args))
                self.scopes[0].add(stmt.name)
            elif isinstance(stmt, ClassDef):
                info = ClassInfo()
                for item in stmt.body:
                    if isinstance(item, FuncDef):
                        arity = len(item.args)
                        if item.name == "__init__":
                            arity = arity - 1 if item.args and item.args[0].name == "self" else arity
                            info.constructor_arity = arity
                        info.methods[item.name] = FunctionInfo(arity=arity)
                self.classes[stmt.name] = info
                self.scopes[0].add(stmt.name)
        for stmt in program.statements:
            self._visit_statement(stmt)

    def _push_scope(self) -> None:
        self.scopes.append(set())

    def _pop_scope(self) -> None:
        self.scopes.pop()

    def _declare(self, name: str) -> None:
        self.scopes[-1].add(name)

    def _is_declared(self, name: str) -> bool:
        return any(name in scope for scope in reversed(self.scopes))

    def _visit_statement(self, stmt: Any) -> None:
        if isinstance(stmt, Assign):
            self._visit_expression(stmt.value)
            for target in stmt.targets:
                self._declare_target(target)
            return
        if isinstance(stmt, AnnAssign):
            if stmt.value:
                self._visit_expression(stmt.value)
            self._declare_target(stmt.target)
            return
        if isinstance(stmt, AugAssign):
            self._visit_expression(stmt.target)
            self._visit_expression(stmt.value)
            return
        if isinstance(stmt, (Import, ImportFrom, Global, Nonlocal, Delete)):
            return
        if isinstance(stmt, Return):
            if self.in_function == 0:
                raise SemanticError("Return statement used outside function.")
            if stmt.value:
                self._visit_expression(stmt.value)
            return
        if isinstance(stmt, Break):
            if self.loop_depth == 0:
                raise SemanticError("break used outside loop.")
            return
        if isinstance(stmt, Continue):
            if self.loop_depth == 0:
                raise SemanticError("continue used outside loop.")
            return
        if isinstance(stmt, If):
            self._visit_expression(stmt.condition)
            for body in [stmt.body, *(body for _, body in stmt.elifs), stmt.else_body or []]:
                self._push_scope()
                for item in body:
                    self._visit_statement(item)
                self._pop_scope()
            return
        if isinstance(stmt, While):
            self._visit_expression(stmt.condition)
            self.loop_depth += 1
            self._push_scope()
            for item in stmt.body:
                self._visit_statement(item)
            self._pop_scope()
            self.loop_depth -= 1
            return
        if isinstance(stmt, For):
            self._visit_expression(stmt.iterable)
            self.loop_depth += 1
            self._push_scope()
            self._declare_target(stmt.target)
            for item in stmt.body:
                self._visit_statement(item)
            self._pop_scope()
            self.loop_depth -= 1
            return
        if isinstance(stmt, FuncDef):
            self._visit_function(stmt)
            return
        if isinstance(stmt, ClassDef):
            for item in stmt.body:
                if isinstance(item, FuncDef):
                    self._visit_function(item, class_name=stmt.name)
            return
        if isinstance(stmt, Try):
            for body in [stmt.body, stmt.else_body or [], stmt.final_body or []]:
                self._push_scope()
                for item in body:
                    self._visit_statement(item)
                self._pop_scope()
            for handler in stmt.handlers:
                self._push_scope()
                if handler.name:
                    self._declare(handler.name)
                for item in handler.body:
                    self._visit_statement(item)
                self._pop_scope()
            return
        if isinstance(stmt, With):
            self._push_scope()
            for ctx, var in stmt.items:
                self._visit_expression(ctx)
                if var:
                    self._declare_target(var)
            for item in stmt.body:
                self._visit_statement(item)
            self._pop_scope()
            return
        self._visit_expression(stmt)

    def _visit_function(self, stmt: FuncDef, class_name: str | None = None) -> None:
        self._push_scope()
        self.in_function += 1
        self.call_stack.append(stmt.name)
        if class_name:
            self._declare(class_name)
            self._declare("this")
        for arg in stmt.args:
            self._declare(arg.name)
        if stmt.vararg:
            self._declare(stmt.vararg.name)
        if stmt.kwarg:
            self._declare(stmt.kwarg.name)
        for item in stmt.body:
            self._visit_statement(item)
        self.call_stack.pop()
        self.in_function -= 1
        self._pop_scope()

    def _declare_target(self, target: Any) -> None:
        if isinstance(target, Identifier):
            self._declare(target.name)
        elif isinstance(target, Tuple_):
            for item in target.elements:
                self._declare_target(item)
        elif isinstance(target, Attribute):
            self._visit_expression(target.obj)
        elif isinstance(target, Subscript):
            self._visit_expression(target.obj)

    def _visit_expression(self, expr: Any) -> None:
        if expr is None:
            return
        if isinstance(expr, Identifier):
            if (
                not self._is_declared(expr.name)
                and expr.name not in self.classes
                and expr.name not in self.functions
                and expr.name not in self.BUILTIN_MODULES
                and expr.name not in self.BUILTIN_FUNCTIONS
            ):
                raise SemanticError(f"Use of undeclared variable '{expr.name}'.")
            return
        if isinstance(expr, (List_, Set_, Tuple_)):
            for item in expr.elements:
                self._visit_expression(item)
            return
        if isinstance(expr, Dict_):
            for item in [*expr.keys, *expr.values]:
                self._visit_expression(item)
            return
        if isinstance(expr, Attribute):
            self._visit_expression(expr.obj)
            return
        if isinstance(expr, Subscript):
            self._visit_expression(expr.obj)
            self._visit_expression(expr.index)
            return
        if isinstance(expr, UnaryOp):
            self._visit_expression(expr.expr)
            return
        if isinstance(expr, BinaryOp):
            self._visit_expression(expr.left)
            self._visit_expression(expr.right)
            return
        if isinstance(expr, BoolOp):
            for value in expr.values:
                self._visit_expression(value)
            return
        if isinstance(expr, Compare):
            self._visit_expression(expr.left)
            for value in expr.comparators:
                self._visit_expression(value)
            return
        if isinstance(expr, Call):
            for arg in expr.args:
                self._visit_expression(arg)
            for _, value in expr.kwargs:
                self._visit_expression(value)
            if isinstance(expr.func, Identifier):
                name = expr.func.name
                if name in self.functions:
                    self._validate_arity(name, self.functions[name].arity, len(expr.args))
                elif name in self.classes:
                    ctor_arity = self.classes[name].constructor_arity
                    if ctor_arity is not None:
                        self._validate_arity(name, ctor_arity, len(expr.args))
                elif name not in self.BUILTIN_FUNCTIONS and not self._is_declared(name):
                    raise SemanticError(f"Call to undefined function or class '{name}'.")
            else:
                self._visit_expression(expr.func)
            return

    def _validate_arity(self, name: str, expected: int, got: int) -> None:
        if expected != got:
            raise SemanticError(f"Function '{name}' expects {expected} args, got {got}.")

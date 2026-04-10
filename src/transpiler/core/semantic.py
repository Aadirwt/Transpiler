from __future__ import annotations

from dataclasses import dataclass, field

from .ast_nodes import (
    Assign,
    Binary,
    Break,
    Call,
    ClassDef,
    Continue,
    ExprStmt,
    Expression,
    For,
    FunctionDef,
    If,
    LetDecl,
    Literal,
    ListLiteral,
    Member,
    MemberAssign,
    Print,
    Program,
    Return,
    Statement,
    Unary,
    Variable,
    While,
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
        "print",
        "len",
        "append",
        "sort",
        "sum",
        "min",
        "max",
        "input",
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
            if isinstance(stmt, FunctionDef):
                if stmt.name in self.functions:
                    raise SemanticError(f"Duplicate function '{stmt.name}'.")
                self.functions[stmt.name] = FunctionInfo(arity=len(stmt.params))
            elif isinstance(stmt, ClassDef):
                if stmt.name in self.classes:
                    raise SemanticError(f"Duplicate class '{stmt.name}'.")
                class_info = ClassInfo()
                for method in stmt.methods:
                    if method.name in class_info.methods:
                        raise SemanticError(
                            f"Duplicate method '{method.name}' in class '{stmt.name}'."
                        )
                    arity = len(method.params)
                    if method.name == "__init__":
                        arity = arity - 1 if method.params and method.params[0] == "self" else arity
                        class_info.constructor_arity = arity
                    class_info.methods[method.name] = FunctionInfo(arity=arity)
                self.classes[stmt.name] = class_info

        for stmt in program.statements:
            self._visit_statement(stmt)

    def _push_scope(self) -> None:
        self.scopes.append(set())

    def _pop_scope(self) -> None:
        self.scopes.pop()

    def _declare(self, name: str) -> None:
        if name in self.scopes[-1]:
            raise SemanticError(f"Duplicate variable '{name}' in same scope.")
        self.scopes[-1].add(name)

    def _is_declared(self, name: str) -> bool:
        return any(name in scope for scope in reversed(self.scopes))

    def _visit_statement(self, stmt: Statement) -> None:
        if isinstance(stmt, LetDecl):
            self._visit_expression(stmt.value)
            self._declare(stmt.name)
            return

        if isinstance(stmt, Assign):
            self._visit_expression(stmt.value)
            if not self._is_declared(stmt.name):
                if self.source_language == "python":
                    self.scopes[-1].add(stmt.name)
                else:
                    raise SemanticError(
                        f"Assignment to undeclared variable '{stmt.name}'."
                    )
            return

        if isinstance(stmt, MemberAssign):
            self._visit_expression(stmt.target.obj)
            self._visit_expression(stmt.value)
            return

        if isinstance(stmt, Print):
            for value in stmt.values:
                self._visit_expression(value)
            return

        if isinstance(stmt, ExprStmt):
            self._visit_expression(stmt.expr)
            return

        if isinstance(stmt, Return):
            if self.in_function == 0:
                raise SemanticError("Return statement used outside function.")
            if self._in_constructor() and stmt.value is not None:
                raise SemanticError("Constructor '__init__' cannot return a value.")
            if stmt.value is not None:
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
            self._push_scope()
            for inner in stmt.then_body:
                self._visit_statement(inner)
            self._pop_scope()
            self._push_scope()
            for inner in stmt.else_body:
                self._visit_statement(inner)
            self._pop_scope()
            return

        if isinstance(stmt, While):
            self._visit_expression(stmt.condition)
            self.loop_depth += 1
            self._push_scope()
            for inner in stmt.body:
                self._visit_statement(inner)
            self._pop_scope()
            self.loop_depth -= 1
            return

        if isinstance(stmt, For):
            self.loop_depth += 1
            self._push_scope()
            if stmt.init is not None:
                self._visit_statement(stmt.init)
            if stmt.condition is not None:
                self._visit_expression(stmt.condition)
            if stmt.increment is not None:
                self._visit_statement(stmt.increment)
            for inner in stmt.body:
                self._visit_statement(inner)
            self._pop_scope()
            self.loop_depth -= 1
            return

        if isinstance(stmt, FunctionDef):
            self._visit_function(stmt)
            return

        if isinstance(stmt, ClassDef):
            for method in stmt.methods:
                self._visit_method(stmt.name, method)
            return

        raise SemanticError(f"Unsupported statement node: {type(stmt).__name__}")

    def _visit_function(self, stmt: FunctionDef) -> None:
        self._push_scope()
        self.in_function += 1
        self.call_stack.append(stmt.name)
        for param in stmt.params:
            self._declare(param)
        for inner in stmt.body:
            self._visit_statement(inner)
        self.call_stack.pop()
        self.in_function -= 1
        self._pop_scope()

    def _visit_method(self, class_name: str, method: FunctionDef) -> None:
        self._push_scope()
        self.in_function += 1
        self.call_stack.append(method.name)
        self.scopes[-1].add(class_name)
        self.scopes[-1].add("this")
        for param in method.params:
            self._declare(param)
        for inner in method.body:
            self._visit_statement(inner)
        self.call_stack.pop()
        self.in_function -= 1
        self._pop_scope()

    def _visit_expression(self, expr: Expression) -> None:
        if isinstance(expr, Literal):
            return

        if isinstance(expr, ListLiteral):
            for value in expr.values:
                self._visit_expression(value)
            return

        if isinstance(expr, Variable):
            if (
                not self._is_declared(expr.name)
                and expr.name not in self.classes
                and expr.name not in self.functions
                and expr.name not in self.BUILTIN_MODULES
            ):
                raise SemanticError(f"Use of undeclared variable '{expr.name}'.")
            return

        if isinstance(expr, Member):
            self._visit_expression(expr.obj)
            return

        if isinstance(expr, Unary):
            self._visit_expression(expr.value)
            return

        if isinstance(expr, Binary):
            self._visit_expression(expr.left)
            self._visit_expression(expr.right)
            return

        if isinstance(expr, Call):
            for arg in expr.args:
                self._visit_expression(arg)

            if isinstance(expr.callee, Variable):
                name = expr.callee.name
                if name in self.functions:
                    self._validate_arity(name, self.functions[name].arity, len(expr.args))
                elif name in self.BUILTIN_FUNCTIONS:
                    return
                elif name in self.classes:
                    ctor_arity = self.classes[name].constructor_arity
                    if ctor_arity is None:
                        if expr.args:
                            raise SemanticError(
                                f"Class '{name}' does not define a constructor that takes arguments."
                            )
                    else:
                        self._validate_arity(name, ctor_arity, len(expr.args))
                elif not self._is_declared(name):
                    raise SemanticError(f"Call to undefined function or class '{name}'.")
                return

            if isinstance(expr.callee, Member):
                if isinstance(expr.callee.obj, Variable):
                    class_name = expr.callee.obj.name
                    if class_name in self.classes:
                        method = self.classes[class_name].methods.get(expr.callee.name)
                        if method is None:
                            raise SemanticError(
                                f"Class '{class_name}' has no method '{expr.callee.name}'."
                            )
                        self._validate_arity(
                            f"{class_name}.{expr.callee.name}",
                            method.arity,
                            len(expr.args),
                        )
                        return
                self._visit_expression(expr.callee.obj)
                return

            self._visit_expression(expr.callee)
            return

        raise SemanticError(f"Unsupported expression node: {type(expr).__name__}")

    def _validate_arity(self, name: str, expected: int, got: int) -> None:
        if expected != got:
            raise SemanticError(f"Function '{name}' expects {expected} args, got {got}.")

    def _in_constructor(self) -> bool:
        return bool(self.call_stack) and self.call_stack[-1] == "__init__"

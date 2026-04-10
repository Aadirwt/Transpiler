from __future__ import annotations

from ..core.ast_nodes import (
    Program,
    ClassDef,
    FunctionDef,
    LetDecl,
    Assign,
    Return,
    ExprStmt,
    Literal,
    Variable,
    Binary,
    Statement,
    Expression,
)

"""Java frontend implementation.

This module uses the pure‑Python :mod:`javalang` library to parse Java source
code and convert it into the shared AST used by the rest of the transpiler.
Only a small subset of Java that maps cleanly to the shared AST is
implemented – classes, methods, fields, simple assignments, return
statements, and basic expressions.
"""


class JavaFrontend:
    def __init__(self) -> None:
        import javalang  # type: ignore
        self.javalang = javalang

    def parse(self, source: str) -> Program:
        tree = self.javalang.parse.parse(source)
        return self._convert(tree)

    def _convert(self, tree) -> Program:
        statements: list[Statement] = []
        for _, node in tree.filter(self.javalang.tree.ClassDeclaration):
            statements.append(self._convert_class(node))
        return Program(statements=statements)

    def _convert_class(self, node) -> ClassDef:
        methods: list[FunctionDef] = []
        for member in node.body:
            if isinstance(member, self.javalang.tree.MethodDeclaration):
                methods.append(self._convert_method(member))
        return ClassDef(name=node.name, methods=methods)

    def _convert_method(self, node) -> FunctionDef:
        params = [param.type.name for param in node.parameters]
        body = [self._convert_statement(stmt) for stmt in node.body]
        return FunctionDef(name=node.name, params=params, body=body)

    def _convert_statement(self, node) -> Statement:
        if isinstance(node, self.javalang.tree.LocalVariableDeclaration):
            decl = node.declarators[0]
            return LetDecl(name=decl.name, value=self._convert_expression(decl.initializer))
        if isinstance(node, self.javalang.tree.StatementExpression):
            expr = node.expression
            if isinstance(expr, self.javalang.tree.Assignment):
                return Assign(name=expr.expressionl.member, value=self._convert_expression(expr.value))
        if isinstance(node, self.javalang.tree.ReturnStatement):
            return Return(value=self._convert_expression(node.expression))
        return ExprStmt(expr=Literal(value=None))

    def _convert_expression(self, expr) -> Expression:
        if isinstance(expr, self.javalang.tree.Literal):
            return Literal(value=expr.value)
        if isinstance(expr, self.javalang.tree.MemberReference):
            return Variable(name=expr.member)
        if isinstance(expr, self.javalang.tree.BinaryOperation):
            return Binary(
                left=self._convert_expression(expr.operandl),
                op=expr.operator,
                right=self._convert_expression(expr.operandr),
            )
        return Variable(name=str(expr))

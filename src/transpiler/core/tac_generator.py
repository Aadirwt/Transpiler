from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

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
from .errors import TACGenerationError
from .tac import TACClass, TACFunction, TACInstruction, TACProgram


@dataclass
class _Context:
    function: TACFunction


class TACGenerator:
    def __init__(self) -> None:
        self.temp_counter = 0

    def generate(self, program: Program) -> TACProgram:
        main_fn = TACFunction(name="__main__", params=[], instructions=[], locals=set())
        main_ctx = _Context(function=main_fn)
        functions: list[TACFunction] = []
        classes: list[TACClass] = []

        for stmt in program.statements:
            if isinstance(stmt, FunctionDef):
                functions.append(self._emit_function(stmt))
            elif isinstance(stmt, ClassDef):
                classes.append(self._emit_class(stmt))
            else:
                self._emit_statement(stmt, main_ctx)

        return TACProgram(main=main_fn, functions=functions, classes=classes)

    def _emit_function(self, stmt: FunctionDef, owner_class: Optional[str] = None) -> TACFunction:
        fn = TACFunction(
            name=stmt.name,
            params=stmt.params,
            instructions=[],
            locals=set(),
            owner_class=owner_class,
        )
        for param in stmt.params:
            fn.locals.add(param)
        ctx = _Context(function=fn)
        for inner in stmt.body:
            self._emit_statement(inner, ctx)
        return fn

    def _emit_class(self, stmt: ClassDef) -> TACClass:
        methods = [self._emit_function(method, owner_class=stmt.name) for method in stmt.methods]
        return TACClass(name=stmt.name, methods=methods)

    def _new_temp(self, ctx: _Context) -> str:
        self.temp_counter += 1
        name = f"_t{self.temp_counter}"
        ctx.function.locals.add(name)
        return name

    def _emit_instruction(self, ctx: _Context, instruction: TACInstruction) -> None:
        ctx.function.instructions.append(instruction)

    def _emit_statement(self, stmt: Statement, ctx: _Context) -> None:
        if isinstance(stmt, LetDecl):
            value = self._emit_expression(stmt.value, ctx)
            ctx.function.locals.add(stmt.name)
            self._emit_instruction(
                ctx, TACInstruction(kind="assign", target=stmt.name, value=value)
            )
            return

        if isinstance(stmt, Assign):
            value = self._emit_expression(stmt.value, ctx)
            ctx.function.locals.add(stmt.name)
            self._emit_instruction(
                ctx, TACInstruction(kind="assign", target=stmt.name, value=value)
            )
            return

        if isinstance(stmt, MemberAssign):
            obj = self._emit_expression(stmt.target.obj, ctx)
            value = self._emit_expression(stmt.value, ctx)
            self._emit_instruction(
                ctx,
                TACInstruction(
                    kind="member_assign",
                    object_ref=obj,
                    member=stmt.target.name,
                    value=value,
                ),
            )
            return

        if isinstance(stmt, Print):
            values = [self._emit_expression(value, ctx) for value in stmt.values]
            kind = "print" if stmt.newline else "print_inline"
            self._emit_instruction(ctx, TACInstruction(kind=kind, args=values))
            return

        if isinstance(stmt, ExprStmt):
            self._emit_expression(stmt.expr, ctx)
            return

        if isinstance(stmt, Return):
            value = self._emit_expression(stmt.value, ctx) if stmt.value else None
            self._emit_instruction(ctx, TACInstruction(kind="return", value=value))
            return

        if isinstance(stmt, Break):
            self._emit_instruction(ctx, TACInstruction(kind="break"))
            return

        if isinstance(stmt, Continue):
            self._emit_instruction(ctx, TACInstruction(kind="continue"))
            return

        if isinstance(stmt, If):
            cond = self._emit_inline_expression(stmt.condition, ctx)
            self._emit_instruction(ctx, TACInstruction(kind="if_begin", condition=cond))
            if not stmt.then_body:
                self._emit_instruction(ctx, TACInstruction(kind="nop"))
            for inner in stmt.then_body:
                self._emit_statement(inner, ctx)
            if stmt.else_body:
                self._emit_instruction(ctx, TACInstruction(kind="else_begin"))
                for inner in stmt.else_body:
                    self._emit_statement(inner, ctx)
            self._emit_instruction(ctx, TACInstruction(kind="if_end"))
            return

        if isinstance(stmt, While):
            cond = self._emit_inline_expression(stmt.condition, ctx)
            self._emit_instruction(
                ctx, TACInstruction(kind="while_begin", condition=cond)
            )
            if not stmt.body:
                self._emit_instruction(ctx, TACInstruction(kind="nop"))
            for inner in stmt.body:
                self._emit_statement(inner, ctx)
            self._emit_instruction(ctx, TACInstruction(kind="while_end"))
            return

        if isinstance(stmt, For):
            if stmt.init is not None:
                self._emit_statement(stmt.init, ctx)
            cond_expr: Expression = stmt.condition if stmt.condition else Literal(True)
            cond = self._emit_inline_expression(cond_expr, ctx)
            self._emit_instruction(
                ctx, TACInstruction(kind="while_begin", condition=cond)
            )
            if not stmt.body and stmt.increment is None:
                self._emit_instruction(ctx, TACInstruction(kind="nop"))
            self._emit_for_body(stmt.body, stmt.increment, ctx)
            if stmt.increment is not None:
                self._emit_statement(stmt.increment, ctx)
            self._emit_instruction(ctx, TACInstruction(kind="while_end"))
            return

        raise TACGenerationError(f"Unsupported statement: {type(stmt).__name__}")

    def _emit_expression(self, expr: Optional[Expression], ctx: _Context) -> str:
        if expr is None:
            return "0"
        if isinstance(expr, Literal):
            return self._literal_text(expr.value)
        if isinstance(expr, ListLiteral):
            values = [self._emit_expression(value, ctx) for value in expr.values]
            return f"__list__({', '.join(values)})"
        if isinstance(expr, Variable):
            return expr.name
        if isinstance(expr, Member):
            return f"{self._emit_expression(expr.obj, ctx)}.{expr.name}"
        if isinstance(expr, Unary):
            value = self._emit_expression(expr.value, ctx)
            temp = self._new_temp(ctx)
            self._emit_instruction(
                ctx,
                TACInstruction(kind="unop", target=temp, op=expr.op, value=value),
            )
            return temp
        if isinstance(expr, Binary):
            left = self._emit_expression(expr.left, ctx)
            right = self._emit_expression(expr.right, ctx)
            temp = self._new_temp(ctx)
            self._emit_instruction(
                ctx,
                TACInstruction(
                    kind="binop",
                    target=temp,
                    left=left,
                    right=right,
                    op=expr.op,
                ),
            )
            return temp
        if isinstance(expr, Call):
            args = [self._emit_expression(arg, ctx) for arg in expr.args]
            callee = self._emit_expression(expr.callee, ctx)
            temp = self._new_temp(ctx)
            self._emit_instruction(
                ctx,
                TACInstruction(kind="call", target=temp, name=callee, args=args),
            )
            return temp
        raise TACGenerationError(f"Unsupported expression: {type(expr).__name__}")

    def _emit_inline_expression(self, expr: Expression, ctx: _Context) -> str:
        if isinstance(expr, Literal):
            return self._literal_text(expr.value)
        if isinstance(expr, ListLiteral):
            values = [self._emit_inline_expression(value, ctx) for value in expr.values]
            return f"__list__({', '.join(values)})"
        if isinstance(expr, Variable):
            return expr.name
        if isinstance(expr, Member):
            return f"{self._emit_inline_expression(expr.obj, ctx)}.{expr.name}"
        if isinstance(expr, Unary):
            return f"({expr.op}{self._emit_inline_expression(expr.value, ctx)})"
        if isinstance(expr, Binary):
            left = self._emit_inline_expression(expr.left, ctx)
            right = self._emit_inline_expression(expr.right, ctx)
            return f"({left} {expr.op} {right})"
        return self._emit_expression(expr, ctx)

    def _emit_for_body(
        self, body: list[Statement], increment: Optional[Statement], ctx: _Context
    ) -> None:
        for inner in body:
            if isinstance(inner, Continue):
                if increment is not None:
                    self._emit_statement(increment, ctx)
                self._emit_instruction(ctx, TACInstruction(kind="continue"))
                continue

            if isinstance(inner, If):
                cond = self._emit_inline_expression(inner.condition, ctx)
                self._emit_instruction(ctx, TACInstruction(kind="if_begin", condition=cond))
                self._emit_for_body(inner.then_body, increment, ctx)
                if inner.else_body:
                    self._emit_instruction(ctx, TACInstruction(kind="else_begin"))
                    self._emit_for_body(inner.else_body, increment, ctx)
                self._emit_instruction(ctx, TACInstruction(kind="if_end"))
                continue

            # Nested loops keep their own continue semantics.
            if isinstance(inner, (While, For)):
                self._emit_statement(inner, ctx)
                continue

            self._emit_statement(inner, ctx)

    def _literal_text(self, value: object) -> str:
        if isinstance(value, str):
            return json.dumps(value)
        if value is True:
            return "true"
        if value is False:
            return "false"
        return str(value)

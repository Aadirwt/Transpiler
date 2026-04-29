from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .ast_nodes import (
    AnnAssign, Assign, Attribute, AugAssign, BinaryOp, BoolOp, Boolean, Break,
    Call, ClassDef, Compare, Continue, Dict_, For, FuncDef, Identifier, If, List_,
    NoneNode, Number, Program, Return, Set_, String, Subscript, Ternary, Tuple_,
    UnaryOp, While,
)
from .errors import TACGenerationError
from .lexer import TokenType
from .tac import TACClass, TACFunction, TACInstruction, TACProgram


@dataclass
class _Context:
    function: TACFunction


BINOP_TEXT = {
    TokenType.PLUS: "+",
    TokenType.MINUS: "-",
    TokenType.STAR: "*",
    TokenType.SLASH: "/",
    TokenType.FLOOR_DIV: "/",
    TokenType.MODULO: "%",
    TokenType.EQ: "==",
    TokenType.NE: "!=",
    TokenType.LT: "<",
    TokenType.LE: "<=",
    TokenType.GT: ">",
    TokenType.GE: ">=",
    TokenType.BIT_AND: "&",
    TokenType.BIT_OR: "|",
    TokenType.BIT_XOR: "^",
    TokenType.LSHIFT: "<<",
    TokenType.RSHIFT: ">>",
}

UNARY_TEXT = {TokenType.NOT: "!", TokenType.MINUS: "-", TokenType.BIT_NOT: "~"}
AUG_TO_BIN = {
    TokenType.PLUS_ASSIGN: TokenType.PLUS,
    TokenType.MINUS_ASSIGN: TokenType.MINUS,
    TokenType.STAR_ASSIGN: TokenType.STAR,
    TokenType.SLASH_ASSIGN: TokenType.SLASH,
    TokenType.FLOOR_DIV_ASSIGN: TokenType.FLOOR_DIV,
    TokenType.MODULO_ASSIGN: TokenType.MODULO,
}


class TACGenerator:
    def __init__(self) -> None:
        self.temp_counter = 0

    def generate(self, program: Program) -> TACProgram:
        main_fn = TACFunction(name="__main__", params=[], instructions=[], locals=set())
        main_ctx = _Context(main_fn)
        functions: list[TACFunction] = []
        classes: list[TACClass] = []
        for stmt in program.statements:
            if isinstance(stmt, FuncDef):
                functions.append(self._emit_function(stmt))
            elif isinstance(stmt, ClassDef):
                classes.append(self._emit_class(stmt))
            else:
                self._emit_statement(stmt, main_ctx)
        return TACProgram(main=main_fn, functions=functions, classes=classes)

    def _emit_function(self, stmt: FuncDef, owner_class: str | None = None) -> TACFunction:
        params = [arg.name for arg in stmt.args]
        if stmt.vararg:
            params.append(stmt.vararg.name)
        if stmt.kwarg:
            params.append(stmt.kwarg.name)
        param_types = {
            arg.name: typ
            for arg in stmt.args
            if (typ := self._metadata_type(arg)) is not None
        }
        if stmt.vararg and (typ := self._metadata_type(stmt.vararg)) is not None:
            param_types[stmt.vararg.name] = typ
        if stmt.kwarg and (typ := self._metadata_type(stmt.kwarg)) is not None:
            param_types[stmt.kwarg.name] = typ
        fn = TACFunction(
            stmt.name,
            params,
            [],
            set(params),
            owner_class=owner_class,
            return_type=self._metadata_type(stmt, attr="_java_return_type"),
            param_types=param_types,
            local_types=dict(param_types),
        )
        ctx = _Context(fn)
        for inner in stmt.body:
            self._emit_statement(inner, ctx)
        return fn

    def _emit_class(self, stmt: ClassDef) -> TACClass:
        methods = [
            self._emit_function(item, owner_class=stmt.name)
            for item in stmt.body
            if isinstance(item, FuncDef)
        ]
        return TACClass(name=stmt.name, methods=methods)

    def _new_temp(self, ctx: _Context, java_type: Any = None) -> str:
        self.temp_counter += 1
        name = f"_t{self.temp_counter}"
        ctx.function.locals.add(name)
        if java_type is not None:
            ctx.function.local_types[name] = java_type
        return name

    def _emit_instruction(self, ctx: _Context, inst: TACInstruction) -> None:
        ctx.function.instructions.append(inst)

    def _emit_statement(self, stmt: Any, ctx: _Context) -> None:
        if isinstance(stmt, Assign):
            value = self._emit_expression(stmt.value, ctx)
            for target in stmt.targets:
                self._emit_assignment(target, value, ctx)
            return
        if isinstance(stmt, AnnAssign):
            value = self._emit_expression(stmt.value, ctx) if stmt.value else self._default_for_node(stmt)
            self._emit_assignment(stmt.target, value, ctx)
            return
        if isinstance(stmt, AugAssign):
            target = self._emit_expression(stmt.target, ctx)
            value = self._emit_expression(stmt.value, ctx)
            op = BINOP_TEXT.get(AUG_TO_BIN.get(stmt.op, TokenType.PLUS), "+")
            java_type = self._metadata_type(stmt) or self._metadata_type(stmt.target)
            temp = self._new_temp(ctx, java_type)
            self._emit_instruction(ctx, TACInstruction("binop", target=temp, left=target, right=value, op=op, java_type=java_type))
            self._emit_assignment(stmt.target, temp, ctx)
            return
        if isinstance(stmt, Call) and self._is_print_call(stmt):
            values = [self._emit_expression(arg, ctx) for arg in stmt.args]
            self._emit_instruction(ctx, TACInstruction(kind="print", args=values))
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
            self._emit_if(stmt, ctx)
            return
        if isinstance(stmt, While):
            self._emit_while(stmt, ctx)
            return
        if isinstance(stmt, For):
            self._emit_for(stmt, ctx)
            return
        if isinstance(stmt, (FuncDef, ClassDef)):
            return
        if stmt is None:
            return
        self._emit_expression(stmt, ctx)

    def _emit_assignment(self, target: Any, value: str, ctx: _Context) -> None:
        if isinstance(target, Identifier):
            ctx.function.locals.add(target.name)
            java_type = self._metadata_type(target)
            if java_type is not None:
                ctx.function.local_types[target.name] = java_type
            self._emit_instruction(ctx, TACInstruction("assign", target=target.name, value=value, java_type=java_type))
            return
        if isinstance(target, Attribute):
            obj = self._emit_expression(target.obj, ctx)
            self._emit_instruction(
                ctx,
                TACInstruction(
                    "member_assign",
                    object_ref=obj,
                    member=target.attr,
                    value=value,
                    java_type=self._metadata_type(target),
                ),
            )
            return
        if isinstance(target, Tuple_):
            for item in target.elements:
                self._emit_assignment(item, value, ctx)
            return
        raise TACGenerationError(f"Unsupported assignment target: {type(target).__name__}")

    def _emit_if(self, stmt: If, ctx: _Context) -> None:
        cond = self._emit_inline_expression(stmt.condition, ctx)
        self._emit_instruction(ctx, TACInstruction("if_begin", condition=cond))
        for inner in stmt.body:
            self._emit_statement(inner, ctx)
        else_chain = self._elif_chain(stmt.elifs, stmt.else_body)
        if else_chain:
            self._emit_instruction(ctx, TACInstruction("else_begin"))
            for inner in else_chain:
                self._emit_statement(inner, ctx)
        self._emit_instruction(ctx, TACInstruction("if_end"))

    def _elif_chain(self, elifs: list[tuple[Any, list[Any]]], else_body: list[Any] | None) -> list[Any]:
        if not elifs:
            return else_body or []
        condition, body = elifs[0]
        return [If(condition, body, elifs[1:], else_body)]

    def _emit_while(self, stmt: While, ctx: _Context) -> None:
        cond = self._emit_inline_expression(stmt.condition, ctx)
        self._emit_instruction(ctx, TACInstruction("while_begin", condition=cond))
        for inner in stmt.body:
            self._emit_statement(inner, ctx)
        self._emit_instruction(ctx, TACInstruction("while_end"))

    def _emit_for(self, stmt: For, ctx: _Context) -> None:
        if isinstance(stmt.target, Identifier) and self._is_range_call(stmt.iterable):
            args = stmt.iterable.args
            if len(args) == 1:
                start, end, step = "0", self._emit_expression(args[0], ctx), "1"
            elif len(args) == 2:
                start, end, step = self._emit_expression(args[0], ctx), self._emit_expression(args[1], ctx), "1"
            elif len(args) == 3:
                start, end, step = self._emit_expression(args[0], ctx), self._emit_expression(args[1], ctx), self._emit_expression(args[2], ctx)
            else:
                raise TACGenerationError("range() supports 1 to 3 arguments only.")
            name = stmt.target.name
            ctx.function.locals.add(name)
            target_type = self._metadata_type(stmt.target)
            if target_type is not None:
                ctx.function.local_types[name] = target_type
            self._emit_instruction(ctx, TACInstruction("assign", target=name, value=start, java_type=target_type))
            compare = ">" if step.startswith("-") else "<"
            self._emit_instruction(ctx, TACInstruction("while_begin", condition=f"{name} {compare} {end}"))
            self._emit_for_body(stmt.body, name, step, ctx)
            self._emit_instruction(ctx, TACInstruction("binop", target=name, left=name, right=step, op="+", java_type=target_type))
            self._emit_instruction(ctx, TACInstruction("while_end"))
            return
        raise TACGenerationError("Only for-loops over range(...) are currently lowered to TAC.")

    def _emit_for_body(self, body: list[Any], loop_name: str, step: str, ctx: _Context) -> None:
        for inner in body:
            if isinstance(inner, Continue):
                self._emit_instruction(ctx, TACInstruction("binop", target=loop_name, left=loop_name, right=step, op="+"))
                self._emit_instruction(ctx, TACInstruction("continue"))
                continue
            if isinstance(inner, If):
                self._emit_for_if(inner, loop_name, step, ctx)
                continue
            self._emit_statement(inner, ctx)

    def _emit_for_if(self, stmt: If, loop_name: str, step: str, ctx: _Context) -> None:
        cond = self._emit_inline_expression(stmt.condition, ctx)
        self._emit_instruction(ctx, TACInstruction("if_begin", condition=cond))
        self._emit_for_body(stmt.body, loop_name, step, ctx)
        else_chain = self._elif_chain(stmt.elifs, stmt.else_body)
        if else_chain:
            self._emit_instruction(ctx, TACInstruction("else_begin"))
            self._emit_for_body(else_chain, loop_name, step, ctx)
        self._emit_instruction(ctx, TACInstruction("if_end"))

    def _emit_expression(self, expr: Any, ctx: _Context) -> str:
        if expr is None:
            return "0"
        if isinstance(expr, Number):
            return str(expr.value)
        if isinstance(expr, String):
            return json.dumps(expr.value)
        if isinstance(expr, Boolean):
            return "true" if expr.value else "false"
        if isinstance(expr, NoneNode):
            return "null"
        if isinstance(expr, Identifier):
            return expr.name
        if isinstance(expr, Attribute):
            return f"{self._emit_expression(expr.obj, ctx)}.{expr.attr}"
        if isinstance(expr, Subscript):
            return f"{self._emit_expression(expr.obj, ctx)}.get({self._emit_expression(expr.index, ctx)})"
        if isinstance(expr, List_):
            return f"__list__({', '.join(self._emit_expression(item, ctx) for item in expr.elements)})"
        if isinstance(expr, (Set_, Tuple_)):
            return f"__list__({', '.join(self._emit_expression(item, ctx) for item in expr.elements)})"
        if isinstance(expr, Dict_):
            return "__dict__()"
        if isinstance(expr, UnaryOp):
            value = self._emit_expression(expr.expr, ctx)
            java_type = self._metadata_type(expr)
            temp = self._new_temp(ctx, java_type)
            self._emit_instruction(ctx, TACInstruction("unop", target=temp, op=UNARY_TEXT.get(expr.op, "!"), value=value, java_type=java_type))
            return temp
        if isinstance(expr, BinaryOp):
            left = self._emit_expression(expr.left, ctx)
            right = self._emit_expression(expr.right, ctx)
            java_type = self._metadata_type(expr)
            temp = self._new_temp(ctx, java_type)
            self._emit_instruction(ctx, TACInstruction("binop", target=temp, left=left, right=right, op=BINOP_TEXT.get(expr.op, "+"), java_type=java_type))
            return temp
        if isinstance(expr, BoolOp):
            return self._emit_boolop(expr, ctx)
        if isinstance(expr, Compare):
            return self._emit_compare(expr, ctx)
        if isinstance(expr, Ternary):
            return f"({self._emit_inline_expression(expr.condition, ctx)} ? {self._emit_expression(expr.true_expr, ctx)} : {self._emit_expression(expr.false_expr, ctx)})"
        if isinstance(expr, Call):
            if self._is_print_call(expr):
                values = [self._emit_expression(arg, ctx) for arg in expr.args]
                self._emit_instruction(ctx, TACInstruction("print", args=values))
                return "0"
            args = [self._emit_expression(arg, ctx) for arg in expr.args]
            callee = self._emit_expression(expr.func, ctx)
            java_type = self._metadata_type(expr)
            temp = self._new_temp(ctx, java_type)
            self._emit_instruction(ctx, TACInstruction("call", target=temp, name=callee, args=args, java_type=java_type))
            return temp
        return str(expr)

    def _emit_inline_expression(self, expr: Any, ctx: _Context) -> str:
        if isinstance(expr, BinaryOp):
            return f"({self._emit_inline_expression(expr.left, ctx)} {BINOP_TEXT.get(expr.op, '+')} {self._emit_inline_expression(expr.right, ctx)})"
        if isinstance(expr, BoolOp):
            op = "&&" if expr.op == TokenType.AND else "||"
            return f"({f' {op} '.join(self._emit_inline_expression(v, ctx) for v in expr.values)})"
        if isinstance(expr, Compare):
            return self._compare_text(expr, ctx)
        return self._emit_expression(expr, ctx)

    def _emit_boolop(self, expr: BoolOp, ctx: _Context) -> str:
        temp = self._new_temp(ctx, self._metadata_type(expr))
        parts = [self._emit_inline_expression(value, ctx) for value in expr.values]
        op = "&&" if expr.op == TokenType.AND else "||"
        self._emit_instruction(ctx, TACInstruction("assign", target=temp, value=f"({f' {op} '.join(parts)})", java_type=self._metadata_type(expr)))
        return temp

    def _is_print_call(self, expr: Call) -> bool:
        return isinstance(expr.func, Identifier) and expr.func.name == "print"

    def _is_range_call(self, expr: Any) -> bool:
        return isinstance(expr, Call) and isinstance(expr.func, Identifier) and expr.func.name == "range"

    def _default_for_node(self, node: Any) -> str:
        type_name = getattr(getattr(node, "_java_type", None), "name", "int")
        return {"String": '""', "boolean": "false", "double": "0.0", "ArrayList": "__list__()"}.get(type_name, "0")

    def _emit_compare(self, expr: Compare, ctx: _Context) -> str:
        temp = self._new_temp(ctx, self._metadata_type(expr))
        self._emit_instruction(
            ctx,
            TACInstruction("assign", target=temp, value=self._compare_text(expr, ctx), java_type=self._metadata_type(expr)),
        )
        return temp

    def _compare_text(self, expr: Compare, ctx: _Context) -> str:
        parts = []
        left = self._emit_inline_expression(expr.left, ctx)
        for op, comparator in zip(expr.ops, expr.comparators):
            right = self._emit_inline_expression(comparator, ctx)
            if op == TokenType.IN:
                parts.append(f"{right}.contains({left})")
            elif op == "not in":
                parts.append(f"!{right}.contains({left})")
            else:
                parts.append(f"{left} {self._compare_op(op)} {right}")
            left = right
        return " && ".join(parts)

    def _compare_op(self, op: Any) -> str:
        return {
            TokenType.EQ: "==",
            TokenType.NE: "!=",
            TokenType.LT: "<",
            TokenType.LE: "<=",
            TokenType.GT: ">",
            TokenType.GE: ">=",
            TokenType.IS: "==",
            "is not": "!=",
        }.get(op, "==")

    def _metadata_type(self, node: Any, attr: str = "_java_type") -> Any:
        typ = getattr(node, attr, None)
        name = getattr(typ, "name", None)
        if name in {"Object", "null"}:
            return None
        return typ

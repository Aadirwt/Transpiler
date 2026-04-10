from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Program:
    statements: list[Statement]


class Statement:
    pass


class Expression:
    pass


@dataclass
class LetDecl(Statement):
    name: str
    value: Expression


@dataclass
class Assign(Statement):
    name: str
    value: Expression


@dataclass
class Print(Statement):
    values: list[Expression]
    newline: bool = True


@dataclass
class If(Statement):
    condition: Expression
    then_body: list[Statement]
    else_body: list[Statement] = field(default_factory=list)


@dataclass
class While(Statement):
    condition: Expression
    body: list[Statement]


@dataclass
class For(Statement):
    init: Optional[Statement]
    condition: Optional[Expression]
    increment: Optional[Statement]
    body: list[Statement]


@dataclass
class FunctionDef(Statement):
    name: str
    params: list[str]
    body: list[Statement]


@dataclass
class Return(Statement):
    value: Optional[Expression]


@dataclass
class ExprStmt(Statement):
    expr: Expression


@dataclass
class Break(Statement):
    pass


@dataclass
class Continue(Statement):
    pass


@dataclass
class ClassDef(Statement):
    name: str
    methods: list[FunctionDef]


@dataclass
class Binary(Expression):
    left: Expression
    op: str
    right: Expression


@dataclass
class Unary(Expression):
    op: str
    value: Expression


@dataclass
class Literal(Expression):
    value: Any


@dataclass
class Variable(Expression):
    name: str


@dataclass
class Call(Expression):
    callee: Expression
    args: list[Expression]


@dataclass
class ListLiteral(Expression):
    values: list[Expression]


@dataclass
class Member(Expression):
    obj: Expression
    name: str


@dataclass
class MemberAssign(Statement):
    target: Member
    value: Expression

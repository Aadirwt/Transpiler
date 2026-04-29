from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


# Literals
@dataclass
class Number:
    value: int | float


@dataclass
class String:
    value: str


@dataclass
class FString:
    value: str


@dataclass
class Boolean:
    value: bool


@dataclass
class NoneNode:
    pass


@dataclass
class Ellipsis_:
    pass


# Collections
@dataclass
class List_:
    elements: list[Any]


@dataclass
class Dict_:
    keys: list[Any]
    values: list[Any]


@dataclass
class Set_:
    elements: list[Any]


@dataclass
class Tuple_:
    elements: list[Any]


# Comprehensions
@dataclass
class ListComp:
    expr: Any
    target: Any
    iterable: Any
    condition: Optional[Any]


@dataclass
class DictComp:
    key: Any
    value: Any
    target: Any
    iterable: Any
    condition: Optional[Any]


@dataclass
class SetComp:
    expr: Any
    target: Any
    iterable: Any
    condition: Optional[Any]


@dataclass
class GeneratorExp:
    expr: Any
    target: Any
    iterable: Any
    condition: Optional[Any]


# Variables and access
@dataclass
class Identifier:
    name: str


@dataclass
class Attribute:
    obj: Any
    attr: str


@dataclass
class Subscript:
    obj: Any
    index: Any


@dataclass
class Slice:
    start: Optional[Any]
    stop: Optional[Any]
    step: Optional[Any]


@dataclass
class StarExpr:
    expr: Any


# Operators
@dataclass
class BinaryOp:
    left: Any
    op: Any
    right: Any


@dataclass
class UnaryOp:
    op: Any
    expr: Any


@dataclass
class Compare:
    left: Any
    ops: list[Any]
    comparators: list[Any]


@dataclass
class BoolOp:
    op: Any
    values: list[Any]


@dataclass
class Ternary:
    condition: Any
    true_expr: Any
    false_expr: Any


@dataclass
class Walrus:
    name: str
    value: Any


# Assignments
@dataclass
class Assign:
    targets: list[Any]
    value: Any


@dataclass
class AugAssign:
    target: Any
    op: Any
    value: Any


@dataclass
class AnnAssign:
    target: Any
    annotation: Any
    value: Optional[Any]


# Control flow
@dataclass
class If:
    condition: Any
    body: list[Any]
    elifs: list[tuple[Any, list[Any]]]
    else_body: Optional[list[Any]]


@dataclass
class While:
    condition: Any
    body: list[Any]
    else_body: Optional[list[Any]]


@dataclass
class For:
    target: Any
    iterable: Any
    body: list[Any]
    else_body: Optional[list[Any]]


@dataclass
class Break:
    pass


@dataclass
class Continue:
    pass


@dataclass
class Pass:
    pass


@dataclass
class Return:
    value: Optional[Any]


@dataclass
class Raise:
    exc: Optional[Any]
    cause: Optional[Any]


@dataclass
class Assert:
    test: Any
    msg: Optional[Any]


@dataclass
class Delete:
    targets: list[Any]


# Functions
@dataclass
class Arg:
    name: str
    annotation: Optional[Any]
    default: Optional[Any]


@dataclass
class FuncDef:
    name: str
    args: list[Arg]
    vararg: Optional[Arg]
    kwarg: Optional[Arg]
    body: list[Any]
    decorators: list[Any]
    returns: Optional[Any]
    is_async: bool = False


@dataclass
class Lambda:
    args: list[Arg]
    body: Any


@dataclass
class Call:
    func: Any
    args: list[Any]
    kwargs: list[tuple[Optional[str], Any]]


@dataclass
class Yield:
    value: Optional[Any]


@dataclass
class YieldFrom:
    value: Any


# Classes
@dataclass
class ClassDef:
    name: str
    bases: list[Any]
    body: list[Any]
    decorators: list[Any]


# Imports
@dataclass
class Import:
    names: list[tuple[str, Optional[str]]]


@dataclass
class ImportFrom:
    module: str
    names: list[tuple[str, Optional[str]]]


# Exceptions and context managers
@dataclass
class Try:
    body: list[Any]
    handlers: list[Any]
    else_body: Optional[list[Any]]
    final_body: Optional[list[Any]]


@dataclass
class ExceptHandler:
    type_: Optional[Any]
    name: Optional[str]
    body: list[Any]


@dataclass
class With:
    items: list[tuple[Any, Optional[Any]]]
    body: list[Any]


@dataclass
class Global:
    names: list[str]


@dataclass
class Nonlocal:
    names: list[str]


@dataclass
class Program:
    statements: list[Any]

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .ast_nodes import (
    AnnAssign, Assign, Attribute, BinaryOp, Boolean, BoolOp, Call, ClassDef,
    Compare, Dict_, For, FuncDef, Identifier, If, List_, NoneNode, Number,
    Program, Return, Set_, String, Subscript, Ternary, Tuple_, While,
)
from .lexer import TokenType


@dataclass
class JavaType:
    name: str
    generics: list["JavaType"] = field(default_factory=list)
    is_array: bool = False
    nullable: bool = False

    def __str__(self) -> str:
        if self.is_array:
            return f"{self.name}[]"
        if self.generics:
            return f"{self.name}<{', '.join(str(g) for g in self.generics)}>"
        return self.name


T_INT = JavaType("int")
T_LONG = JavaType("long")
T_DOUBLE = JavaType("double")
T_BOOLEAN = JavaType("boolean")
T_VOID = JavaType("void")
T_STRING = JavaType("String")
T_OBJECT = JavaType("Object")
T_NULL = JavaType("null", nullable=True)
T_INTEGER = JavaType("Integer")
T_DOUBLE_BOX = JavaType("Double")
T_BOOLEAN_BOX = JavaType("Boolean")


def T_LIST(inner: JavaType = T_OBJECT) -> JavaType:
    return JavaType("ArrayList", [inner])


def T_MAP(k: JavaType = T_OBJECT, v: JavaType = T_OBJECT) -> JavaType:
    return JavaType("HashMap", [k, v])


def T_SET(inner: JavaType = T_OBJECT) -> JavaType:
    return JavaType("HashSet", [inner])


def box(t: JavaType) -> JavaType:
    return {
        "int": T_INTEGER,
        "double": T_DOUBLE_BOX,
        "boolean": T_BOOLEAN_BOX,
    }.get(t.name, t)


def unify(a: JavaType, b: JavaType) -> JavaType:
    if a.name == b.name and a.generics == b.generics:
        return a
    if a.name == "null":
        b.nullable = True
        return b
    if b.name == "null":
        a.nullable = True
        return a
    rank = {"int": 1, "Integer": 1, "long": 2, "double": 3, "Double": 3}
    if a.name in rank and b.name in rank:
        return a if rank[a.name] >= rank[b.name] else b
    if a.name == "String" or b.name == "String":
        return T_STRING
    if a.name == b.name and a.generics and b.generics:
        return JavaType(a.name, [unify(x, y) for x, y in zip(a.generics, b.generics)])
    return T_OBJECT


def is_numeric(t: JavaType) -> bool:
    return t.name in {"int", "long", "double", "Integer", "Double"}


def element_type(t: JavaType) -> JavaType:
    if t.generics:
        return t.generics[0]
    if t.is_array:
        return JavaType(t.name)
    if t.name == "String":
        return JavaType("char")
    return T_OBJECT


ANNOTATION_MAP = {
    "int": T_INT,
    "float": T_DOUBLE,
    "str": T_STRING,
    "bool": T_BOOLEAN,
    "None": T_VOID,
    "Any": T_OBJECT,
    "list": T_LIST(),
    "List": T_LIST(),
    "dict": T_MAP(),
    "Dict": T_MAP(),
    "set": T_SET(),
    "Set": T_SET(),
}

BUILTIN_RETURN_TYPES = {
    "len": T_INT,
    "range": T_LIST(T_INT),
    "print": T_VOID,
    "input": T_STRING,
    "int": T_INT,
    "float": T_DOUBLE,
    "str": T_STRING,
    "bool": T_BOOLEAN,
    "list": T_LIST(),
    "dict": T_MAP(),
    "set": T_SET(),
    "sum": T_INT,
    "min": T_INT,
    "max": T_INT,
    "abs": T_INT,
    "round": T_INT,
    "math.sqrt": T_DOUBLE,
    "math.pow": T_DOUBLE,
    "math.floor": T_DOUBLE,
    "math.ceil": T_DOUBLE,
    "math.sin": T_DOUBLE,
    "math.cos": T_DOUBLE,
    "math.tan": T_DOUBLE,
    "math.log": T_DOUBLE,
    "math.exp": T_DOUBLE,
    "math.fabs": T_DOUBLE,
}


class Scope:
    def __init__(self, parent: Optional["Scope"] = None, kind: str = "block"):
        self.parent = parent
        self.kind = kind
        self.vars: dict[str, JavaType] = {}
        self.return_types: list[JavaType] = []

    def define(self, name: str, type_: JavaType) -> None:
        self.vars[name] = type_

    def lookup(self, name: str) -> JavaType | None:
        if name in self.vars:
            return self.vars[name]
        return self.parent.lookup(name) if self.parent else None

    def function_scope(self) -> "Scope | None":
        if self.kind == "function":
            return self
        return self.parent.function_scope() if self.parent else None


class TypeInferencer:
    def __init__(self) -> None:
        self.global_scope = Scope(kind="global")
        self.scope = self.global_scope
        self.class_stack: list[str] = []
        self.func_return_map: dict[str, JavaType] = {}
        self.class_field_map: dict[str, dict[str, JavaType]] = {}

    def push_scope(self, kind: str = "block") -> None:
        self.scope = Scope(self.scope, kind)

    def pop_scope(self) -> None:
        if self.scope.parent:
            self.scope = self.scope.parent

    def infer(self, node) -> JavaType:
        fn = getattr(self, f"infer_{type(node).__name__}", self.infer_default)
        t = fn(node)
        if not hasattr(node, "_java_type"):
            try:
                node._java_type = t
            except Exception:
                pass
        return t

    def infer_default(self, node) -> JavaType:
        return T_OBJECT

    def infer_Program(self, node: Program) -> JavaType:
        for stmt in node.statements:
            self.infer(stmt)
        return T_VOID

    def infer_Number(self, node: Number) -> JavaType:
        t = T_DOUBLE if isinstance(node.value, float) else T_LONG if node.value > 2**31 - 1 or node.value < -(2**31) else T_INT
        node._java_type = t
        return t

    def infer_String(self, node: String) -> JavaType:
        node._java_type = T_STRING
        return T_STRING

    def infer_Boolean(self, node: Boolean) -> JavaType:
        node._java_type = T_BOOLEAN
        return T_BOOLEAN

    def infer_NoneNode(self, node: NoneNode) -> JavaType:
        node._java_type = T_NULL
        return T_NULL

    def infer_Identifier(self, node: Identifier) -> JavaType:
        t = self.scope.lookup(node.name) or T_OBJECT
        node._java_type = t
        return t

    def infer_List_(self, node: List_) -> JavaType:
        elem = T_OBJECT
        for item in node.elements:
            elem = unify(elem, self.infer(item)) if elem != T_OBJECT else self.infer(item)
        node._java_type = T_LIST(box(elem))
        return node._java_type

    def infer_Dict_(self, node: Dict_) -> JavaType:
        key = T_OBJECT
        val = T_OBJECT
        for item in node.keys:
            key = unify(key, self.infer(item)) if key != T_OBJECT else self.infer(item)
        for item in node.values:
            val = unify(val, self.infer(item)) if val != T_OBJECT else self.infer(item)
        node._java_type = T_MAP(box(key), box(val))
        return node._java_type

    def infer_Set_(self, node: Set_) -> JavaType:
        elem = T_OBJECT
        for item in node.elements:
            elem = unify(elem, self.infer(item)) if elem != T_OBJECT else self.infer(item)
        node._java_type = T_SET(box(elem))
        return node._java_type

    def infer_Tuple_(self, node: Tuple_) -> JavaType:
        node._java_type = JavaType("Object", is_array=True)
        return node._java_type

    def infer_Assign(self, node: Assign) -> JavaType:
        val_type = self.infer(node.value)
        for target in node.targets:
            self._bind_target(target, val_type)
        node._java_type = val_type
        return T_VOID

    def infer_AnnAssign(self, node: AnnAssign) -> JavaType:
        ann = self._resolve_annotation(node.annotation)
        val = self.infer(node.value) if node.value else ann
        result = ann if ann != T_OBJECT else val
        self._bind_target(node.target, result)
        node._java_type = result
        return T_VOID

    def infer_BinaryOp(self, node: BinaryOp) -> JavaType:
        left = self.infer(node.left)
        right = self.infer(node.right)
        if node.op == TokenType.PLUS and (left.name == "String" or right.name == "String"):
            result = T_STRING
        elif node.op in {TokenType.EQ, TokenType.NE, TokenType.LT, TokenType.LE, TokenType.GT, TokenType.GE}:
            result = T_BOOLEAN
        elif is_numeric(left) and is_numeric(right):
            result = unify(left, right)
        else:
            result = T_OBJECT
        node._java_type = result
        return result

    def infer_BoolOp(self, node: BoolOp) -> JavaType:
        for value in node.values:
            self.infer(value)
        node._java_type = T_BOOLEAN
        return T_BOOLEAN

    def infer_Compare(self, node: Compare) -> JavaType:
        self.infer(node.left)
        for comp in node.comparators:
            self.infer(comp)
        node._java_type = T_BOOLEAN
        return T_BOOLEAN

    def infer_Ternary(self, node: Ternary) -> JavaType:
        self.infer(node.condition)
        result = unify(self.infer(node.true_expr), self.infer(node.false_expr))
        node._java_type = result
        return result

    def infer_Subscript(self, node: Subscript) -> JavaType:
        obj = self.infer(node.obj)
        result = obj.generics[1] if obj.name == "HashMap" and len(obj.generics) > 1 else element_type(obj)
        node._java_type = result
        return result

    def infer_Attribute(self, node: Attribute) -> JavaType:
        obj = self.infer(node.obj)
        result = self.class_field_map.get(obj.name, {}).get(node.attr, T_OBJECT)
        node._java_type = result
        return result

    def infer_Call(self, node: Call) -> JavaType:
        for arg in node.args:
            self.infer(arg)
        result = T_OBJECT
        if isinstance(node.func, Identifier):
            name = node.func.name
            result = BUILTIN_RETURN_TYPES.get(name, self.func_return_map.get(name, T_OBJECT))
            if name == "list" and node.args:
                result = T_LIST(element_type(self.infer(node.args[0])))
            elif name == "set" and node.args:
                result = T_SET(element_type(self.infer(node.args[0])))
            elif self.scope.lookup(name):
                result = self.scope.lookup(name) or result
        elif isinstance(node.func, Attribute):
            obj = self.infer(node.func.obj)
            if obj.name == "ArrayList" and node.func.attr in {"append", "extend", "insert", "sort", "reverse"}:
                result = T_VOID
            elif obj.name == "ArrayList" and node.func.attr == "pop":
                result = element_type(obj)
            elif obj.name == "String" and node.func.attr in {"upper", "lower", "strip", "replace"}:
                result = T_STRING
            elif isinstance(node.func.obj, Identifier) and node.func.obj.name == "math":
                result = T_DOUBLE
            elif node.func.attr in self.func_return_map:
                result = self.func_return_map[node.func.attr]
        node._java_type = result
        return result

    def infer_If(self, node: If) -> JavaType:
        self.infer(node.condition)
        for body in [node.body, *(body for _, body in node.elifs), node.else_body or []]:
            self.push_scope()
            for stmt in body:
                self.infer(stmt)
            self.pop_scope()
        return T_VOID

    def infer_While(self, node: While) -> JavaType:
        self.infer(node.condition)
        self.push_scope()
        for stmt in node.body:
            self.infer(stmt)
        self.pop_scope()
        return T_VOID

    def infer_For(self, node: For) -> JavaType:
        iter_type = self.infer(node.iterable)
        elem = T_INT if isinstance(node.iterable, Call) and isinstance(node.iterable.func, Identifier) and node.iterable.func.name == "range" else element_type(iter_type)
        self.push_scope()
        self._bind_target(node.target, elem)
        node._iter_type = iter_type
        node._elem_type = elem
        for stmt in node.body:
            self.infer(stmt)
        self.pop_scope()
        return T_VOID

    def infer_Return(self, node: Return) -> JavaType:
        t = self.infer(node.value) if node.value else T_VOID
        node._java_type = t
        fn = self.scope.function_scope()
        if fn:
            fn.return_types.append(t)
        return t

    def infer_FuncDef(self, node: FuncDef) -> JavaType:
        self.push_scope("function")
        for arg in node.args:
            t = self._resolve_annotation(arg.annotation) if arg.annotation else T_OBJECT
            if arg.name == "self" and self.class_stack:
                t = JavaType(self.class_stack[-1])
            arg._java_type = t
            self.scope.define(arg.name, t)
        for stmt in node.body:
            self.infer(stmt)
        fn_scope = self.scope
        self.pop_scope()
        ret = self._resolve_annotation(node.returns) if node.returns else T_VOID
        for t in fn_scope.return_types:
            ret = t if ret == T_VOID else unify(ret, t)
        node._java_return_type = ret
        self.func_return_map[node.name] = ret
        self.scope.define(node.name, ret)
        return T_VOID

    def infer_ClassDef(self, node: ClassDef) -> JavaType:
        self.class_stack.append(node.name)
        self.class_field_map.setdefault(node.name, {})
        for stmt in node.body:
            self.infer(stmt)
        self.class_stack.pop()
        self.scope.define(node.name, JavaType(node.name))
        return T_VOID

    def _bind_target(self, target, type_: JavaType) -> None:
        if isinstance(target, Identifier):
            target._java_type = type_
            self.scope.define(target.name, type_)
        elif isinstance(target, Attribute):
            target._java_type = type_
            if isinstance(target.obj, Identifier) and target.obj.name == "self" and self.class_stack:
                self.class_field_map.setdefault(self.class_stack[-1], {})[target.attr] = type_
        elif isinstance(target, Tuple_):
            for item in target.elements:
                self._bind_target(item, T_OBJECT)
        else:
            try:
                target._java_type = type_
            except Exception:
                pass

    def _resolve_annotation(self, annotation) -> JavaType:
        if annotation is None:
            return T_OBJECT
        if isinstance(annotation, Identifier):
            return ANNOTATION_MAP.get(annotation.name, JavaType(annotation.name))
        if isinstance(annotation, Subscript) and isinstance(annotation.obj, Identifier):
            name = annotation.obj.name
            if name in {"List", "list"}:
                return T_LIST(box(self._resolve_annotation(annotation.index)))
            if name in {"Set", "set"}:
                return T_SET(box(self._resolve_annotation(annotation.index)))
            if name in {"Dict", "dict"} and isinstance(annotation.index, Tuple_) and len(annotation.index.elements) == 2:
                return T_MAP(box(self._resolve_annotation(annotation.index.elements[0])), box(self._resolve_annotation(annotation.index.elements[1])))
        if isinstance(annotation, NoneNode):
            return T_VOID
        return T_OBJECT

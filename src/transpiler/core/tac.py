from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TACInstruction:
    kind: str
    target: Optional[str] = None
    value: Optional[str] = None
    left: Optional[str] = None
    right: Optional[str] = None
    op: Optional[str] = None
    condition: Optional[str] = None
    name: Optional[str] = None
    args: list[str] = field(default_factory=list)
    object_ref: Optional[str] = None
    member: Optional[str] = None
    java_type: Any = None

    def to_text(self) -> str:
        if self.kind == "assign":
            return f"{self.target} = {self.value}"
        if self.kind == "binop":
            return f"{self.target} = {self.left} {self.op} {self.right}"
        if self.kind == "unop":
            return f"{self.target} = {self.op}{self.value}"
        if self.kind == "call":
            arg_text = ", ".join(self.args)
            if self.target:
                return f"{self.target} = call {self.name}({arg_text})"
            return f"call {self.name}({arg_text})"
        if self.kind == "member_assign":
            return f"{self.object_ref}.{self.member} = {self.value}"
        if self.kind == "print":
            return f"print {', '.join(self.args)}"
        if self.kind == "print_inline":
            return f"print_inline {', '.join(self.args)}"
        if self.kind == "return":
            return "return" if self.value is None else f"return {self.value}"
        if self.kind == "break":
            return "break"
        if self.kind == "continue":
            return "continue"
        if self.kind == "if_begin":
            return f"if {self.condition}"
        if self.kind == "else_begin":
            return "else"
        if self.kind == "if_end":
            return "endif"
        if self.kind == "while_begin":
            return f"while {self.condition}"
        if self.kind == "while_end":
            return "endwhile"
        if self.kind == "nop":
            return "nop"
        return self.kind


@dataclass
class TACFunction:
    name: str
    params: list[str]
    instructions: list[TACInstruction]
    locals: set[str] = field(default_factory=set)
    owner_class: Optional[str] = None
    return_type: Any = None
    param_types: dict[str, Any] = field(default_factory=dict)
    local_types: dict[str, Any] = field(default_factory=dict)

    def to_text(self) -> str:
        prefix = f"{self.owner_class}." if self.owner_class else ""
        lines = [f"function {prefix}{self.name}({', '.join(self.params)})"]
        for inst in self.instructions:
            lines.append(f"  {inst.to_text()}")
        return "\n".join(lines)


@dataclass
class TACClass:
    name: str
    methods: list[TACFunction]

    def to_text(self) -> str:
        lines = [f"class {self.name}"]
        for method in self.methods:
            for line in method.to_text().splitlines():
                lines.append(f"  {line}")
        return "\n".join(lines)


@dataclass
class TACProgram:
    main: TACFunction
    functions: list[TACFunction]
    classes: list[TACClass] = field(default_factory=list)

    def to_text(self) -> str:
        parts = [self.main.to_text()]
        for fn in self.functions:
            parts.append(fn.to_text())
        for cls in self.classes:
            parts.append(cls.to_text())
        return "\n\n".join(parts)

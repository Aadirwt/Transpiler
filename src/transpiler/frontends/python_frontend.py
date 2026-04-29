from __future__ import annotations

from ..core.ast_nodes import Program
from ..core.lexer import Lexer
from ..core.parser import Parser


class PythonFrontend:
    def __init__(self) -> None:
        self.lexer_cls = Lexer
        self.parser_cls = Parser

    def parse(self, source: str) -> Program:
        normalized = source.replace("\r\n", "\n").replace("\r", "\n")
        tokens = self.lexer_cls(normalized).tokenize()
        return self.parser_cls(tokens).parse()

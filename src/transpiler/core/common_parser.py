from __future__ import annotations

from .ast_nodes import Program
from .lexer import Lexer, Token, TokenType
from .parser import Parser


class CommonParser:
    def parse(self, source: str) -> Program:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        return parser.parse()


__all__ = ["CommonParser", "Lexer", "Parser", "Token", "TokenType"]

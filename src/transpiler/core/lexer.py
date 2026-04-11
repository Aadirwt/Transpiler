from __future__ import annotations

from enum import Enum
from typing import Any

from .errors import FrontendError


class TokenType(Enum):
    IF = "if"
    ELSE = "else"
    WHILE = "while"
    FOR = "for"
    FUNCTION = "function"
    RETURN = "return"
    LET = "let"
    PRINT = "print"
    PRINT_INLINE = "print_inline"
    TRUE = "true"
    FALSE = "false"
    BREAK = "break"
    CONTINUE = "continue"
    CLASS = "class"

    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    ASSIGN = "="
    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    AND = "&&"
    OR = "||"
    NOT = "!"
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    LBRACE = "{"
    RBRACE = "}"
    COMMA = ","
    SEMI = ";"
    DOT = "."

    IDENTIFIER = "identifier"
    NUMBER = "number"
    FLOAT = "float"
    STRING = "string"

    EOF = "eof"


class Token:
    def __init__(self, type_: TokenType, value: Any, line: int):
        self.type = type_
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type}, {self.value}, {self.line})"


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.current_char = self.source[0] if source else None

    def advance(self):
        self.pos += 1
        if self.pos >= len(self.source):
            self.current_char = None
        else:
            if self.current_char == "\n":
                self.line += 1
            self.current_char = self.source[self.pos]

    def skip_whitespace(self):
        while self.current_char and self.current_char.isspace():
            self.advance()

    def read_number(self) -> Token:
        result = ""
        while self.current_char and (self.current_char.isdigit() or self.current_char == "."):
            result += self.current_char
            self.advance()
        if "." in result:
            return Token(TokenType.FLOAT, float(result), self.line)
        return Token(TokenType.NUMBER, int(result), self.line)

    def read_string(self) -> Token:
        quote = self.current_char
        self.advance()
        result = ""
        while self.current_char and self.current_char != quote:
            if self.current_char == "\\":
                self.advance()
                if self.current_char == "n":
                    result += "\n"
                elif self.current_char == "t":
                    result += "\t"
                elif self.current_char == '"':
                    result += '"'
                elif self.current_char == "'":
                    result += "'"
                elif self.current_char == "\\":
                    result += "\\"
                else:
                    result += self.current_char
            else:
                result += self.current_char
            self.advance()
        if self.current_char == quote:
            self.advance()
        return Token(TokenType.STRING, result, self.line)

    def read_identifier_or_keyword(self) -> Token:
        result = ""
        while self.current_char and (self.current_char.isalnum() or self.current_char == "_"):
            result += self.current_char
            self.advance()
        for token_type in TokenType:
            if token_type.value == result:
                return Token(token_type, result, self.line)
        return Token(TokenType.IDENTIFIER, result, self.line)

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self.current_char is not None:
            if self.current_char.isspace():
                self.skip_whitespace()
                continue
            if self.current_char.isdigit():
                tokens.append(self.read_number())
            elif self.current_char in ('"', "'"):
                tokens.append(self.read_string())
            elif self.current_char.isalpha() or self.current_char == "_":
                tokens.append(self.read_identifier_or_keyword())
            elif self.current_char == "+":
                tokens.append(Token(TokenType.PLUS, "+", self.line))
                self.advance()
            elif self.current_char == "-":
                tokens.append(Token(TokenType.MINUS, "-", self.line))
                self.advance()
            elif self.current_char == "*":
                tokens.append(Token(TokenType.STAR, "*", self.line))
                self.advance()
            elif self.current_char == "/":
                self.advance()
                if self.current_char == "/":
                    while self.current_char and self.current_char != "\n":
                        self.advance()
                elif self.current_char == "*":
                    self.advance()
                    while self.current_char:
                        if self.current_char == "*":
                            self.advance()
                            if self.current_char == "/":
                                self.advance()
                                break
                        else:
                            self.advance()
                else:
                    tokens.append(Token(TokenType.SLASH, "/", self.line))
            elif self.current_char == "=":
                self.advance()
                if self.current_char == "=":
                    tokens.append(Token(TokenType.EQ, "==", self.line))
                    self.advance()
                else:
                    tokens.append(Token(TokenType.ASSIGN, "=", self.line))
            elif self.current_char == "!":
                self.advance()
                if self.current_char == "=":
                    tokens.append(Token(TokenType.NE, "!=", self.line))
                    self.advance()
                else:
                    tokens.append(Token(TokenType.NOT, "!", self.line))
            elif self.current_char == "<":
                self.advance()
                if self.current_char == "=":
                    tokens.append(Token(TokenType.LE, "<=", self.line))
                    self.advance()
                else:
                    tokens.append(Token(TokenType.LT, "<", self.line))
            elif self.current_char == ">":
                self.advance()
                if self.current_char == "=":
                    tokens.append(Token(TokenType.GE, ">=", self.line))
                    self.advance()
                else:
                    tokens.append(Token(TokenType.GT, ">", self.line))
            elif self.current_char == "&":
                self.advance()
                if self.current_char == "&":
                    tokens.append(Token(TokenType.AND, "&&", self.line))
                    self.advance()
                else:
                    raise FrontendError(f"Unexpected character '&' at line {self.line}")
            elif self.current_char == "|":
                self.advance()
                if self.current_char == "|":
                    tokens.append(Token(TokenType.OR, "||", self.line))
                    self.advance()
                else:
                    raise FrontendError(f"Unexpected character '|' at line {self.line}")
            elif self.current_char == "(":
                tokens.append(Token(TokenType.LPAREN, "(", self.line))
                self.advance()
            elif self.current_char == ")":
                tokens.append(Token(TokenType.RPAREN, ")", self.line))
                self.advance()
            elif self.current_char == "[":
                tokens.append(Token(TokenType.LBRACKET, "[", self.line))
                self.advance()
            elif self.current_char == "]":
                tokens.append(Token(TokenType.RBRACKET, "]", self.line))
                self.advance()
            elif self.current_char == "{":
                tokens.append(Token(TokenType.LBRACE, "{", self.line))
                self.advance()
            elif self.current_char == "}":
                tokens.append(Token(TokenType.RBRACE, "}", self.line))
                self.advance()
            elif self.current_char == ",":
                tokens.append(Token(TokenType.COMMA, ",", self.line))
                self.advance()
            elif self.current_char == ";":
                tokens.append(Token(TokenType.SEMI, ";", self.line))
                self.advance()
            elif self.current_char == ".":
                tokens.append(Token(TokenType.DOT, ".", self.line))
                self.advance()
            else:
                raise FrontendError(f"Illegal character '{self.current_char}' at line {self.line}")
        tokens.append(Token(TokenType.EOF, None, self.line))
        return tokens

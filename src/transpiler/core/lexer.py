from __future__ import annotations

from enum import Enum
from typing import Any

from .errors import FrontendError


class TokenType(Enum):
    IF = "if"
    ELIF = "elif"
    ELSE = "else"
    WHILE = "while"
    FOR = "for"
    IN = "in"
    RANGE = "range"
    FUNCTION = "def"
    RETURN = "return"
    PRINT = "print"
    TRUE = "True"   
    FALSE = "False"
    BREAK = "break"
    CONTINUE = "continue"
    CLASS = "class"
    AND = "and"
    OR = "or"
    NOT = "not"

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
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    COMMA = ","
    DOT = "."
    COLON = ":"

    IDENTIFIER = "identifier"
    NUMBER = "number"
    FLOAT = "float"
    STRING = "string"

    NEWLINE = "newline"
    INDENT = "indent"
    DEDENT = "dedent"
    EOF = "eof"


_KEYWORDS = {
    token_type.value: token_type
    for token_type in (
        TokenType.IF,
        TokenType.ELIF,
        TokenType.ELSE,
        TokenType.WHILE,
        TokenType.FOR,
        TokenType.IN,
        TokenType.RANGE,
        TokenType.FUNCTION,
        TokenType.RETURN,
        TokenType.PRINT,
        TokenType.TRUE,
        TokenType.FALSE,
        TokenType.BREAK,
        TokenType.CONTINUE,
        TokenType.CLASS,
        TokenType.AND,
        TokenType.OR,
        TokenType.NOT,
    )
}


class Token:
    def __init__(self, type_: TokenType, value: Any, line: int):
        self.type = type_
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type}, {self.value}, {self.line})"


class Lexer:
    def __init__(self, source: str):
        self.source = source.replace("\r\n", "\n").replace("\r", "\n")

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        indent_stack = [0]

        for line_no, raw_line in enumerate(self.source.split("\n"), start=1):
            expanded = raw_line.replace("\t", "    ")
            uncommented = self._strip_comment(expanded).rstrip()
            if not uncommented.strip():
                continue

            indent = len(uncommented) - len(uncommented.lstrip(" "))
            if indent > indent_stack[-1]:
                indent_stack.append(indent)
                tokens.append(Token(TokenType.INDENT, None, line_no))
            else:
                while indent < indent_stack[-1]:
                    indent_stack.pop()
                    tokens.append(Token(TokenType.DEDENT, None, line_no))
                if indent != indent_stack[-1]:
                    raise FrontendError(f"Inconsistent indentation at line {line_no}.")

            content = uncommented.lstrip(" ")
            tokens.extend(self._tokenize_line(content, line_no))
            tokens.append(Token(TokenType.NEWLINE, None, line_no))

        while len(indent_stack) > 1:
            indent_stack.pop()
            tokens.append(Token(TokenType.DEDENT, None, 0))

        tokens.append(Token(TokenType.EOF, None, 0))
        return tokens

    def _strip_comment(self, line: str) -> str:
        quote: str | None = None
        escaped = False
        chars: list[str] = []

        for ch in line:
            if quote is not None:
                chars.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == quote:
                    quote = None
                continue

            if ch in {'"', "'"}:
                quote = ch
                chars.append(ch)
                continue
            if ch == "#":
                break
            chars.append(ch)

        return "".join(chars)

    def _tokenize_line(self, line: str, line_no: int) -> list[Token]:
        tokens: list[Token] = []
        pos = 0

        while pos < len(line):
            ch = line[pos]
            if ch.isspace():
                pos += 1
                continue

            if ch.isdigit():
                token, pos = self._read_number(line, pos, line_no)
                tokens.append(token)                
                continue

            if ch in {'"', "'"}:
                token, pos = self._read_string(line, pos, line_no)
                tokens.append(token)
                continue

            if ch.isalpha() or ch == "_":
                token, pos = self._read_identifier(line, pos, line_no)
                tokens.append(token)
                continue

            if pos + 1 < len(line):
                pair = line[pos : pos + 2]
                if pair == "==":
                    tokens.append(Token(TokenType.EQ, pair, line_no))
                    pos += 2
                    continue
                if pair == "!=":
                    tokens.append(Token(TokenType.NE, pair, line_no))
                    pos += 2
                    continue
                if pair == "<=":
                    tokens.append(Token(TokenType.LE, pair, line_no))
                    pos += 2
                    continue
                if pair == ">=":
                    tokens.append(Token(TokenType.GE, pair, line_no))
                    pos += 2
                    continue

            single_tokens = {
                "+": TokenType.PLUS,
                "-": TokenType.MINUS,
                "*": TokenType.STAR,
                "/": TokenType.SLASH,
                "=": TokenType.ASSIGN,
                "<": TokenType.LT,
                ">": TokenType.GT,
                "(": TokenType.LPAREN,
                ")": TokenType.RPAREN,
                "[": TokenType.LBRACKET,
                "]": TokenType.RBRACKET,
                ",": TokenType.COMMA,
                ".": TokenType.DOT,
                ":": TokenType.COLON,
            }
            token_type = single_tokens.get(ch)
            if token_type is None:
                raise FrontendError(f"Illegal character '{ch}' at line {line_no}")
            tokens.append(Token(token_type, ch, line_no))
            pos += 1

        return tokens

    def _read_number(self, line: str, pos: int, line_no: int) -> tuple[Token, int]:
        start = pos
        has_dot = False
        while pos < len(line):
            ch = line[pos]
            if ch.isdigit():
                pos += 1
                continue
            if ch == "." and not has_dot and pos + 1 < len(line) and line[pos + 1].isdigit():
                has_dot = True
                pos += 1
                continue
            break

        text = line[start:pos]
        if has_dot:
            return Token(TokenType.FLOAT, float(text), line_no), pos
        return Token(TokenType.NUMBER, int(text), line_no), pos

    def _read_string(self, line: str, pos: int, line_no: int) -> tuple[Token, int]:
        quote = line[pos]
        pos += 1
        result = ""

        while pos < len(line):
            ch = line[pos]
            if ch == "\\":
                pos += 1
                if pos >= len(line):
                    break
                escaped = line[pos]
                if escaped == "n":
                    result += "\n"
                elif escaped == "t":
                    result += "\t"
                else:
                    result += escaped
                pos += 1
                continue
            if ch == quote:
                pos += 1
                return Token(TokenType.STRING, result, line_no), pos
            result += ch
            pos += 1

        raise FrontendError(f"Unterminated string at line {line_no}")

    def _read_identifier(self, line: str, pos: int, line_no: int) -> tuple[Token, int]:
        start = pos
        while pos < len(line) and (line[pos].isalnum() or line[pos] == "_"):
            pos += 1
        text = line[start:pos]
        token_type = _KEYWORDS.get(text, TokenType.IDENTIFIER)
        if token_type == TokenType.AND:
            return Token(token_type, "&&", line_no), pos
        if token_type == TokenType.OR:
            return Token(token_type, "||", line_no), pos
        if token_type == TokenType.NOT:
            return Token(token_type, "!", line_no), pos
        return Token(token_type, text, line_no), pos

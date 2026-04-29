from __future__ import annotations

from enum import Enum
from typing import Any

from .errors import FrontendError


class TokenType(Enum):
    DEF = "def"
    CLASS = "class"
    RETURN = "return"
    IF = "if"
    ELIF = "elif"
    ELSE = "else"
    WHILE = "while"
    FOR = "for"
    IN = "in"
    BREAK = "break"
    CONTINUE = "continue"
    PASS = "pass"
    IMPORT = "import"
    FROM = "from"
    AS = "as"
    TRY = "try"
    EXCEPT = "except"
    FINALLY = "finally"
    RAISE = "raise"
    WITH = "with"
    YIELD = "yield"
    LAMBDA = "lambda"
    GLOBAL = "global"
    NONLOCAL = "nonlocal"
    DEL = "del"
    ASSERT = "assert"
    AND = "and"
    OR = "or"
    NOT = "not"
    IS = "is"
    NONE = "None"
    TRUE = "True"
    FALSE = "False"

    INDENT = "INDENT"
    DEDENT = "DEDENT"
    NEWLINE = "NEWLINE"
    EOF = "eof"

    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    FLOOR_DIV = "//"
    POWER = "**"
    MODULO = "%"
    PLUS_ASSIGN = "+="
    MINUS_ASSIGN = "-="
    STAR_ASSIGN = "*="
    SLASH_ASSIGN = "/="
    FLOOR_DIV_ASSIGN = "//="
    POWER_ASSIGN = "**="
    MODULO_ASSIGN = "%="
    AND_ASSIGN = "&="
    OR_ASSIGN = "|="
    XOR_ASSIGN = "^="
    LSHIFT_ASSIGN = "<<="
    RSHIFT_ASSIGN = ">>="

    ASSIGN = "="
    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    WALRUS = ":="

    BIT_AND = "&"
    BIT_OR = "|"
    BIT_XOR = "^"
    BIT_NOT = "~"
    LSHIFT = "<<"
    RSHIFT = ">>"

    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    LBRACE = "{"
    RBRACE = "}"
    COLON = ":"
    COMMA = ","
    DOT = "."
    SEMICOLON = ";"
    AT = "@"
    ARROW = "->"
    ELLIPSIS = "..."

    IDENTIFIER = "identifier"
    NUMBER = "number"
    FLOAT = "float"
    STRING = "string"
    FSTRING = "fstring"


class Token:
    def __init__(self, type_: TokenType, value: Any, line: int):
        self.type = type_
        self.value = value
        self.line = line

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r}, line={self.line})"


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.current_char = self.source[0] if source else None
        self.indent_stack = [0]
        self.at_line_start = True
        self.paren_depth = 0

    def peek(self, k: int = 1) -> str | None:
        pos = self.pos + k
        return self.source[pos] if pos < len(self.source) else None

    def advance(self) -> None:
        if self.current_char == "\n":
            self.line += 1
        self.pos += 1
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None

    def peek_str(self, text: str) -> bool:
        return self.source[self.pos:self.pos + len(text)] == text

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self.current_char is not None:
            if self.at_line_start and self.paren_depth == 0:
                self._handle_indentation(tokens)
                self.at_line_start = False
            if self.current_char is None:
                break
            if self.current_char in (" ", "\t"):
                self._skip_whitespace()
                continue
            if self.current_char == "\n":
                if self.paren_depth == 0:
                    tokens.append(Token(TokenType.NEWLINE, None, self.line))
                self.advance()
                self.at_line_start = True
                continue
            if self.current_char == "\\" and self.peek() == "\n":
                self.advance()
                self.advance()
                continue
            if self.current_char == "#":
                while self.current_char and self.current_char != "\n":
                    self.advance()
                continue
            if self.peek_str("..."):
                tokens.append(Token(TokenType.ELLIPSIS, "...", self.line))
                self.advance(); self.advance(); self.advance()
                continue
            if self.current_char.isdigit():
                tokens.append(self._read_number())
                continue
            if self.current_char in ("'", '"'):
                tokens.append(self._read_string())
                continue
            if self.current_char.isalpha() or self.current_char == "_":
                tokens.append(self._read_identifier_or_keyword())
                continue
            token = self._read_operator_or_symbol()
            if token is None:
                raise FrontendError(f"Illegal character '{self.current_char}' at line {self.line}")
            tokens.append(token)

        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            tokens.append(Token(TokenType.DEDENT, None, self.line))
        tokens.append(Token(TokenType.EOF, None, self.line))
        return tokens

    def _skip_whitespace(self) -> None:
        while self.current_char in (" ", "\t"):
            self.advance()

    def _handle_indentation(self, tokens: list[Token]) -> None:
        count = 0
        while self.current_char == " ":
            count += 1
            self.advance()
        while self.current_char == "\t":
            count += 4
            self.advance()
        if self.current_char in ("\n", "#", None):
            return
        prev = self.indent_stack[-1]
        if count > prev:
            self.indent_stack.append(count)
            tokens.append(Token(TokenType.INDENT, count, self.line))
        elif count < prev:
            while self.indent_stack[-1] > count:
                self.indent_stack.pop()
                tokens.append(Token(TokenType.DEDENT, None, self.line))
            if self.indent_stack[-1] != count:
                raise FrontendError(f"Indentation error at line {self.line}")

    def _read_number(self) -> Token:
        result = ""
        is_float = False
        if self.current_char == "0" and self.peek() in ("x", "X", "b", "B", "o", "O"):
            prefix = self.peek()
            result += self.current_char
            self.advance()
            result += self.current_char
            self.advance()
            valid = {
                "x": "0123456789abcdefABCDEF_",
                "X": "0123456789abcdefABCDEF_",
                "b": "01_",
                "B": "01_",
                "o": "01234567_",
                "O": "01234567_",
            }[prefix]
            while self.current_char and self.current_char in valid:
                if self.current_char != "_":
                    result += self.current_char
                self.advance()
            return Token(TokenType.NUMBER, int(result, 0), self.line)
        while self.current_char and (self.current_char.isdigit() or self.current_char == "_"):
            if self.current_char != "_":
                result += self.current_char
            self.advance()
        if self.current_char == "." and self.peek() and self.peek().isdigit():
            is_float = True
            result += "."
            self.advance()
            while self.current_char and (self.current_char.isdigit() or self.current_char == "_"):
                if self.current_char != "_":
                    result += self.current_char
                self.advance()
        if self.current_char in ("e", "E"):
            is_float = True
            result += self.current_char
            self.advance()
            if self.current_char in ("+", "-"):
                result += self.current_char
                self.advance()
            while self.current_char and self.current_char.isdigit():
                result += self.current_char
                self.advance()
        return Token(TokenType.FLOAT if is_float else TokenType.NUMBER, float(result) if is_float else int(result), self.line)

    def _read_string(self, prefix: str = "") -> Token:
        is_fstring = "f" in prefix.lower()
        is_raw = "r" in prefix.lower()
        quote = self.current_char
        if self.peek() == quote and self.peek(2) == quote:
            self.advance(); self.advance(); self.advance()
            result = ""
            while self.current_char:
                if self.current_char == quote and self.peek() == quote and self.peek(2) == quote:
                    self.advance(); self.advance(); self.advance()
                    return Token(TokenType.FSTRING if is_fstring else TokenType.STRING, result, self.line)
                result += self.current_char
                self.advance()
            raise FrontendError(f"Unterminated triple-quoted string at line {self.line}")
        self.advance()
        result = ""
        while self.current_char and self.current_char != quote and self.current_char != "\n":
            if self.current_char == "\\" and not is_raw:
                self.advance()
                escapes = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "'": "'", "\\": "\\"}
                result += escapes.get(self.current_char, "\\" + (self.current_char or ""))
            else:
                result += self.current_char
            self.advance()
        if self.current_char != quote:
            raise FrontendError(f"Unterminated string at line {self.line}")
        self.advance()
        return Token(TokenType.FSTRING if is_fstring else TokenType.STRING, result, self.line)

    def _read_identifier_or_keyword(self) -> Token:
        result = ""
        while self.current_char and (self.current_char.isalnum() or self.current_char == "_"):
            result += self.current_char
            self.advance()
        if result.lower() in ("f", "r", "b", "rb", "br", "fr", "rf") and self.current_char in ("'", '"'):
            return self._read_string(prefix=result)
        for token_type in TokenType:
            if token_type.value == result:
                return Token(token_type, result, self.line)
        return Token(TokenType.IDENTIFIER, result, self.line)

    def _read_operator_or_symbol(self) -> Token | None:
        line = self.line
        triples = {"**=": TokenType.POWER_ASSIGN, "//=": TokenType.FLOOR_DIV_ASSIGN, "<<=": TokenType.LSHIFT_ASSIGN, ">>=": TokenType.RSHIFT_ASSIGN}
        for text, typ in triples.items():
            if self.peek_str(text):
                for _ in text:
                    self.advance()
                return Token(typ, text, line)
        doubles = {
            "->": TokenType.ARROW, "+=": TokenType.PLUS_ASSIGN, "-=": TokenType.MINUS_ASSIGN,
            "*=": TokenType.STAR_ASSIGN, "/=": TokenType.SLASH_ASSIGN, "%=": TokenType.MODULO_ASSIGN,
            "&=": TokenType.AND_ASSIGN, "|=": TokenType.OR_ASSIGN, "^=": TokenType.XOR_ASSIGN,
            "**": TokenType.POWER, "//": TokenType.FLOOR_DIV, "<<": TokenType.LSHIFT, ">>": TokenType.RSHIFT,
            "==": TokenType.EQ, "!=": TokenType.NE, "<=": TokenType.LE, ">=": TokenType.GE, ":=": TokenType.WALRUS,
        }
        for text, typ in doubles.items():
            if self.peek_str(text):
                self.advance(); self.advance()
                return Token(typ, text, line)
        single = {
            "+": TokenType.PLUS, "-": TokenType.MINUS, "*": TokenType.STAR, "/": TokenType.SLASH,
            "%": TokenType.MODULO, "&": TokenType.BIT_AND, "|": TokenType.BIT_OR,
            "^": TokenType.BIT_XOR, "~": TokenType.BIT_NOT, "<": TokenType.LT,
            ">": TokenType.GT, "=": TokenType.ASSIGN, "(": TokenType.LPAREN,
            ")": TokenType.RPAREN, "[": TokenType.LBRACKET, "]": TokenType.RBRACKET,
            "{": TokenType.LBRACE, "}": TokenType.RBRACE, ":": TokenType.COLON,
            ",": TokenType.COMMA, ".": TokenType.DOT, ";": TokenType.SEMICOLON, "@": TokenType.AT,
        }
        typ = single.get(self.current_char)
        if typ is None:
            return None
        if typ in (TokenType.LPAREN, TokenType.LBRACKET, TokenType.LBRACE):
            self.paren_depth += 1
        elif typ in (TokenType.RPAREN, TokenType.RBRACKET, TokenType.RBRACE):
            self.paren_depth -= 1
        value = self.current_char
        self.advance()
        return Token(typ, value, line)

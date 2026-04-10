from __future__ import annotations

import ast as py_ast
import re
from enum import Enum
from typing import Any, List, Optional

from .ast_nodes import (
    Assign,
    Binary,
    Break,
    Call,
    ClassDef,
    Continue,
    ExprStmt,
    For,
    FunctionDef,
    If,
    LetDecl,
    Literal,
    ListLiteral,
    Member,
    MemberAssign,
    Print,
    Program,
    Return,
    Unary,
    Variable,
    While,
)
from .errors import FrontendError


class TokenType(Enum):
    # Keywords
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

    # Symbols
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

    # Literals and identifiers
    IDENTIFIER = "identifier"
    NUMBER = "number"
    FLOAT = "float"
    STRING = "string"

    # Special
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
            if self.current_char == '\n':
                self.line += 1
            self.current_char = self.source[self.pos]

    def skip_whitespace(self):
        while self.current_char and self.current_char.isspace():
            self.advance()

    def read_number(self) -> Token:
        result = ''
        while self.current_char and (self.current_char.isdigit() or self.current_char == '.'):
            result += self.current_char
            self.advance()
        if '.' in result:
            return Token(TokenType.FLOAT, float(result), self.line)
        else:
            return Token(TokenType.NUMBER, int(result), self.line)

    def read_string(self) -> Token:
        quote = self.current_char
        self.advance()
        result = ''
        while self.current_char and self.current_char != quote:
            if self.current_char == '\\':
                self.advance()
                if self.current_char == 'n':
                    result += '\n'
                elif self.current_char == 't':
                    result += '\t'
                elif self.current_char == '"':
                    result += '"'
                elif self.current_char == "'":
                    result += "'"
                elif self.current_char == '\\':
                    result += '\\'
                else:
                    result += self.current_char
            else:
                result += self.current_char
            self.advance()
        if self.current_char == quote:
            self.advance()
        return Token(TokenType.STRING, result, self.line)

    def read_identifier_or_keyword(self) -> Token:
        result = ''
        while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
            result += self.current_char
            self.advance()
        # Check if it's a keyword
        for token_type in TokenType:
            if token_type.value == result:
                return Token(token_type, result, self.line)
        return Token(TokenType.IDENTIFIER, result, self.line)

    def tokenize(self) -> List[Token]:
        tokens = []
        while self.current_char is not None:
            if self.current_char.isspace():
                self.skip_whitespace()
                continue
            elif self.current_char.isdigit():
                tokens.append(self.read_number())
            elif self.current_char in ('"', "'"):
                tokens.append(self.read_string())
            elif self.current_char.isalpha() or self.current_char == '_':
                tokens.append(self.read_identifier_or_keyword())
            elif self.current_char == '+':
                tokens.append(Token(TokenType.PLUS, '+', self.line))
                self.advance()
            elif self.current_char == '-':
                tokens.append(Token(TokenType.MINUS, '-', self.line))
                self.advance()
            elif self.current_char == '*':
                tokens.append(Token(TokenType.STAR, '*', self.line))
                self.advance()
            elif self.current_char == '/':
                self.advance()
                if self.current_char == '/':
                    # Line comment
                    while self.current_char and self.current_char != '\n':
                        self.advance()
                elif self.current_char == '*':
                    # Block comment
                    self.advance()
                    while self.current_char:
                        if self.current_char == '*':
                            self.advance()
                            if self.current_char == '/':
                                self.advance()
                                break
                        else:
                            self.advance()
                else:
                    tokens.append(Token(TokenType.SLASH, '/', self.line))
            elif self.current_char == '=':
                self.advance()
                if self.current_char == '=':
                    tokens.append(Token(TokenType.EQ, '==', self.line))
                    self.advance()
                else:
                    tokens.append(Token(TokenType.ASSIGN, '=', self.line))
            elif self.current_char == '!':
                self.advance()
                if self.current_char == '=':
                    tokens.append(Token(TokenType.NE, '!=', self.line))
                    self.advance()
                else:
                    tokens.append(TokenType.NOT, '!', self.line)
            elif self.current_char == '<':
                self.advance()
                if self.current_char == '=':
                    tokens.append(Token(TokenType.LE, '<=', self.line))
                    self.advance()
                else:
                    tokens.append(Token(TokenType.LT, '<', self.line))
            elif self.current_char == '>':
                self.advance()
                if self.current_char == '=':
                    tokens.append(Token(TokenType.GE, '>=', self.line))
                    self.advance()
                else:
                    tokens.append(Token(TokenType.GT, '>', self.line))
            elif self.current_char == '&':
                self.advance()
                if self.current_char == '&':
                    tokens.append(Token(TokenType.AND, '&&', self.line))
                    self.advance()
                else:
                    raise FrontendError(f"Unexpected character '&' at line {self.line}")
            elif self.current_char == '|':
                self.advance()
                if self.current_char == '|':
                    tokens.append(Token(TokenType.OR, '||', self.line))
                    self.advance()
                else:
                    raise FrontendError(f"Unexpected character '|' at line {self.line}")
            elif self.current_char == '(':
                tokens.append(Token(TokenType.LPAREN, '(', self.line))
                self.advance()
            elif self.current_char == ')':
                tokens.append(Token(TokenType.RPAREN, ')', self.line))
                self.advance()
            elif self.current_char == '[':
                tokens.append(Token(TokenType.LBRACKET, '[', self.line))
                self.advance()
            elif self.current_char == ']':
                tokens.append(Token(TokenType.RBRACKET, ']', self.line))
                self.advance()
            elif self.current_char == '{':
                tokens.append(Token(TokenType.LBRACE, '{', self.line))
                self.advance()
            elif self.current_char == '}':
                tokens.append(Token(TokenType.RBRACE, '}', self.line))
                self.advance()
            elif self.current_char == ',':
                tokens.append(Token(TokenType.COMMA, ',', self.line))
                self.advance()
            elif self.current_char == ';':
                tokens.append(Token(TokenType.SEMI, ';', self.line))
                self.advance()
            elif self.current_char == '.':
                tokens.append(Token(TokenType.DOT, '.', self.line))
                self.advance()
            else:
                raise FrontendError(f"Illegal character '{self.current_char}' at line {self.line}")
        tokens.append(Token(TokenType.EOF, None, self.line))
        return tokens


class CommonParser:
    def __init__(self) -> None:
        pass

    def parse(self, source: str) -> Program:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        return parser.parse()
class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.current_token = self.tokens[0] if tokens else None

    def advance(self):
        self.pos += 1
        if self.pos < len(self.tokens):
            self.current_token = self.tokens[self.pos]
        else:
            self.current_token = None

    def peek(self, offset: int = 1) -> Optional[Token]:
        peek_pos = self.pos + offset
        if peek_pos < len(self.tokens):
            return self.tokens[peek_pos]
        return None

    def expect(self, token_type: TokenType) -> Token:
        if self.current_token and self.current_token.type == token_type:
            token = self.current_token
            self.advance()
            return token
        else:
            expected = token_type.value
            actual = self.current_token.value if self.current_token else "EOF"
            raise FrontendError(f"Expected {expected}, got {actual} at line {self.current_token.line if self.current_token else 'EOF'}")

    def parse(self) -> Program:
        statements = self.parse_statement_list_opt()
        self.expect(TokenType.EOF)
        return Program(statements)

    def parse_statement_list_opt(self) -> List[Any]:
        statements = []
        while self.current_token and self.current_token.type not in (TokenType.RBRACE, TokenType.EOF):
            stmt = self.parse_statement()
            statements.append(stmt)
        return statements

    def parse_statement(self) -> Any:
        if self.current_token.type == TokenType.LET:
            return self.parse_let_statement()
        elif self.current_token.type in (TokenType.PRINT, TokenType.PRINT_INLINE):
            return self.parse_print_statement()
        elif self.current_token.type == TokenType.IF:
            return self.parse_if_statement()
        elif self.current_token.type == TokenType.WHILE:
            return self.parse_while_statement()
        elif self.current_token.type == TokenType.FOR:
            return self.parse_for_statement()
        elif self.current_token.type == TokenType.FUNCTION:
            return self.parse_function_statement()
        elif self.current_token.type == TokenType.CLASS:
            return self.parse_class_statement()
        elif self.current_token.type == TokenType.RETURN:
            return self.parse_return_statement()
        elif self.current_token.type == TokenType.BREAK:
            return self.parse_break_statement()
        elif self.current_token.type == TokenType.CONTINUE:
            return self.parse_continue_statement()
        else:
            # Try assignment or expression
            saved_pos = self.pos
            saved_current = self.current_token
            try:
                lvalue = self.parse_lvalue()
                if self.current_token and self.current_token.type == TokenType.ASSIGN:
                    self.advance()
                    value = self.parse_expression()
                    self.expect(TokenType.SEMI)
                    return Assign(name=lvalue, value=value) if isinstance(lvalue, str) else MemberAssign(target=lvalue, value=value)
                else:
                    # Not assignment, backtrack
                    self.pos = saved_pos
                    self.current_token = saved_current
            except:
                self.pos = saved_pos
                self.current_token = saved_current
            # Expression statement
            expr = self.parse_expression()
            self.expect(TokenType.SEMI)
            return ExprStmt(expr=expr)

    def parse_let_statement(self) -> LetDecl:
        self.expect(TokenType.LET)
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.ASSIGN)
        value = self.parse_expression()
        self.expect(TokenType.SEMI)
        return LetDecl(name=name, value=value)

    def parse_lvalue(self) -> Any:
        name = self.expect(TokenType.IDENTIFIER).value
        lvalue = name
        while self.current_token and self.current_token.type == TokenType.DOT:
            self.advance()
            member = self.expect(TokenType.IDENTIFIER).value
            lvalue = Member(Variable(lvalue) if isinstance(lvalue, str) else lvalue, member)
        return lvalue

    def parse_print_statement(self) -> Print:
        is_inline = self.current_token.type == TokenType.PRINT_INLINE
        self.advance()
        if self.current_token and self.current_token.type == TokenType.LPAREN:
            self.advance()
            args = self.parse_argument_list_opt()
            self.expect(TokenType.RPAREN)
        else:
            # PRINT expression
            expr = self.parse_expression()
            args = [expr]
        self.expect(TokenType.SEMI)
        return Print(values=args, newline=not is_inline)

    def parse_if_statement(self) -> If:
        self.expect(TokenType.IF)
        self.expect(TokenType.LPAREN)
        condition = self.parse_expression()
        self.expect(TokenType.RPAREN)
        then_body = self.parse_block()
        else_body = self.parse_else_part()
        return If(condition=condition, then_body=then_body, else_body=else_body)

    def parse_else_part(self) -> List[Any]:
        if self.current_token and self.current_token.type == TokenType.ELSE:
            self.advance()
            if self.current_token and self.current_token.type == TokenType.IF:
                return [self.parse_if_statement()]
            else:
                return self.parse_block()
        return []

    def parse_while_statement(self) -> While:
        self.expect(TokenType.WHILE)
        self.expect(TokenType.LPAREN)
        condition = self.parse_expression()
        self.expect(TokenType.RPAREN)
        body = self.parse_block()
        return While(condition=condition, body=body)

    def parse_for_statement(self) -> For:
        self.expect(TokenType.FOR)
        self.expect(TokenType.LPAREN)
        init = self.parse_for_init()
        self.expect(TokenType.SEMI)
        condition = self.parse_expression_opt()
        self.expect(TokenType.SEMI)
        increment = self.parse_for_step()
        self.expect(TokenType.RPAREN)
        body = self.parse_block()
        return For(init=init, condition=condition, increment=increment, body=body)

    def parse_for_init(self) -> Optional[Any]:
        if self.current_token.type == TokenType.LET:
            return self.parse_let_core()
        elif self.current_token.type == TokenType.IDENTIFIER and self.peek().type == TokenType.ASSIGN:
            return self.parse_assign_core()
        return None

    def parse_let_core(self) -> LetDecl:
        self.expect(TokenType.LET)
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.ASSIGN)
        value = self.parse_expression()
        return LetDecl(name=name, value=value)

    def parse_assign_core(self) -> Any:
        lvalue = self.parse_lvalue()
        self.expect(TokenType.ASSIGN)
        value = self.parse_expression()
        if isinstance(lvalue, str):
            return Assign(name=lvalue, value=value)
        else:
            return MemberAssign(target=lvalue, value=value)

    def parse_for_step(self) -> Optional[Any]:
        if self.current_token:
            saved_pos = self.pos
            saved_current = self.current_token
            try:
                lvalue = self.parse_lvalue()
                if self.current_token and self.current_token.type == TokenType.ASSIGN:
                    self.advance()
                    value = self.parse_expression()
                    return Assign(name=lvalue, value=value) if isinstance(lvalue, str) else MemberAssign(target=lvalue, value=value)
                else:
                    self.pos = saved_pos
                    self.current_token = saved_current
            except:
                self.pos = saved_pos
                self.current_token = saved_current
            # Try expression
            expr = self.parse_expression()
            return ExprStmt(expr)
        return None

    def parse_function_statement(self) -> FunctionDef:
        self.expect(TokenType.FUNCTION)
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.LPAREN)
        params = self.parse_param_list_opt()
        self.expect(TokenType.RPAREN)
        body = self.parse_block()
        return FunctionDef(name=name, params=params, body=body)

    def parse_class_statement(self) -> ClassDef:
        self.expect(TokenType.CLASS)
        name = self.expect(TokenType.IDENTIFIER).value
        methods = self.parse_class_block()
        return ClassDef(name=name, methods=methods)

    def parse_class_block(self) -> List[FunctionDef]:
        self.expect(TokenType.LBRACE)
        methods = []
        while self.current_token and self.current_token.type != TokenType.RBRACE:
            method = self.parse_class_member()
            methods.append(method)
        self.expect(TokenType.RBRACE)
        return methods

    def parse_class_member(self) -> FunctionDef:
        # method_statement: IDENTIFIER LPAREN param_list_opt RPAREN block
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.LPAREN)
        params = self.parse_param_list_opt()
        self.expect(TokenType.RPAREN)
        body = self.parse_block()
        return FunctionDef(name=name, params=params, body=body)

    def parse_param_list_opt(self) -> List[str]:
        params = []
        if self.current_token and self.current_token.type == TokenType.IDENTIFIER:
            params.append(self.expect(TokenType.IDENTIFIER).value)
            while self.current_token and self.current_token.type == TokenType.COMMA:
                self.advance()
                params.append(self.expect(TokenType.IDENTIFIER).value)
        return params

    def parse_return_statement(self) -> Return:
        self.expect(TokenType.RETURN)
        value = self.parse_expression_opt()
        self.expect(TokenType.SEMI)
        return Return(value=value)

    def parse_break_statement(self) -> Break:
        self.expect(TokenType.BREAK)
        self.expect(TokenType.SEMI)
        return Break()

    def parse_continue_statement(self) -> Continue:
        self.expect(TokenType.CONTINUE)
        self.expect(TokenType.SEMI)
        return Continue()

    def parse_expr_statement(self) -> ExprStmt:
        expr = self.parse_expression()
        self.expect(TokenType.SEMI)
        return ExprStmt(expr=expr)

    def parse_block(self) -> List[Any]:
        self.expect(TokenType.LBRACE)
        statements = self.parse_statement_list_opt()
        self.expect(TokenType.RBRACE)
        return statements

    def parse_expression_opt(self) -> Optional[Any]:
        if self.current_token and self.current_token.type in (TokenType.IDENTIFIER, TokenType.LPAREN, TokenType.MINUS, TokenType.NOT, TokenType.NUMBER, TokenType.FLOAT, TokenType.STRING, TokenType.TRUE, TokenType.FALSE, TokenType.LBRACKET):
            return self.parse_expression()
        return None

    def parse_expression(self) -> Any:
        return self.parse_logical_or()

    def parse_logical_or(self) -> Any:
        left = self.parse_logical_and()
        while self.current_token and self.current_token.type == TokenType.OR:
            op = self.current_token.value
            self.advance()
            right = self.parse_logical_and()
            left = Binary(left, op, right)
        return left

    def parse_logical_and(self) -> Any:
        left = self.parse_equality()
        while self.current_token and self.current_token.type == TokenType.AND:
            op = self.current_token.value
            self.advance()
            right = self.parse_equality()
            left = Binary(left, op, right)
        return left

    def parse_equality(self) -> Any:
        left = self.parse_comparison()
        while self.current_token and self.current_token.type in (TokenType.EQ, TokenType.NE):
            op = self.current_token.value
            self.advance()
            right = self.parse_comparison()
            left = Binary(left, op, right)
        return left

    def parse_comparison(self) -> Any:
        left = self.parse_term()
        while self.current_token and self.current_token.type in (TokenType.LT, TokenType.LE, TokenType.GT, TokenType.GE):
            op = self.current_token.value
            self.advance()
            right = self.parse_term()
            left = Binary(left, op, right)
        return left

    def parse_term(self) -> Any:
        left = self.parse_factor()
        while self.current_token and self.current_token.type in (TokenType.PLUS, TokenType.MINUS):
            op = self.current_token.value
            self.advance()
            right = self.parse_factor()
            left = Binary(left, op, right)
        return left

    def parse_factor(self) -> Any:
        left = self.parse_unary()
        while self.current_token and self.current_token.type in (TokenType.STAR, TokenType.SLASH):
            op = self.current_token.value
            self.advance()
            right = self.parse_unary()
            left = Binary(left, op, right)
        return left

    def parse_unary(self) -> Any:
        if self.current_token and self.current_token.type == TokenType.NOT:
            op = self.current_token.value
            self.advance()
            expr = self.parse_unary()
            return Unary(op, expr)
        elif self.current_token and self.current_token.type == TokenType.MINUS:
            op = self.current_token.value
            self.advance()
            expr = self.parse_unary()
            return Unary(op, expr)
        else:
            return self.parse_postfix()

    def parse_postfix(self) -> Any:
        expr = self.parse_primary()
        while self.current_token and self.current_token.type in (TokenType.DOT, TokenType.LPAREN):
            if self.current_token.type == TokenType.DOT:
                self.advance()
                name = self.expect(TokenType.IDENTIFIER).value
                expr = Member(expr, name)
            elif self.current_token.type == TokenType.LPAREN:
                self.advance()
                args = self.parse_argument_list_opt()
                self.expect(TokenType.RPAREN)
                expr = Call(expr, args)
        return expr

    def parse_primary(self) -> Any:
        if self.current_token.type == TokenType.NUMBER:
            value = self.current_token.value
            self.advance()
            return Literal(value)
        elif self.current_token.type == TokenType.FLOAT:
            value = self.current_token.value
            self.advance()
            return Literal(value)
        elif self.current_token.type == TokenType.STRING:
            value = self.current_token.value
            self.advance()
            return Literal(value)
        elif self.current_token.type == TokenType.TRUE:
            self.advance()
            return Literal(True)
        elif self.current_token.type == TokenType.FALSE:
            self.advance()
            return Literal(False)
        elif self.current_token.type == TokenType.IDENTIFIER:
            value = self.current_token.value
            self.advance()
            return Variable(value)
        elif self.current_token.type == TokenType.LBRACKET:
            return self.parse_list_literal()
        elif self.current_token.type == TokenType.LPAREN:
            self.advance()
            expr = self.parse_expression()
            self.expect(TokenType.RPAREN)
            return expr
        else:
            raise FrontendError(f"Unexpected token {self.current_token.type} at line {self.current_token.line}")

    def parse_argument_list_opt(self) -> List[Any]:
        args = []
        if self.current_token and self.current_token.type not in (TokenType.RPAREN, TokenType.RBRACKET):
            args.append(self.parse_expression())
            while self.current_token and self.current_token.type == TokenType.COMMA:
                self.advance()
                args.append(self.parse_expression())
        return args

    def parse_list_literal(self) -> ListLiteral:
        self.expect(TokenType.LBRACKET)
        values = self.parse_argument_list_opt()
        self.expect(TokenType.RBRACKET)
        return ListLiteral(values=values)

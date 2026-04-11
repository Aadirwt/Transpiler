from __future__ import annotations

from typing import Any

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
from .lexer import Token, TokenType


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        self.current_token = self.tokens[0] if tokens else None

    def advance(self):
        self.pos += 1
        if self.pos < len(self.tokens):
            self.current_token = self.tokens[self.pos]
        else:
            self.current_token = None

    def peek(self, offset: int = 1) -> Token | None:
        peek_pos = self.pos + offset
        if peek_pos < len(self.tokens):
            return self.tokens[peek_pos]
        return None

    def expect(self, token_type: TokenType) -> Token:
        if self.current_token and self.current_token.type == token_type:
            token = self.current_token
            self.advance()
            return token
        expected = token_type.value
        actual = self.current_token.value if self.current_token else "EOF"
        raise FrontendError(
            f"Expected {expected}, got {actual} at line "
            f"{self.current_token.line if self.current_token else 'EOF'}"
        )

    def parse(self) -> Program:
        statements = self.parse_statement_list_opt()
        self.expect(TokenType.EOF)
        return Program(statements)

    def parse_statement_list_opt(self) -> list[Any]:
        statements = []
        while self.current_token and self.current_token.type not in (
            TokenType.RBRACE,
            TokenType.EOF,
        ):
            stmt = self.parse_statement()
            statements.append(stmt)
        return statements

    def parse_statement(self) -> Any:
        if self.current_token.type == TokenType.LET:
            return self.parse_let_statement()
        if self.current_token.type in (TokenType.PRINT, TokenType.PRINT_INLINE):
            return self.parse_print_statement()
        if self.current_token.type == TokenType.IF:
            return self.parse_if_statement()
        if self.current_token.type == TokenType.WHILE:
            return self.parse_while_statement()
        if self.current_token.type == TokenType.FOR:
            return self.parse_for_statement()
        if self.current_token.type == TokenType.FUNCTION:
            return self.parse_function_statement()
        if self.current_token.type == TokenType.CLASS:
            return self.parse_class_statement()
        if self.current_token.type == TokenType.RETURN:
            return self.parse_return_statement()
        if self.current_token.type == TokenType.BREAK:
            return self.parse_break_statement()
        if self.current_token.type == TokenType.CONTINUE:
            return self.parse_continue_statement()

        saved_pos = self.pos
        saved_current = self.current_token
        try:
            lvalue = self.parse_lvalue()
            if self.current_token and self.current_token.type == TokenType.ASSIGN:
                self.advance()
                value = self.parse_expression()
                self.expect(TokenType.SEMI)
                if isinstance(lvalue, str):
                    return Assign(name=lvalue, value=value)
                return MemberAssign(target=lvalue, value=value)
            self.pos = saved_pos
            self.current_token = saved_current
        except Exception:
            self.pos = saved_pos
            self.current_token = saved_current

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
        lvalue: Any = name
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
            args = [self.parse_expression()]
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

    def parse_else_part(self) -> list[Any]:
        if self.current_token and self.current_token.type == TokenType.ELSE:
            self.advance()
            if self.current_token and self.current_token.type == TokenType.IF:
                return [self.parse_if_statement()]
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

    def parse_for_init(self) -> Any | None:
        if self.current_token.type == TokenType.LET:
            return self.parse_let_core()
        if self.current_token.type == TokenType.IDENTIFIER and self.peek() and self.peek().type == TokenType.ASSIGN:
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
        return MemberAssign(target=lvalue, value=value)

    def parse_for_step(self) -> Any | None:
        if not self.current_token:
            return None

        saved_pos = self.pos
        saved_current = self.current_token
        try:
            lvalue = self.parse_lvalue()
            if self.current_token and self.current_token.type == TokenType.ASSIGN:
                self.advance()
                value = self.parse_expression()
                if isinstance(lvalue, str):
                    return Assign(name=lvalue, value=value)
                return MemberAssign(target=lvalue, value=value)
            self.pos = saved_pos
            self.current_token = saved_current
        except Exception:
            self.pos = saved_pos
            self.current_token = saved_current

        expr = self.parse_expression()
        return ExprStmt(expr)

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

    def parse_class_block(self) -> list[FunctionDef]:
        self.expect(TokenType.LBRACE)
        methods = []
        while self.current_token and self.current_token.type != TokenType.RBRACE:
            methods.append(self.parse_class_member())
        self.expect(TokenType.RBRACE)
        return methods

    def parse_class_member(self) -> FunctionDef:
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.LPAREN)
        params = self.parse_param_list_opt()
        self.expect(TokenType.RPAREN)
        body = self.parse_block()
        return FunctionDef(name=name, params=params, body=body)

    def parse_param_list_opt(self) -> list[str]:
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

    def parse_block(self) -> list[Any]:
        self.expect(TokenType.LBRACE)
        statements = self.parse_statement_list_opt()
        self.expect(TokenType.RBRACE)
        return statements

    def parse_expression_opt(self) -> Any | None:
        if self.current_token and self.current_token.type in (
            TokenType.IDENTIFIER,
            TokenType.LPAREN,
            TokenType.MINUS,
            TokenType.NOT,
            TokenType.NUMBER,
            TokenType.FLOAT,
            TokenType.STRING,
            TokenType.TRUE,
            TokenType.FALSE,
            TokenType.LBRACKET,
        ):
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
        while self.current_token and self.current_token.type in (
            TokenType.LT,
            TokenType.LE,
            TokenType.GT,
            TokenType.GE,
        ):
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
        if self.current_token and self.current_token.type == TokenType.MINUS:
            op = self.current_token.value
            self.advance()
            expr = self.parse_unary()
            return Unary(op, expr)
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
        if self.current_token.type == TokenType.FLOAT:
            value = self.current_token.value
            self.advance()
            return Literal(value)
        if self.current_token.type == TokenType.STRING:
            value = self.current_token.value
            self.advance()
            return Literal(value)
        if self.current_token.type == TokenType.TRUE:
            self.advance()
            return Literal(True)
        if self.current_token.type == TokenType.FALSE:
            self.advance()
            return Literal(False)
        if self.current_token.type == TokenType.IDENTIFIER:
            value = self.current_token.value
            self.advance()
            return Variable(value)
        if self.current_token.type == TokenType.LBRACKET:
            return self.parse_list_literal()
        if self.current_token.type == TokenType.LPAREN:
            self.advance()
            expr = self.parse_expression()
            self.expect(TokenType.RPAREN)
            return expr
        raise FrontendError(
            f"Unexpected token {self.current_token.type} at line {self.current_token.line}"
        )

    def parse_argument_list_opt(self) -> list[Any]:
        args = []
        if self.current_token and self.current_token.type not in (
            TokenType.RPAREN,
            TokenType.RBRACKET,
        ):
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

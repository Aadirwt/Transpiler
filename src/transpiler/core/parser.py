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

    def advance(self) -> None:
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

    def skip_newlines(self) -> None:
        while self.current_token and self.current_token.type == TokenType.NEWLINE:
            self.advance()

    def parse(self) -> Program:
        statements = self.parse_statement_list_opt(stop_tokens={TokenType.EOF})
        self.expect(TokenType.EOF)
        return Program(statements)

    def parse_statement_list_opt(self, stop_tokens: set[TokenType]) -> list[Any]:
        statements = []
        self.skip_newlines()
        while self.current_token and self.current_token.type not in stop_tokens:
            statements.append(self.parse_statement())
            self.skip_newlines()
        return statements

    def parse_statement(self) -> Any:
        token_type = self.current_token.type
        if token_type == TokenType.PRINT:
            return self.parse_print_statement()
        if token_type == TokenType.IF:
            return self.parse_if_statement()
        if token_type == TokenType.WHILE:
            return self.parse_while_statement()
        if token_type == TokenType.FOR:
            return self.parse_for_statement()
        if token_type == TokenType.FUNCTION:
            return self.parse_function_statement()
        if token_type == TokenType.CLASS:
            return self.parse_class_statement()
        if token_type == TokenType.RETURN:
            return self.parse_return_statement()
        if token_type == TokenType.BREAK:
            return self.parse_break_statement()
        if token_type == TokenType.CONTINUE:
            return self.parse_continue_statement()
        return self.parse_assignment_or_expr_statement()

    def parse_assignment_or_expr_statement(self) -> Any:
        saved_pos = self.pos
        saved_current = self.current_token
        try:
            lvalue = self.parse_lvalue()
            if self.current_token and self.current_token.type == TokenType.ASSIGN:
                self.advance()
                value = self.parse_expression()
                self.expect_line_end()
                if isinstance(lvalue, str):
                    return Assign(name=lvalue, value=value)
                return MemberAssign(target=lvalue, value=value)
            self.pos = saved_pos
            self.current_token = saved_current
        except Exception:
            self.pos = saved_pos
            self.current_token = saved_current

        expr = self.parse_expression()
        self.expect_line_end()
        return ExprStmt(expr=expr)

    def parse_lvalue(self) -> Any:
        name = self.expect(TokenType.IDENTIFIER).value
        lvalue: Any = name
        while self.current_token and self.current_token.type == TokenType.DOT:
            self.advance()
            member = self.expect(TokenType.IDENTIFIER).value
            lvalue = Member(Variable(lvalue) if isinstance(lvalue, str) else lvalue, member)
        return lvalue

    def parse_print_statement(self) -> Print:
        self.expect(TokenType.PRINT)
        newline = True
        values: list[Any] = []

        if self.current_token and self.current_token.type == TokenType.LPAREN:
            self.advance()
            if self.current_token and self.current_token.type != TokenType.RPAREN:
                while True:
                    if (
                        self.current_token.type == TokenType.IDENTIFIER
                        and self.current_token.value == "end"
                        and self.peek()
                        and self.peek().type == TokenType.ASSIGN
                    ):
                        self.advance()
                        self.advance()
                        end_value = self.parse_expression()
                        if not isinstance(end_value, Literal) or end_value.value != "":
                            raise FrontendError("Only print(..., end='') is supported.")
                        newline = False
                    else:
                        values.append(self.parse_expression())

                    if not self.current_token or self.current_token.type != TokenType.COMMA:
                        break
                    self.advance()
            self.expect(TokenType.RPAREN)
        else:
            values.append(self.parse_expression())

        self.expect_line_end()
        return Print(values=values, newline=newline)

    def parse_if_statement(self) -> If:
        self.expect(TokenType.IF)
        condition = self.parse_expression()
        then_body = self.parse_suite()
        else_body = self.parse_else_part()
        return If(condition=condition, then_body=then_body, else_body=else_body)

    def parse_else_part(self) -> list[Any]:
        if self.current_token and self.current_token.type == TokenType.ELIF:
            self.advance()
            condition = self.parse_expression()
            then_body = self.parse_suite()
            nested_else = self.parse_else_part()
            return [If(condition=condition, then_body=then_body, else_body=nested_else)]
        if self.current_token and self.current_token.type == TokenType.ELSE:
            self.advance()
            return self.parse_suite()
        return []

    def parse_while_statement(self) -> While:
        self.expect(TokenType.WHILE)
        condition = self.parse_expression()
        body = self.parse_suite()
        return While(condition=condition, body=body)

    def parse_for_statement(self) -> For:
        self.expect(TokenType.FOR)
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.IN)
        self.expect(TokenType.RANGE)
        self.expect(TokenType.LPAREN)
        args = self.parse_argument_list_opt()
        self.expect(TokenType.RPAREN)
        body = self.parse_suite()
        return self.build_range_for(name, args, body)

    def build_range_for(self, name: str, args: list[Any], body: list[Any]) -> For:
        if len(args) == 1:
            start, end, step = Literal(0), args[0], Literal(1)
        elif len(args) == 2:
            start, end, step = args[0], args[1], Literal(1)
        elif len(args) == 3:
            start, end, step = args[0], args[1], args[2]
        else:
            raise FrontendError("range() supports 1 to 3 arguments only.")

        compare_op = ">" if self.is_negative_step(step) else "<"
        init = Assign(name=name, value=start)
        condition = Binary(Variable(name), compare_op, end)
        increment = Assign(name=name, value=Binary(Variable(name), "+", step))
        return For(init=init, condition=condition, increment=increment, body=body)

    def is_negative_step(self, step: Any) -> bool:
        if isinstance(step, Literal) and isinstance(step.value, (int, float)):
            return step.value < 0
        return (
            isinstance(step, Unary)
            and step.op == "-"
            and isinstance(step.value, Literal)
            and isinstance(step.value.value, (int, float))
        )

    def parse_function_statement(self) -> FunctionDef:
        self.expect(TokenType.FUNCTION)
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.LPAREN)
        params = self.parse_param_list_opt()
        self.expect(TokenType.RPAREN)
        body = self.parse_suite()
        return FunctionDef(name=name, params=params, body=body)

    def parse_class_statement(self) -> ClassDef:
        self.expect(TokenType.CLASS)
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.COLON)
        self.expect(TokenType.NEWLINE)
        self.expect(TokenType.INDENT)
        methods = self.parse_statement_list_opt(stop_tokens={TokenType.DEDENT})
        self.expect(TokenType.DEDENT)
        typed_methods = [method for method in methods if isinstance(method, FunctionDef)]
        return ClassDef(name=name, methods=typed_methods)

    def parse_return_statement(self) -> Return:
        self.expect(TokenType.RETURN)
        value = None
        if self.current_token and self.current_token.type not in (TokenType.NEWLINE, TokenType.EOF):
            value = self.parse_expression()
        self.expect_line_end()
        return Return(value=value)

    def parse_break_statement(self) -> Break:
        self.expect(TokenType.BREAK)
        self.expect_line_end()
        return Break()

    def parse_continue_statement(self) -> Continue:
        self.expect(TokenType.CONTINUE)
        self.expect_line_end()
        return Continue()

    def parse_suite(self) -> list[Any]:
        self.expect(TokenType.COLON)
        self.expect(TokenType.NEWLINE)
        self.expect(TokenType.INDENT)
        statements = self.parse_statement_list_opt(stop_tokens={TokenType.DEDENT})
        self.expect(TokenType.DEDENT)
        return statements

    def expect_line_end(self) -> None:
        if self.current_token and self.current_token.type == TokenType.NEWLINE:
            self.advance()
            return
        if self.current_token and self.current_token.type in {TokenType.DEDENT, TokenType.EOF}:
            return
        actual = self.current_token.value if self.current_token else "EOF"
        raise FrontendError(f"Expected line end, got {actual}")

    def parse_param_list_opt(self) -> list[str]:
        params = []
        if self.current_token and self.current_token.type == TokenType.IDENTIFIER:
            params.append(self.expect(TokenType.IDENTIFIER).value)
            while self.current_token and self.current_token.type == TokenType.COMMA:
                self.advance()
                params.append(self.expect(TokenType.IDENTIFIER).value)
        return params

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
            return Unary(op, self.parse_unary())
        if self.current_token and self.current_token.type == TokenType.MINUS:
            op = self.current_token.value
            self.advance()
            return Unary(op, self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self) -> Any:
        expr = self.parse_primary()
        while self.current_token and self.current_token.type in (TokenType.DOT, TokenType.LPAREN):
            if self.current_token.type == TokenType.DOT:
                self.advance()
                expr = Member(expr, self.expect(TokenType.IDENTIFIER).value)
            else:
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
        if self.current_token and self.current_token.type != TokenType.RPAREN:
            args.append(self.parse_expression())
            while self.current_token and self.current_token.type == TokenType.COMMA:
                self.advance()
                args.append(self.parse_expression())
        return args

    def parse_list_literal(self) -> ListLiteral:
        self.expect(TokenType.LBRACKET)
        values = []
        if self.current_token and self.current_token.type != TokenType.RBRACKET:
            values = self.parse_argument_list_opt()
        self.expect(TokenType.RBRACKET)
        return ListLiteral(values=values)

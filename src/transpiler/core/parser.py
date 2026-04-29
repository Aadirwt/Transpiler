from __future__ import annotations

from typing import Any

from .ast_nodes import (
    AnnAssign, Arg, Assert, Assign, Attribute, AugAssign, BinaryOp, Boolean,
    BoolOp, Break, Call, ClassDef, Compare, Continue, Delete, DictComp, Dict_,
    Ellipsis_, ExceptHandler, FString, For, FuncDef, GeneratorExp, Global,
    Identifier, If, Import, ImportFrom, Lambda, ListComp, List_, NoneNode,
    Nonlocal, Number, Pass, Program, Raise, Return, SetComp, Set_, Slice,
    StarExpr, String, Subscript, Ternary, Try, Tuple_, UnaryOp, Walrus, While,
    With, Yield, YieldFrom,
)
from .errors import FrontendError
from .lexer import Token, TokenType


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        self.current = tokens[0]

    def advance(self) -> None:
        self.pos += 1
        if self.pos < len(self.tokens):
            self.current = self.tokens[self.pos]

    def peek(self, k: int = 1) -> Token:
        pos = self.pos + k
        return self.tokens[pos] if pos < len(self.tokens) else self.tokens[-1]

    def eat(self, token_type: TokenType) -> Token:
        if self.current.type == token_type:
            tok = self.current
            self.advance()
            return tok
        raise FrontendError(
            f"Line {self.current.line}: Expected {token_type}, got {self.current.type} ({self.current.value!r})"
        )

    def match(self, *types: TokenType) -> bool:
        return self.current.type in types

    def skip_newlines(self) -> None:
        while self.match(TokenType.NEWLINE):
            self.advance()

    def parse(self) -> Program:
        statements = []
        self.skip_newlines()
        while not self.match(TokenType.EOF):
            statements.append(self.statement())
            self.skip_newlines()
        return Program(statements)

    def statement(self) -> Any:
        if self.match(TokenType.AT):
            return self.decorated()
        if self.match(TokenType.DEF):
            return self.func_def()
        if self.match(TokenType.CLASS):
            return self.class_def()
        if self.match(TokenType.IF):
            return self.if_statement()
        if self.match(TokenType.WHILE):
            return self.while_statement()
        if self.match(TokenType.FOR):
            return self.for_statement()
        if self.match(TokenType.TRY):
            return self.try_statement()
        if self.match(TokenType.WITH):
            return self.with_statement()
        if self.match(TokenType.RETURN):
            return self.return_statement()
        if self.match(TokenType.RAISE):
            return self.raise_statement()
        if self.match(TokenType.IMPORT):
            return self.import_statement()
        if self.match(TokenType.FROM):
            return self.from_import_statement()
        if self.match(TokenType.GLOBAL):
            return self.global_statement()
        if self.match(TokenType.NONLOCAL):
            return self.nonlocal_statement()
        if self.match(TokenType.DEL):
            return self.del_statement()
        if self.match(TokenType.ASSERT):
            return self.assert_statement()
        if self.match(TokenType.PASS):
            self.advance()
            self.eat_newline()
            return Pass()
        if self.match(TokenType.BREAK):
            self.advance()
            self.eat_newline()
            return Break()
        if self.match(TokenType.CONTINUE):
            self.advance()
            self.eat_newline()
            return Continue()
        return self.expr_statement()

    def eat_newline(self) -> None:
        if self.match(TokenType.NEWLINE):
            self.advance()
        elif self.match(TokenType.SEMICOLON):
            self.advance()

    def expr_statement(self) -> Any:
        expr = self.expr()
        if self.match(TokenType.COLON):
            self.advance()
            annotation = self.expr()
            value = None
            if self.match(TokenType.ASSIGN):
                self.advance()
                value = self.expr()
            self.eat_newline()
            return AnnAssign(expr, annotation, value)
        aug_ops = {
            TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN, TokenType.STAR_ASSIGN,
            TokenType.SLASH_ASSIGN, TokenType.FLOOR_DIV_ASSIGN, TokenType.POWER_ASSIGN,
            TokenType.MODULO_ASSIGN, TokenType.AND_ASSIGN, TokenType.OR_ASSIGN,
            TokenType.XOR_ASSIGN, TokenType.LSHIFT_ASSIGN, TokenType.RSHIFT_ASSIGN,
        }
        if self.current.type in aug_ops:
            op = self.current.type
            self.advance()
            value = self.expr()
            self.eat_newline()
            return AugAssign(expr, op, value)
        if self.match(TokenType.ASSIGN):
            targets = [expr]
            while self.match(TokenType.ASSIGN):
                self.advance()
                targets.append(self.expr())
            value = targets.pop()
            self.eat_newline()
            return Assign(targets, value)
        self.eat_newline()
        return expr

    def decorated(self) -> Any:
        decorators = []
        while self.match(TokenType.AT):
            self.advance()
            decorators.append(self.expr())
            self.eat_newline()
            self.skip_newlines()
        if self.match(TokenType.DEF):
            node = self.func_def()
        elif self.match(TokenType.CLASS):
            node = self.class_def()
        else:
            raise FrontendError(f"Line {self.current.line}: Expected def or class after decorator")
        node.decorators = decorators
        return node

    def func_def(self, is_async: bool = False) -> FuncDef:
        self.eat(TokenType.DEF)
        name = self.eat(TokenType.IDENTIFIER).value
        self.eat(TokenType.LPAREN)
        args, vararg, kwarg = self.parse_params()
        self.eat(TokenType.RPAREN)
        returns = None
        if self.match(TokenType.ARROW):
            self.advance()
            returns = self.expr()
        self.eat(TokenType.COLON)
        body = self.block()
        return FuncDef(name, args, vararg, kwarg, body, [], returns, is_async)

    def parse_params(self) -> tuple[list[Arg], Arg | None, Arg | None]:
        args: list[Arg] = []
        vararg = None
        kwarg = None
        while not self.match(TokenType.RPAREN):
            if self.match(TokenType.POWER):
                self.advance()
                name = self.eat(TokenType.IDENTIFIER).value
                annotation = self._optional_annotation()
                kwarg = Arg(name, annotation, None)
                if self.match(TokenType.COMMA):
                    self.advance()
                break
            if self.match(TokenType.STAR):
                self.advance()
                if self.match(TokenType.IDENTIFIER):
                    name = self.eat(TokenType.IDENTIFIER).value
                    vararg = Arg(name, self._optional_annotation(), None)
                if self.match(TokenType.COMMA):
                    self.advance()
                continue
            name = self.eat(TokenType.IDENTIFIER).value
            annotation = self._optional_annotation()
            default = None
            if self.match(TokenType.ASSIGN):
                self.advance()
                default = self.expr()
            args.append(Arg(name, annotation, default))
            if self.match(TokenType.COMMA):
                self.advance()
        return args, vararg, kwarg

    def _optional_annotation(self) -> Any:
        if self.match(TokenType.COLON):
            self.advance()
            return self.expr()
        return None

    def class_def(self) -> ClassDef:
        self.eat(TokenType.CLASS)
        name = self.eat(TokenType.IDENTIFIER).value
        bases = []
        if self.match(TokenType.LPAREN):
            self.advance()
            while not self.match(TokenType.RPAREN):
                bases.append(self.expr())
                if self.match(TokenType.COMMA):
                    self.advance()
            self.eat(TokenType.RPAREN)
        self.eat(TokenType.COLON)
        return ClassDef(name, bases, self.block(), [])

    def if_statement(self) -> If:
        self.eat(TokenType.IF)
        condition = self.expr()
        self.eat(TokenType.COLON)
        body = self.block()
        elifs = []
        else_body = None
        while self.match(TokenType.ELIF):
            self.advance()
            elif_cond = self.expr()
            self.eat(TokenType.COLON)
            elifs.append((elif_cond, self.block()))
        if self.match(TokenType.ELSE):
            self.advance()
            self.eat(TokenType.COLON)
            else_body = self.block()
        return If(condition, body, elifs, else_body)

    def while_statement(self) -> While:
        self.eat(TokenType.WHILE)
        condition = self.expr()
        self.eat(TokenType.COLON)
        body = self.block()
        else_body = None
        if self.match(TokenType.ELSE):
            self.advance()
            self.eat(TokenType.COLON)
            else_body = self.block()
        return While(condition, body, else_body)

    def for_statement(self) -> For:
        self.eat(TokenType.FOR)
        target = self.for_target()
        self.eat(TokenType.IN)
        iterable = self.expr()
        self.eat(TokenType.COLON)
        body = self.block()
        else_body = None
        if self.match(TokenType.ELSE):
            self.advance()
            self.eat(TokenType.COLON)
            else_body = self.block()
        return For(target, iterable, body, else_body)

    def for_target(self) -> Any:
        targets = [self.primary()]
        while self.match(TokenType.COMMA):
            self.advance()
            if self.match(TokenType.IN):
                break
            targets.append(self.primary())
        return targets[0] if len(targets) == 1 else Tuple_(targets)

    def try_statement(self) -> Try:
        self.eat(TokenType.TRY)
        self.eat(TokenType.COLON)
        body = self.block()
        handlers = []
        while self.match(TokenType.EXCEPT):
            handlers.append(self.except_handler())
        else_body = None
        if self.match(TokenType.ELSE):
            self.advance()
            self.eat(TokenType.COLON)
            else_body = self.block()
        final_body = None
        if self.match(TokenType.FINALLY):
            self.advance()
            self.eat(TokenType.COLON)
            final_body = self.block()
        if not handlers and not final_body:
            raise FrontendError(f"Line {self.current.line}: try must have except or finally")
        return Try(body, handlers, else_body, final_body)

    def except_handler(self) -> ExceptHandler:
        self.eat(TokenType.EXCEPT)
        type_ = None
        name = None
        if not self.match(TokenType.COLON):
            type_ = self.expr()
            if self.match(TokenType.AS):
                self.advance()
                name = self.eat(TokenType.IDENTIFIER).value
        self.eat(TokenType.COLON)
        return ExceptHandler(type_, name, self.block())

    def with_statement(self) -> With:
        self.eat(TokenType.WITH)
        items = []
        while True:
            ctx = self.expr()
            var = None
            if self.match(TokenType.AS):
                self.advance()
                var = self.expr()
            items.append((ctx, var))
            if not self.match(TokenType.COMMA):
                break
            self.advance()
        self.eat(TokenType.COLON)
        return With(items, self.block())

    def import_statement(self) -> Import:
        self.eat(TokenType.IMPORT)
        names = []
        while True:
            name = self.dotted_name()
            alias = None
            if self.match(TokenType.AS):
                self.advance()
                alias = self.eat(TokenType.IDENTIFIER).value
            names.append((name, alias))
            if not self.match(TokenType.COMMA):
                break
            self.advance()
        self.eat_newline()
        return Import(names)

    def from_import_statement(self) -> ImportFrom:
        self.eat(TokenType.FROM)
        module = self.dotted_name()
        self.eat(TokenType.IMPORT)
        names = []
        if self.match(TokenType.STAR):
            self.advance()
            names.append(("*", None))
        else:
            while True:
                name = self.eat(TokenType.IDENTIFIER).value
                alias = None
                if self.match(TokenType.AS):
                    self.advance()
                    alias = self.eat(TokenType.IDENTIFIER).value
                names.append((name, alias))
                if not self.match(TokenType.COMMA):
                    break
                self.advance()
        self.eat_newline()
        return ImportFrom(module, names)

    def dotted_name(self) -> str:
        name = self.eat(TokenType.IDENTIFIER).value
        while self.match(TokenType.DOT):
            self.advance()
            name += "." + self.eat(TokenType.IDENTIFIER).value
        return name

    def return_statement(self) -> Return:
        self.eat(TokenType.RETURN)
        value = None
        if not self.match(TokenType.NEWLINE, TokenType.EOF, TokenType.DEDENT):
            value = self.expr()
        self.eat_newline()
        return Return(value)

    def raise_statement(self) -> Raise:
        self.eat(TokenType.RAISE)
        exc = None
        cause = None
        if not self.match(TokenType.NEWLINE, TokenType.EOF):
            exc = self.expr()
            if self.match(TokenType.FROM):
                self.advance()
                cause = self.expr()
        self.eat_newline()
        return Raise(exc, cause)

    def assert_statement(self) -> Assert:
        self.eat(TokenType.ASSERT)
        test = self.expr()
        msg = None
        if self.match(TokenType.COMMA):
            self.advance()
            msg = self.expr()
        self.eat_newline()
        return Assert(test, msg)

    def del_statement(self) -> Delete:
        self.eat(TokenType.DEL)
        targets = [self.expr()]
        while self.match(TokenType.COMMA):
            self.advance()
            targets.append(self.expr())
        self.eat_newline()
        return Delete(targets)

    def global_statement(self) -> Global:
        self.eat(TokenType.GLOBAL)
        names = [self.eat(TokenType.IDENTIFIER).value]
        while self.match(TokenType.COMMA):
            self.advance()
            names.append(self.eat(TokenType.IDENTIFIER).value)
        self.eat_newline()
        return Global(names)

    def nonlocal_statement(self) -> Nonlocal:
        self.eat(TokenType.NONLOCAL)
        names = [self.eat(TokenType.IDENTIFIER).value]
        while self.match(TokenType.COMMA):
            self.advance()
            names.append(self.eat(TokenType.IDENTIFIER).value)
        self.eat_newline()
        return Nonlocal(names)

    def block(self) -> list[Any]:
        statements = []
        if self.match(TokenType.NEWLINE):
            self.eat(TokenType.NEWLINE)
            self.skip_newlines()
            self.eat(TokenType.INDENT)
            self.skip_newlines()
            while not self.match(TokenType.DEDENT, TokenType.EOF):
                statements.append(self.statement())
                self.skip_newlines()
            if self.match(TokenType.DEDENT):
                self.advance()
        else:
            statements.append(self.statement())
        return statements

    def expr(self) -> Any:
        return self.ternary()

    def ternary(self) -> Any:
        node = self.logical_or()
        if self.match(TokenType.IF):
            self.advance()
            condition = self.logical_or()
            self.eat(TokenType.ELSE)
            return Ternary(condition, node, self.ternary())
        return node

    def logical_or(self) -> Any:
        values = [self.logical_and()]
        while self.match(TokenType.OR):
            self.advance()
            values.append(self.logical_and())
        return values[0] if len(values) == 1 else BoolOp(TokenType.OR, values)

    def logical_and(self) -> Any:
        values = [self.logical_not()]
        while self.match(TokenType.AND):
            self.advance()
            values.append(self.logical_not())
        return values[0] if len(values) == 1 else BoolOp(TokenType.AND, values)

    def logical_not(self) -> Any:
        if self.match(TokenType.NOT):
            op = self.current.type
            self.advance()
            return UnaryOp(op, self.logical_not())
        return self.comparison()

    def comparison(self) -> Any:
        node = self.bitor()
        ops = []
        comparators = []
        while self.match(TokenType.EQ, TokenType.NE, TokenType.LT, TokenType.LE, TokenType.GT, TokenType.GE, TokenType.IN, TokenType.IS, TokenType.NOT):
            if self.match(TokenType.NOT):
                self.advance()
                self.eat(TokenType.IN)
                ops.append("not in")
            elif self.match(TokenType.IS):
                self.advance()
                if self.match(TokenType.NOT):
                    self.advance()
                    ops.append("is not")
                else:
                    ops.append(TokenType.IS)
            else:
                ops.append(self.current.type)
                self.advance()
            comparators.append(self.bitor())
        return node if not ops else Compare(node, ops, comparators)

    def bitor(self) -> Any:
        node = self.bitxor()
        while self.match(TokenType.BIT_OR):
            op = self.current.type; self.advance()
            node = BinaryOp(node, op, self.bitxor())
        return node

    def bitxor(self) -> Any:
        node = self.bitand()
        while self.match(TokenType.BIT_XOR):
            op = self.current.type; self.advance()
            node = BinaryOp(node, op, self.bitand())
        return node

    def bitand(self) -> Any:
        node = self.shift()
        while self.match(TokenType.BIT_AND):
            op = self.current.type; self.advance()
            node = BinaryOp(node, op, self.shift())
        return node

    def shift(self) -> Any:
        node = self.term()
        while self.match(TokenType.LSHIFT, TokenType.RSHIFT):
            op = self.current.type; self.advance()
            node = BinaryOp(node, op, self.term())
        return node

    def term(self) -> Any:
        node = self.factor()
        while self.match(TokenType.PLUS, TokenType.MINUS):
            op = self.current.type; self.advance()
            node = BinaryOp(node, op, self.factor())
        return node

    def factor(self) -> Any:
        node = self.unary()
        while self.match(TokenType.STAR, TokenType.SLASH, TokenType.FLOOR_DIV, TokenType.MODULO):
            op = self.current.type; self.advance()
            node = BinaryOp(node, op, self.unary())
        return node

    def unary(self) -> Any:
        if self.match(TokenType.MINUS, TokenType.BIT_NOT):
            op = self.current.type
            self.advance()
            return UnaryOp(op, self.unary())
        return self.power()

    def power(self) -> Any:
        node = self.call_expr()
        if self.match(TokenType.POWER):
            op = self.current.type
            self.advance()
            node = BinaryOp(node, op, self.unary())
        return node

    def call_expr(self) -> Any:
        node = self.primary()
        while True:
            if self.match(TokenType.LPAREN):
                node = self.finish_call(node)
            elif self.match(TokenType.DOT):
                self.advance()
                node = Attribute(node, self.eat(TokenType.IDENTIFIER).value)
            elif self.match(TokenType.LBRACKET):
                self.advance()
                index = self.parse_subscript()
                self.eat(TokenType.RBRACKET)
                node = Subscript(node, index)
            else:
                break
        return node

    def finish_call(self, func: Any) -> Call:
        self.eat(TokenType.LPAREN)
        args = []
        kwargs = []
        while not self.match(TokenType.RPAREN):
            if self.match(TokenType.POWER):
                self.advance()
                kwargs.append((None, StarExpr(self.expr())))
            elif self.match(TokenType.STAR):
                self.advance()
                args.append(StarExpr(self.expr()))
            elif self.match(TokenType.IDENTIFIER) and self.peek().type == TokenType.ASSIGN:
                key = self.eat(TokenType.IDENTIFIER).value
                self.advance()
                kwargs.append((key, self.expr()))
            else:
                args.append(self.expr())
            if self.match(TokenType.COMMA):
                self.advance()
        self.eat(TokenType.RPAREN)
        return Call(func, args, kwargs)

    def parse_subscript(self) -> Any:
        start = None
        stop = None
        step = None
        if not self.match(TokenType.COLON):
            start = self.expr()
        if self.match(TokenType.COLON):
            self.advance()
            if not self.match(TokenType.COLON, TokenType.RBRACKET):
                stop = self.expr()
            if self.match(TokenType.COLON):
                self.advance()
                if not self.match(TokenType.RBRACKET):
                    step = self.expr()
            return Slice(start, stop, step)
        return start

    def primary(self) -> Any:
        token = self.current
        if token.type in (TokenType.NUMBER, TokenType.FLOAT):
            self.advance(); return Number(token.value)
        if token.type == TokenType.STRING:
            self.advance(); return String(token.value)
        if token.type == TokenType.FSTRING:
            self.advance(); return FString(token.value)
        if token.type == TokenType.TRUE:
            self.advance(); return Boolean(True)
        if token.type == TokenType.FALSE:
            self.advance(); return Boolean(False)
        if token.type == TokenType.NONE:
            self.advance(); return NoneNode()
        if token.type == TokenType.ELLIPSIS:
            self.advance(); return Ellipsis_()
        if token.type == TokenType.IDENTIFIER:
            self.advance()
            if self.match(TokenType.WALRUS):
                self.advance()
                return Walrus(token.value, self.expr())
            return Identifier(token.value)
        if token.type == TokenType.LAMBDA:
            return self.lambda_expr()
        if token.type == TokenType.YIELD:
            return self.yield_expr()
        if token.type == TokenType.LPAREN:
            return self.paren_expr()
        if token.type == TokenType.LBRACKET:
            return self.list_expr()
        if token.type == TokenType.LBRACE:
            return self.dict_or_set_expr()
        if token.type == TokenType.STAR:
            self.advance()
            return StarExpr(self.expr())
        raise FrontendError(f"Line {token.line}: Unexpected token {token.type} ({token.value!r})")

    def lambda_expr(self) -> Lambda:
        self.eat(TokenType.LAMBDA)
        args = []
        while not self.match(TokenType.COLON):
            name = self.eat(TokenType.IDENTIFIER).value
            default = None
            if self.match(TokenType.ASSIGN):
                self.advance()
                default = self.expr()
            args.append(Arg(name, None, default))
            if self.match(TokenType.COMMA):
                self.advance()
        self.eat(TokenType.COLON)
        return Lambda(args, self.expr())

    def yield_expr(self) -> Any:
        self.eat(TokenType.YIELD)
        if self.match(TokenType.FROM):
            self.advance()
            return YieldFrom(self.expr())
        value = None
        if not self.match(TokenType.NEWLINE, TokenType.RPAREN, TokenType.RBRACKET, TokenType.RBRACE, TokenType.EOF):
            value = self.expr()
        return Yield(value)

    def paren_expr(self) -> Any:
        self.eat(TokenType.LPAREN)
        if self.match(TokenType.RPAREN):
            self.advance()
            return Tuple_([])
        expr = self.expr()
        if self.match(TokenType.FOR):
            result = self.comprehension_clauses(expr)
            self.eat(TokenType.RPAREN)
            return GeneratorExp(result[0], result[1], result[2], result[3])
        if self.match(TokenType.COMMA):
            elements = [expr]
            while self.match(TokenType.COMMA):
                self.advance()
                if self.match(TokenType.RPAREN):
                    break
                elements.append(self.expr())
            self.eat(TokenType.RPAREN)
            return Tuple_(elements)
        self.eat(TokenType.RPAREN)
        return expr

    def list_expr(self) -> Any:
        self.eat(TokenType.LBRACKET)
        if self.match(TokenType.RBRACKET):
            self.advance()
            return List_([])
        expr = self.expr()
        if self.match(TokenType.FOR):
            result = self.comprehension_clauses(expr)
            self.eat(TokenType.RBRACKET)
            return ListComp(result[0], result[1], result[2], result[3])
        elements = [expr]
        while self.match(TokenType.COMMA):
            self.advance()
            if self.match(TokenType.RBRACKET):
                break
            elements.append(self.expr())
        self.eat(TokenType.RBRACKET)
        return List_(elements)

    def dict_or_set_expr(self) -> Any:
        self.eat(TokenType.LBRACE)
        if self.match(TokenType.RBRACE):
            self.advance()
            return Dict_([], [])
        first = self.expr()
        if self.match(TokenType.COLON):
            self.advance()
            value = self.expr()
            if self.match(TokenType.FOR):
                result = self.comprehension_clauses(value)
                self.eat(TokenType.RBRACE)
                return DictComp(first, result[0], result[1], result[2], result[3])
            keys = [first]
            values = [value]
            while self.match(TokenType.COMMA):
                self.advance()
                if self.match(TokenType.RBRACE):
                    break
                keys.append(self.expr())
                self.eat(TokenType.COLON)
                values.append(self.expr())
            self.eat(TokenType.RBRACE)
            return Dict_(keys, values)
        if self.match(TokenType.FOR):
            result = self.comprehension_clauses(first)
            self.eat(TokenType.RBRACE)
            return SetComp(result[0], result[1], result[2], result[3])
        elements = [first]
        while self.match(TokenType.COMMA):
            self.advance()
            if self.match(TokenType.RBRACE):
                break
            elements.append(self.expr())
        self.eat(TokenType.RBRACE)
        return Set_(elements)

    def comprehension_clauses(self, expr: Any) -> tuple[Any, Any, Any, Any]:
        self.eat(TokenType.FOR)
        target = self.for_target()
        self.eat(TokenType.IN)
        iterable = self.expr()
        condition = None
        if self.match(TokenType.IF):
            self.advance()
            condition = self.expr()
        return expr, target, iterable, condition

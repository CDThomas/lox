import lark
import typing

from lox import ast
from lox import environment
from lox import errors
from lox import lox_callable
from lox import lox_class
from lox import lox_function
from lox import lox_globals
from lox import lox_instance
from lox import lox_return
from lox import types
from lox import visitor

ObjId = typing.NewType("ObjId", int)


class Interpreter(
    visitor.StatementVisitor[None],
    visitor.ExpressionVisitor[typing.Optional[types.Value]],
):
    def __init__(self) -> None:
        globals = environment.Environment()
        globals.define("clock", lox_globals.ClockGlobal())

        self.globals = globals
        self.environment = globals
        self.locals: dict[ObjId, int] = {}

    def interpret(self, statements: list[ast._Statement]) -> None:
        for statement in statements:
            self._execute(statement)

        return None

    def visit_expression_statement(
        self, statement: ast.ExpressionStatement
    ) -> None:
        self._evaluate(statement.expression)
        return None

    def visit_function(self, statement: ast.Function) -> None:
        func = lox_function.LoxFunction(statement, self.environment, False)
        self.environment.define(statement.name.value, func)

        return None

    def visit_if_statement(self, statement: ast.IfStatement) -> None:
        if self._is_truthy(self._evaluate(statement.condition)):
            self._execute(statement.then_branch)
        elif statement.else_branch:
            self._execute(statement.else_branch)

    def visit_print_statement(self, statement: ast.PrintStatement) -> None:
        value = self._evaluate(statement.expression)
        print(self._stringify(value))
        return None

    def visit_return_statement(self, statement: ast.ReturnStatement) -> None:
        value: typing.Optional[types.Value] = None
        if statement.value:
            value = self._evaluate(statement.value)

        raise lox_return.LoxReturn(value)

    def visit_variable_declaration(
        self, statement: ast.VariableDeclaration
    ) -> None:
        value = None

        if statement.initializer:
            value = self._evaluate(statement.initializer)

        self.environment.define(statement.name.value, value)

        return None

    def visit_while_statement(self, statement: ast.WhileStatement) -> None:
        while self._is_truthy(self._evaluate(statement.condition)):
            self._execute(statement.body)

        return None

    def visit_assignment_expression(
        self, expression: ast.Assignment
    ) -> typing.Optional[types.Value]:
        value = self._evaluate(expression.value)

        distance = self.locals.get(self._obj_id(expression))

        if distance is not None:
            self.environment.assign_at(distance, expression.name, value)
        else:
            self.globals.assign(expression.name, value)

        return value

    def visit_literal_expression(
        self, expression: ast.Literal
    ) -> typing.Optional[types.Value]:
        return expression.value

    def visit_logical_expression(
        self, expression: ast.LogicalExpression
    ) -> typing.Optional[types.Value]:
        left = self._evaluate(expression.left)

        if expression.operator.value == "or":
            if self._is_truthy(left):
                return left
        else:
            if not self._is_truthy(left):
                return left

        return self._evaluate(expression.right)

    def visit_grouping_expression(
        self, expression: ast.Grouping
    ) -> typing.Optional[types.Value]:
        return self._evaluate(expression.expression)

    def visit_unary_expression(
        self, expression: ast.Unary
    ) -> typing.Optional[types.Value]:
        right = self._evaluate(expression.right)

        if expression.operator.value == "!":
            return not self._is_truthy(right)
        elif expression.operator.value == "-":
            right = self._check_number_operand(expression.operator, right)
            return -right

        # Unreachable.
        return None

    def visit_variable_expression(
        self, expression: ast.Variable
    ) -> typing.Optional[types.Value]:
        return self._look_up_variable(expression.name, expression)

    def visit_binary_expression(
        self, expression: ast.Binary
    ) -> typing.Optional[types.Value]:
        left = self._evaluate(expression.left)
        right = self._evaluate(expression.right)

        op = expression.operator.value

        if op == ">":
            left, right = self._check_number_operands(
                expression.operator, left, right
            )
            return left > right
        elif op == ">=":
            left, right = self._check_number_operands(
                expression.operator, left, right
            )
            return left >= right
        elif op == "<":
            left, right = self._check_number_operands(
                expression.operator, left, right
            )
            return left < right
        elif op == "<=":
            left, right = self._check_number_operands(
                expression.operator, left, right
            )
            return left <= right
        elif op == "-":
            left, right = self._check_number_operands(
                expression.operator, left, right
            )
            return left - right
        elif op == "/":
            left, right = self._check_number_operands(
                expression.operator, left, right
            )
            return left / right
        elif op == "*":
            left, right = self._check_number_operands(
                expression.operator, left, right
            )
            return left * right
        elif op == "==":
            return self._is_equal(left, right)
        elif op == "!=":
            return not self._is_equal(left, right)
        elif op == "+":
            if isinstance(left, float) and isinstance(right, float):
                return left + right

            if isinstance(left, str) and isinstance(right, str):
                return left + right

            raise errors.LoxRuntimeError(
                expression.operator,
                "Operands must be two numbers or two strings.",
            )

        # Unreachable.
        return None

    def visit_call_expression(
        self, expression: ast.Call
    ) -> typing.Optional[types.Value]:
        callee = self._evaluate(expression.callee)

        arguments: list[typing.Optional[types.Value]] = []

        for argument in expression.arguments:
            arguments.append(self._evaluate(argument))

        if not isinstance(callee, lox_callable.LoxCallable):
            raise errors.LoxRuntimeError(
                expression.closing_paren,
                "Can only call functions and classes.",
            )

        if len(arguments) != callee.arity():
            message = (
                f"Expected {callee.arity()} arguments"
                f" but got {len(arguments)}."
            )

            raise errors.LoxRuntimeError(expression.closing_paren, message)

        return callee.call(self, arguments)

    def visit_get_expression(
        self, expression: ast.Get
    ) -> typing.Optional[types.Value]:
        obj = self._evaluate(expression.obj)

        if isinstance(obj, lox_instance.LoxInstance):
            return obj.get(expression.name)

        raise errors.LoxRuntimeError(
            expression.name, "Only instances have properties."
        )

    def visit_set_expression(
        self, expression: ast.Set
    ) -> typing.Optional[types.Value]:
        obj = self._evaluate(expression.obj)

        if not isinstance(obj, lox_instance.LoxInstance):
            raise errors.LoxRuntimeError(
                expression.name, "Only instances have fields."
            )

        value = self._evaluate(expression.value)

        obj.set(expression.name, value)

        return value

    def visit_super_expression(
        self, expression: ast.Super
    ) -> typing.Optional[types.Value]:
        distance = self.locals.get(self._obj_id(expression))
        assert distance is not None

        superclass = self.environment.get_at(distance, "super")
        assert isinstance(superclass, lox_class.LoxClass)

        obj = self.environment.get_at(distance - 1, "this")
        assert isinstance(obj, lox_instance.LoxInstance)

        method = superclass.find_method(expression.method.value)

        if not method:
            raise errors.LoxRuntimeError(
                expression.method,
                f"Undefined property '{expression.method.value}'.",
            )

        return method.bind(obj)

    def visit_this_expression(
        self, expression: ast.This
    ) -> typing.Optional[types.Value]:
        return self._look_up_variable(expression.keyword, expression)

    def visit_block_statement(self, statement: ast.Block) -> None:
        self._execute_block(
            statement.statements, environment.Environment(self.environment)
        )

    def visit_class_declaration(self, statement: ast.ClassDeclaration) -> None:
        superclass: typing.Optional[types.Value] = None
        if statement.superclass:
            superclass = self._evaluate(statement.superclass)

            if not isinstance(superclass, lox_class.LoxClass):
                raise errors.LoxRuntimeError(
                    statement.superclass.name, "Superclass must be a class."
                )

        # Need this assertion since Mypy doesn't seem to automatically narrow
        # this type from the nested if statement above.
        assert isinstance(superclass, lox_class.LoxClass) or superclass is None

        self.environment.define(statement.name.value, None)

        if statement.superclass:
            self.environment = environment.Environment(self.environment)
            self.environment.define("super", superclass)

        methods: dict[str, lox_function.LoxFunction] = {}
        for method in statement.methods:
            func = lox_function.LoxFunction(
                method, self.environment, method.name.value == "init"
            )
            methods[method.name.value] = func

        klass = lox_class.LoxClass(statement.name.value, superclass, methods)

        if superclass:
            assert self.environment.enclosing
            self.environment = self.environment.enclosing

        self.environment.assign(statement.name, klass)

    def resolve(self, expression: ast._Expression, depth: int) -> None:
        self.locals[self._obj_id(expression)] = depth

    def _look_up_variable(
        self, name: lark.Token, expression: ast._Expression
    ) -> typing.Optional[types.Value]:
        distance = self.locals.get(self._obj_id(expression))
        if distance is not None:
            return self.environment.get_at(distance, name.value)
        else:
            return self.globals.get(name)

    def _execute(self, statement: ast._Statement) -> None:
        return statement.accept(self)

    def _execute_block(
        self,
        statements: list[ast._Statement],
        environment: environment.Environment,
    ) -> None:
        if not statements:
            return

        prevous = self.environment

        try:
            self.environment = environment

            for statement in statements:
                self._execute(statement)
        finally:
            self.environment = prevous

    def _evaluate(
        self, expression: ast._Expression
    ) -> typing.Optional[types.Value]:
        return expression.accept(self)

    def _is_truthy(self, value: typing.Optional[types.Value]) -> bool:
        if value is None:
            return False

        if isinstance(value, bool):
            return value

        return True

    def _is_equal(
        self, a: typing.Optional[types.Value], b: typing.Optional[types.Value]
    ):
        return a == b and type(a) == type(b)

    def _stringify(self, value: typing.Optional[types.Value]) -> str:
        if value is None:
            return "nil"

        if value is True:
            return "true"

        if value is False:
            return "false"

        if isinstance(value, float):
            text = str(value)

            if text.endswith(".0"):
                return text[:-2]
            else:
                return text

        if isinstance(value, str):
            return value

        return value.to_string()

    def _check_number_operand(
        self, operator: lark.Token, operand: typing.Optional[types.Value]
    ) -> float:
        if isinstance(operand, float):
            return operand

        raise errors.LoxRuntimeError(operator, "Operand must be a number.")

    def _check_number_operands(
        self,
        operator: lark.Token,
        left: typing.Optional[types.Value],
        right: typing.Optional[types.Value],
    ) -> tuple[float, float]:
        if isinstance(left, float) and isinstance(right, float):
            return left, right

        raise errors.LoxRuntimeError(operator, "Operands must be numbers.")

    # XXX: Returns Python's internal ID for the expression's AST node. This is
    # a workaround for Lark requiring mutable AST node objects and Python
    # needing immutable dict keys. This isn't ideal since IDs can be reused
    # once objects are garbage collected, but should be OK since the ID is
    # used to keep track of expression nodes which are all held in memory at
    # the same time.
    def _obj_id(self, obj: ast._Expression) -> ObjId:
        return ObjId(id(obj))

import argparse
import enum
import sys

import lark

import lox.errors
import lox.interpreter
import lox.parser
import lox.resolver


class InterpreterResult(enum.Enum):
    OK = enum.auto()
    SYNTAX_ERROR = enum.auto()
    RUNTIME_ERROR = enum.auto()


def main() -> None:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "path", nargs="?", help="path to the Lox file to run"
    )
    args = arg_parser.parse_args()

    if args.path:
        _run_file(args.path)
    else:
        try:
            _run_prompt()
        except KeyboardInterrupt:
            # Suppress error and exit normally.
            pass


def _run_file(path: str) -> None:
    with open(path, "r") as reader:
        interpreter = lox.interpreter.Interpreter()
        result = _run(interpreter, reader.read())

        if result == InterpreterResult.SYNTAX_ERROR:
            sys.exit(65)

        if result == InterpreterResult.RUNTIME_ERROR:
            sys.exit(70)


def _run_prompt() -> None:
    interpreter = lox.interpreter.Interpreter()

    while True:
        line = input("> ")

        if line == "":
            break

        _run(interpreter, line)


def _run(
    interpreter: lox.interpreter.Interpreter, code: str
) -> InterpreterResult:

    try:
        statements = lox.parser.parse(code)
    except lark.UnexpectedInput as error:
        print(f"Syntax error:\n\n{error}", file=sys.stderr)
        return InterpreterResult.SYNTAX_ERROR

    try:
        resolver = lox.resolver.Resolver(interpreter)
        resolver.resolve(statements)
    except lox.errors.LoxResolutionError as error:
        message = (
            f"[line {error.token.line}] "
            f"Error at '{error.token.value}': {error.message}"
        )
        print(message, file=sys.stderr)

        return InterpreterResult.SYNTAX_ERROR

    try:
        interpreter.interpret(statements)
    except lox.errors.LoxRuntimeError as error:
        print(error.message, file=sys.stderr)
        print(f"[line {error.token.line}]", file=sys.stderr)
        return InterpreterResult.RUNTIME_ERROR

    return InterpreterResult.OK


if __name__ == "__main__":
    main()

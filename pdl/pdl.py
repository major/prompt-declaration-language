import argparse
import json
from typing import Any, Optional, TypedDict

import yaml
from pydantic.json_schema import models_json_schema

from . import pdl_interpreter
from .pdl_ast import (
    LocationType,
    PdlBlock,
    PdlBlocks,
    Program,
    RoleType,
    ScopeType,
    empty_block_location,
)
from .pdl_interpreter import InterpreterState, process_prog
from .pdl_parser import parse_file, parse_str


class InterpreterConfig(TypedDict, total=False):
    """Configuration parameters of the PDL interpreter."""

    yield_output: bool
    """Print the program messages during the execution.
    """
    batch: int
    """Execution type:
         - 0: streaming
         - 1: non-streaming
    """
    role: RoleType
    """Default role.
    """


def exec_program(
    prog: Program,
    config: Optional[InterpreterConfig] = None,
    scope: Optional[ScopeType] = None,
    loc: Optional[LocationType] = None,
):
    """Execute a PDL program given as a value of type `pdl.pdl_ast.Program`.

    Args:
        prog: Program to execute.
        config: Interpreter configuration. Defaults to None.
        scope: Environment defining the initial variables in scope to execute the program. Defaults to None.
        loc: Source code location mapping. Defaults to None.

    Returns:
        Return the final result.
    """
    config = config or {}
    state = InterpreterState(**config)
    scope = scope or {}
    loc = loc or empty_block_location
    result = process_prog(state, scope, prog, loc)
    return result


def exec_dict(
    prog: dict[str, Any],
    config: Optional[InterpreterConfig] = None,
    scope: Optional[ScopeType] = None,
    loc: Optional[LocationType] = None,
):
    """Execute a PDL program given as a dictionary.

    Args:
        prog: Program to execute.
        config: Interpreter configuration. Defaults to None.
        scope: Environment defining the initial variables in scope to execute the program. Defaults to None.
        loc: Source code location mapping. Defaults to None.

    Returns:
        Return the final result.
    """
    program = Program.model_validate(prog)
    result = exec_program(program, config, scope, loc)
    return result


def exec_str(
    prog: str,
    config: Optional[InterpreterConfig] = None,
    scope: Optional[ScopeType] = None,
):
    """Execute a PDL program given as YAML string.

    Args:
        prog: Program to execute.
        config: Interpreter configuration. Defaults to None.
        scope: Environment defining the initial variables in scope to execute the program. Defaults to None.

    Returns:
        Return the final result.
    """
    program, loc = parse_str(prog)
    result = exec_program(program, config, scope, loc)
    return result


def exec_file(
    prog: str,
    config: Optional[InterpreterConfig] = None,
    scope: Optional[ScopeType] = None,
):
    """Execute a PDL program given as YAML file.

    Args:
        prog: Program to execute.
        config: Interpreter configuration. Defaults to None.
        scope: Environment defining the initial variables in scope to execute the program. Defaults to None.

    Returns:
        Return the final result.
    """
    program, loc = parse_file(prog)
    result = exec_program(program, config, scope, loc)
    return result


def main():
    parser = argparse.ArgumentParser("")
    parser.add_argument(
        "--schema",
        action=argparse.BooleanOptionalAction,
        help="generate PDL Json Schema",
    )
    parser.add_argument(
        "-l",
        "--log",
        help="log file",
    )

    parser.add_argument(
        "-f",
        "--data_file",
        help="initial scope data file",
    )

    parser.add_argument(
        "-d",
        "--data",
        help="scope data",
    )

    parser.add_argument("-o", "--output", help="output file")
    parser.add_argument(
        "-m", "--trace", help="output trace for live document", choices=["json", "yaml"]
    )
    parser.add_argument("--json", help="json file")
    parser.add_argument("--yaml", help="yaml file")
    parser.add_argument("pdl", nargs="?", help="pdl file", type=str)

    args = parser.parse_args()
    if args.schema:
        schema, top_level_schema = models_json_schema(
            [
                (Program, "validation"),
                (PdlBlock, "validation"),
                (PdlBlocks, "validation"),
            ],
            title="PDL Schemas",
        )
        top_level_schema["anyOf"] = list(schema.values())
        print(json.dumps(top_level_schema, indent=2))
    if args.pdl is None:
        return

    initial_scope = {}
    if args.data_file is not None:
        with open(args.data_file, "r", encoding="utf-8") as scope_fp:
            initial_scope = yaml.safe_load(scope_fp)
    if args.data is not None:
        initial_scope = initial_scope | yaml.safe_load(args.data)

    pdl_interpreter.generate(
        args.pdl,
        args.log,
        initial_scope,
        args.trace,
        args.output,
    )


if __name__ == "__main__":
    main()

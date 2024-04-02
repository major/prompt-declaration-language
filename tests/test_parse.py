from pdl.pdl.pdl_ast import Program  # pyright: ignore
from pdl.pdl.pdl_interpreter import empty_scope  # pyright: ignore
from pdl.pdl.pdl_interpreter import process_block  # pyright: ignore

regex_data = {
    "description": "Parsing using regex",
    "parse": {"first_name": "str", "last_name": "str"},
    "from": "Malcolm Reynolds",
    "with": "(?P<first_name>\\w+) (?P<last_name>\\w+)",
    "parser": "regex",
}


def test_model():
    log = []
    data = Program.model_validate(regex_data)
    result, document, _, _ = process_block(log, empty_scope, data.root)
    assert result == {"first_name": "Malcolm", "last_name": "Reynolds"}
    assert document == '{"first_name": "Malcolm", "last_name": "Reynolds"}'

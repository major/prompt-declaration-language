import json
import os
import types
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv
from genai.credentials import Credentials
from genai.model import Model
from genai.schemas import GenerateParams

from . import pdl_ast, ui
from .pdl_ast import (
    ApiBlock,
    Block,
    CodeBlock,
    ContainsCondition,
    EndsWithCondition,
    GetBlock,
    IfBlock,
    ModelBlock,
    Program,
    RepeatsBlock,
    RepeatsUntilBlock,
    SequenceBlock,
    ValueBlock,
)
from .pdl_dumper import dump_yaml

# from .pdl_dumper import dump_yaml, dumps_json, program_to_dict

DEBUG = False

load_dotenv()
GENAI_KEY = os.getenv("GENAI_KEY")
GENAI_API = os.getenv("GENAI_API")


def generate(pdl, logging, mode, output):
    scope = {}
    if logging is None:
        logging = "log.txt"
    with open(pdl, "r", encoding="utf-8") as infile:
        with open(logging, "w", encoding="utf-8") as logfile:
            data = yaml.safe_load(infile)
            prog = Program.model_validate(data)
            log = []
            result = ""
            try:
                result = process_block(log, scope, "", prog.root)
            finally:
                print(result)
                print("\n")
                for prompt in log:
                    logfile.write(prompt)
                if mode == "html":
                    if output is None:
                        output = str(Path(pdl).with_suffix("")) + "_result.html"
                    ui.render(prog.root, output)
                if mode == "json":
                    if output is None:
                        output = str(Path(pdl).with_suffix("")) + "_result.json"
                    with open(output, "w", encoding="utf-8") as fp:
                        json.dump(prog.model_dump(), fp)
                if mode == "yaml":
                    if output is None:
                        output = str(Path(pdl).with_suffix("")) + "_result.yaml"
                    with open(output, "w", encoding="utf-8") as fp:
                        dump_yaml(prog.model_dump(), stream=fp)


def process_block(log, scope, document: str, block: pdl_ast.BlockType) -> str:
    result = ""
    match block:
        case ModelBlock():
            result = call_model(log, scope, document, block)
        case CodeBlock(lan="python", code=code):
            result = call_python(log, scope, code)
        case CodeBlock(lan=l):
            error(f"Unsupported language: {l}")
            result = ""
        case GetBlock():
            result = get_var(block, scope)
        case ValueBlock(value=v):
            result = str(v)
        case ApiBlock():
            result = call_api(log, scope, block)
        case SequenceBlock():
            result += process_prompts(log, scope, document, block.prompts)
        case IfBlock(condition=cond):
            if condition(log, scope, document, cond):
                result += process_prompts(log, scope, document, block.prompts)
        case RepeatsBlock(repeats=n):
            for _ in range(n):
                result += process_prompts(log, scope, document + result, block.prompts)
        case RepeatsUntilBlock(repeats_until=cond):
            result += process_prompts(log, scope, document, block.prompts)
            while not condition(log, scope, document, cond):
                result += process_prompts(log, scope, document + result, block.prompts)
    block.result = result
    if block.assign is not None:
        var = block.assign
        # scope[var] = "".join(result)
        scope[var] = result
        debug("Storing model result for " + var + ": " + str(result))
    if block.show_result is False:
        result = ""
    return result


def call_api(log, scope, block: pdl_ast.ApiBlock) -> str:
    inputs = process_prompt(log, scope, "", block.input)
    input_str = "".join(inputs)
    input_str = block.url + input_str
    append_log(log, "API Input", True)
    append_log(log, input_str, False)
    response = requests.get(input_str)
    result = str(response.json())
    debug(result)
    append_log(log, "API Output", True)
    append_log(log, result, False)
    return result


def process_prompts(log, scope, document: str, prompts) -> str:
    result: str = ""
    for prompt in prompts:
        result += process_prompt(log, scope, document + result, prompt)
    return result


def process_prompt(log, scope, document, prompt) -> str:
    if isinstance(prompt, str):
        result = prompt
        append_log(log, "Prompt", True)
        append_log(log, prompt, False)
    elif isinstance(prompt, Block):
        result = process_block(log, scope, document, prompt)
    else:
        assert False
    return result


def append_log(log, somestring, doc):
    if doc:
        somestring = "**********  " + somestring + "  **********"
    log.append(somestring + "\n")


def debug(somestring):
    if DEBUG:
        print("******")
        print(somestring)
        print("******")


def error(somestring):
    print("***Error: " + somestring)


def get_var(block, scope) -> str:
    match block:
        case GetBlock(get=var):
            return str(scope[var])
        case _:
            return ""


def condition(log, scope, document, cond: pdl_ast.ConditionType):
    match cond:
        case EndsWithCondition(ends_with=args):
            return ends_with(log, scope, document, args)
        case ContainsCondition(contains=args):
            return contains(log, scope, document, args)
    return False


def ends_with(log, scope, document, cond: pdl_ast.EndsWithArgs):
    arg0 = "".join(process_prompt(log, scope, document, cond.arg0))
    return arg0.endswith(cond.arg1)


def contains(log, scope, document, cond: pdl_ast.ContainsArgs):
    arg0 = "".join(process_prompt(log, scope, document, cond.arg0))
    return cond.arg1 in arg0


def call_model(log, scope, document, block: pdl_ast.ModelBlock) -> str:
    model_input = ""
    stop_sequences = []
    include_stop_sequences = False

    if block.input is not None:  # If not set to document, then input must be a block
        model_input = process_prompt(log, scope, "", block.input)
        # model_input = "".join(inputs)
    if model_input == "":
        # model_input = "".join(document)
        model_input = document
    if block.stop_sequences is not None:
        stop_sequences = block.stop_sequences
    if block.include_stop_sequences is not None:
        include_stop_sequences = block.include_stop_sequences

    if GENAI_API is None:
        error("Environment variable GENAI_API must be defined")
        genai_api = ""
    else:
        genai_api = GENAI_API
    if GENAI_KEY is None:
        error("Environment variable GENAI_KEY must be defined")
        genai_key = ""
    else:
        genai_key = GENAI_KEY
    creds = Credentials(genai_key, api_endpoint=genai_api)
    params = None
    if stop_sequences != []:
        params = GenerateParams(  # pyright: ignore
            decoding_method="greedy",
            max_new_tokens=200,
            min_new_tokens=1,
            # stream=False,
            # temperature=1,
            # top_k=50,
            # top_p=1,
            repetition_penalty=1.07,
            include_stop_sequence=include_stop_sequences,
            stop_sequences=stop_sequences,
        )
    else:
        params = GenerateParams(  # pyright: ignore
            decoding_method="greedy",
            max_new_tokens=200,
            min_new_tokens=1,
            # stream=False,
            # temperature=1,
            # top_k=50,
            # top_p=1,
            repetition_penalty=1.07,
        )

    debug("model input: " + model_input)
    append_log(log, "Model Input", True)
    append_log(log, model_input, False)
    model = Model(block.model, params=params, credentials=creds)
    response = model.generate([model_input])
    gen = response[0].generated_text
    debug("model output: " + gen)
    append_log(log, "Model Output", True)
    append_log(log, gen, False)
    return gen


def call_python(log, scope, code) -> str:
    code_str = get_code_string(log, scope, code)
    my_namespace = types.SimpleNamespace()
    append_log(log, "Code Input", True)
    append_log(log, code_str, False)
    exec(code_str, my_namespace.__dict__)
    result = str(my_namespace.result)
    append_log(log, "Code Output", True)
    append_log(log, result, False)
    return result


def get_code_string(log, scope, code) -> str:
    code_l = process_prompts(log, scope, "", code)
    code_s = "".join(code_l)
    debug("code string: " + code_s)
    return code_s
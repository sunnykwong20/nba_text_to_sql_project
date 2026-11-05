import sqlite3
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
import json

import logging

from helpers import get_full_schema_ddl, get_schema_ddl_for_tables, run_sql
from state import AgentState

from pathlib import Path
import os
from dotenv import load_dotenv

from prompts import (
    SCHEMA_LINKING_PROMPT,
    SchemaLinkingResult,
    generate_sql_prompt_no_error,
    generate_sql_prompt_error,
    GenerateSQLResult,
    format_response_prompt,
    FormatResponseResult,
    ScopeResult
    ,SCOPE_PROMPT
)

## Nodes.py: Makes all Nodes needed for the AI Agent

## sets up logger
logging.basicConfig(level=logging.WARNING)
text_to_sql_logger = logging.getLogger(__name__)

# Gets all paths
DB_PATH = "data/nba.sqlite"
script_dir = Path(__file__).resolve().parent
env_path = script_dir.parent / '.env'

load_dotenv(dotenv_path=env_path)

anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
llm = ChatAnthropic(model="claude-haiku-5-5",anthropic_api_key = anthropic_api_key)


check_scope_llm = llm.with_structured_output(ScopeResult)

def check_scope(state: AgentState) -> dict: 

    ### Checks if the question is in scope of being answered by the LLM

    question = state['question']

    ### Gets table list
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    sql_str = "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    table_list = [row['name'] for row in run_sql(cursor=cursor,sql_str = sql_str)]
    tables_list_text = "\n".join(table_list)

    conn.close()

    prompt = SCOPE_PROMPT.format(question=question, tables_list = tables_list_text)
    result = check_scope_llm.invoke(prompt) 

    return {"in_scope": result.in_scope, "scope_reason":result.scope_reason}


schema_linking_llm = llm.with_structured_output(SchemaLinkingResult)

def identify_schema(state: AgentState) -> dict:

    ## Gathers tables and variables needed. Guesses the appropiate response format for the Agent (Narrative or Table)

    question = state["question"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    schema = get_full_schema_ddl(cursor)
    conn.close()

    prompt = SCHEMA_LINKING_PROMPT.format(schema=schema, question=question)
    result = schema_linking_llm.invoke(prompt)

    return {"tables": result.tables, "variables": result.variables, "response_format": result.response_format}

generate_sql_llm = llm.with_structured_output(GenerateSQLResult)


def generate_sql(state: AgentState) -> dict: 

    ## Generates the SQL text based on the question and variables and tables needed 

    ## No safety / guard rail checks yet. This is for later version

    ## Gathers states variables needed
    question = state["question"]
    variables = state["variables"]
    tables = state["tables"]
    attempts = state['attempts']
    error = state['error']
    prev_sql = state['sql']


    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    ## Gets the schema needed for only the tables needed
    schema = get_schema_ddl_for_tables(cursor, tables)

    conn.close()

    ## Checks if there is an error. This will impact what is in the next node
    if error:
        prompt = generate_sql_prompt_no_error.format(schema=schema, question=question, variables = variables)
        result = generate_sql_llm.invoke(prompt)

    else: 
        prompt = generate_sql_prompt_error.format(schema=schema, question=question, variables = variables, error = error, query = prev_sql)
        result = generate_sql_llm.invoke(prompt)
        

    return {"sql": result.sql, "attempts": attempts + 1}

def execute_sql(state: AgentState) -> dict:

    ## Takes the sql produced and runs it against the sqlite database

    sql = state['sql']

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try: 
        result = run_sql(cursor,sql)
        return {"result": result, "error": None}
    except sqlite3.Error as e:
        return {"error":str(e)}
    finally:
        conn.close()

format_response_llm = llm.with_structured_output(FormatResponseResult)

def format_response(state: AgentState)-> dict:

    ## Makes the AI response based on the result. 
    ## This only runs if the response_format is narrative.

    question = state['question']
    result = state['result']

    prompt = format_response_prompt.format(question=question, result = result)
    result = format_response_llm.invoke(prompt)

    return {"response":result.response}

def refuse_out_of_scope(state:AgentState) -> dict:

    ## Sets what happened in the case the AI Agent refuses to answer a question
    ## This only gets triggered if the question is out of scope of what the AI Agent can answer. 

    question = state['question']
    scope_reason = state['scope_reason']

    text_to_sql_logger.warning("refuse out of scope fired: question=%r reason =%r", question, scope_reason)

    return {"response":f"I wasn't able to answer the question '{question}' because it is out of scope. This is the reason: '{scope_reason}' Please try again.", "refused":True}

def give_up(state: AgentState)-> dict:

    ## Sets what happened in the case the AI Agent wants to give up. 
    ## This only gets triggered if more than 3 tries happened and it still returns an error

    question = state['question']
    sql = state['sql']
    error = state['error']

    text_to_sql_logger.warning("give_up fired: question=%r sql=%r error=%r", question, sql, error)

    return {"response":f"I wasn't able to answer the question '{question}' after a few tries. Please try again.","refused":True}
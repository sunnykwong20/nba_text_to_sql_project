from langgraph.graph import StateGraph, START, END

from nodes import (
    identify_schema,
    generate_sql, 
    execute_sql, 
    format_response, 
    give_up,
    refuse_out_of_scope,
    check_scope
)

from state import (
    AgentState
)

### graph.py: Combines all nodes into a single AI Agent. 

### Branch 1: After checking_scope node, figure out what to do based on if it's in scope or not
### if it is in scope, move on to identify_schema
### else, move on to refuse_out_of_scope
def route_after_check_scope(state: AgentState):
    in_scope = state['in_scope']

    if in_scope:
        return "identify_schema"
    else:
        return "refuse_out_of_scope"

### Branch 2: After execute_sql node, do the following
### If there is an error, but attempts is less than 3, go back to generate sql
### IF there is an error, but attempts at 3, give up
### If there is no error, but response_format is narrative, move on to format_response
### If there is no error, but response_format is table, END the agent (it will automatically return the table)

def route_after_execute(state: AgentState):
    response_format = state['response_format']
    error = state['error']
    attempts = state['attempts']

    if error: 
        if attempts < 3: 
            print(f"generate sql: attempt # {attempts}")
            return "generate_sql"

        else:
            print(f"give up: attempt # {attempts}")
            return "give_up"
    else:
        if response_format == 'Narrative':
            return "format_response"
        else:
            return "END"

text_to_sql_builder = StateGraph(AgentState)

## Adds necessary nodes
text_to_sql_builder.add_node("check_scope",check_scope)
text_to_sql_builder.add_node("identify_schema",identify_schema)
text_to_sql_builder.add_node("generate_sql",generate_sql)
text_to_sql_builder.add_node("execute_sql",execute_sql)
text_to_sql_builder.add_node("format_response",format_response)
text_to_sql_builder.add_node("give_up",give_up)
text_to_sql_builder.add_node("refuse_out_of_scope",refuse_out_of_scope)

## Makes the start
text_to_sql_builder.add_edge(START,"check_scope")

## Makes edges
text_to_sql_builder.add_edge("identify_schema","generate_sql")
text_to_sql_builder.add_edge("generate_sql","execute_sql")

## Makes conditional edges

### Conditional edge 1: makes conditional adge for check_scope
text_to_sql_builder.add_conditional_edges(
        "check_scope" ## source node 
        , route_after_check_scope ## function used to define the next path
        , {                      # Path map: maps router output -> node name
            "identify_schema": "identify_schema"
            , "refuse_out_of_scope": "refuse_out_of_scope"
        }
)


### Conditional edge 2: makes conditional adge for execute_sql
text_to_sql_builder.add_conditional_edges(
        "execute_sql" ## source node 
        , route_after_execute ## function used to define the next path
        , {                      # Path map: maps router output -> node name
            "generate_sql": "generate_sql"
            , "give_up": "give_up"
            , "format_response":"format_response"
            , "END": END # If the result is the table, end immediately
        }
)


## Makes the end
text_to_sql_builder.add_edge("format_response",END)
text_to_sql_builder.add_edge("give_up",END)
text_to_sql_builder.add_edge("refuse_out_of_scope",END)

graph = text_to_sql_builder.compile()

def run(question):
    initial_state = {
        "question": question,
        "sql": None,
        "tables": None,
        "variables": None,
        "result": None,
        "attempts": 0,
        "error": None,
        "response_format": None,
        "response": None,
        "in_scope": None, 
        "scope_reason":None,
        "refused": False
    }
    final_state = graph.invoke(initial_state)
    print(f"\n=== {question!r} ===")
    for key, value in final_state.items():
        print(f"  {key}: {value}")
    return final_state
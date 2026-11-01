from langgraph.graph import StateGraph, START, END

from nodes import (
    identify_schema,
    generate_sql, 
    execute_sql, 
    format_response, 
    give_up
)

from state import (
    AgentState

)

### graph.py: Combines all nodes into a single AI Agent. 

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
text_to_sql_builder.add_node("identify_schema",identify_schema)
text_to_sql_builder.add_node("generate_sql",generate_sql)
text_to_sql_builder.add_node("execute_sql",execute_sql)
text_to_sql_builder.add_node("format_response",format_response)
text_to_sql_builder.add_node("give_up",give_up)

## Makes the start
text_to_sql_builder.add_edge(START,"identify_schema")

## Makes edges
text_to_sql_builder.add_edge("identify_schema","generate_sql")
text_to_sql_builder.add_edge("generate_sql","execute_sql")

## Makes conditional edge
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
    }
    final_state = graph.invoke(initial_state)
    print(f"\n=== {question!r} ===")
    for key, value in final_state.items():
        print(f"  {key}: {value}")
    return final_state
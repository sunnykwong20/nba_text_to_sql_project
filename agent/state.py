from typing import TypedDict, Optional, Annotated
import operator


## Defines the State for the Text to SQL agent

class AgentState(TypedDict):
    question: str 
    sql: Optional[str]
    tables: Optional[list]
    variables: Optional[list]
    result: Optional[list]
    attempts: int 
    error: Optional[str]
    response: Optional[str]
    response_format: Optional[str]
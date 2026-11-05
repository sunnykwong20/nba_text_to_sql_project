from typing import TypedDict, Optional, Annotated
import operator


## Defines the State for the Text to SQL agent

class AgentState(TypedDict):
    in_scope: bool | None 
    scope_reason: str | None
    refused: bool
    question: str 
    sql: Optional[str]
    tables: Optional[list]
    variables: Optional[list]
    result: Optional[list]
    attempts: int 
    error: Optional[str]
    response: Optional[str]
    response_format: Optional[str]
from typing import List, Tuple, Annotated, TypedDict
import operator


class PlanExecute(TypedDict):
    input: str
    plan: List[str]
    past_steps: Annotated[List[Tuple], operator.add]
    intermediate_steps: Annotated[List[Tuple], operator.add]
    chat_history: list
    response: str
    feedback_task: str
    gave_feedback: bool
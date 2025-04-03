from langchain import hub
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

from typing import List, Tuple, Annotated, TypedDict
import operator

import os
import json

from services.llm_utils import el, Plan
from services.ld_utils import execute, post_process


lang = 'en'
openai_model_name = "gpt-4o-2024-05-13" 

### Initialize embeddings
model_name = "intfloat/multilingual-e5-large"
model_kwargs = {'device': 'cpu'}
encode_kwargs = {'normalize_embeddings': False}
hf = HuggingFaceEmbeddings(
    model_name=model_name,
    model_kwargs=model_kwargs,
    encode_kwargs=encode_kwargs
)
### END Initialize embeddings

### Load ICL VDB
icl_file_path = f"./data/datasets/qald_9_plus_train_dbpedia_{lang}.json"
with open(icl_file_path, "r", encoding='utf-8') as f:
    json_data = json.load(f)

icl_faiss_vdb = icl_file_path.split("/")[-1].replace(".json", "")
icl_faiss_vdb_path = os.path.join(".", "data", "experience-pool", icl_faiss_vdb)
return_N = 5
icl_db = FAISS.load_local(icl_faiss_vdb_path, hf, allow_dangerous_deserialization = True)
### END Load ICL VDB

tools = [el]

system_prompt = {
    "en": """You are an intelligent Knowledge Graph-based Question Answering system.""",
}

last_task = {
    "en": """Make sure that the query is formatted correctly. No extra text. No markdown. Just plain SPARQL query.
Determine whether to output a URI (SELECT ?uri), number (COUNT), date, boolean (ASK), string (SELECT ?label)
DON'T USE "SERVICE wikibase:label"
"""
}

planner_prompt_dct = {
    "en": """For the given objective, come up with a simple step by step plan to write a SPARQL query. 
This plan should involve individual tasks (e.g., **named entity linking**, **relation linking**), that if executed correctly will yield the correct SPARQL.
Do not add any superfluous steps.
Be very specific when defining the steps e.g.,: "Link the following named entities: Name Surname, ..."
The result of the final step should be the final SPARQL query over DBpedia. Don't propose to execute the query.
At the end step you MUST output exactly **ONE** SPARQL query over DBpedia string **without extra text or markdown**.

Objective: {objective}

Formatting instructions:
Just output the valid JSON with the list of strings as follows: {{"plan": ["step1", "step2", ...]}} Put every step to the list
Only output VALID JSON without escape chars: {{"plan": ["step1", "step2", ...]}}
Make sure that the output is VALID JSON"""
}

feedback_step_dict = {
    "en": """
    This is feedback to your generated SPARQL query produced by executing it on a triplestore.
    Please rework your query if neccessary.

    Initial question: {question}
    Your query: 
    {query}

    --- Start triplestore response ---
    {feedback}
    --- End triplestore response ---

    {last_task}
    """
  }


plan_llm = ChatOpenAI(model=openai_model_name, temperature=0).with_structured_output(Plan)

class PlanExecute(TypedDict):
    input: str
    plan: List[str]
    past_steps: Annotated[List[Tuple], operator.add]
    intermediate_steps: Annotated[List[Tuple], operator.add]
    chat_history: list
    response: str
    feedback_task: str
    gave_feedback: bool

def plan_step(state: PlanExecute):
    try:
        plan = plan_llm.invoke(planner_prompt_dct[lang].format(objective=state["input"]))
        return {"plan": plan.steps + [last_task]}
    except Exception as e:
        plan = [last_task]
        return {"plan": plan}
    
def execute_step(state: PlanExecute):
    if state["gave_feedback"]:
        task = state["feedback_task"]
    else:
        task = state["plan"].pop(0)

    try:
        agent_response = agent_executor.invoke({"input": task, "chat_history": state['chat_history']})
        state['chat_history'].append(AIMessage(agent_response['output'])) # update chat history
    except Exception as e:
        state['chat_history'].append(AIMessage(str(e)))
        agent_response = {"output": str(e), "intermediate_steps": "No"}

    return {
        "past_steps": [task, agent_response["output"]],
        "intermediate_steps": [task, agent_response["intermediate_steps"]],
        "gave_feedback": state["gave_feedback"]
    }

def feedback_step(state: PlanExecute):
    task = feedback_step_dict[lang]
    try:
        feedback = execute(state['chat_history'][-1].content)
        if type(feedback) == dict and "error" not in feedback.keys():
            feedback = json.dumps(feedback['results']['bindings'][:3])
    except Exception as e:
        feedback = str(e)
    
    return {
        "feedback_task": str(task.format(question=state["input"], query=state['chat_history'][-1].content, feedback=feedback, last_task=last_task)),
        "gave_feedback": True
    }

def feedback_router(state: PlanExecute):
    if len(state["plan"]) > 0:
        return "agent"
    if len(state["plan"]) == 0 and state["gave_feedback"] == False:
        return "feedback"
    if len(state["plan"]) == 0 and state["gave_feedback"] == True:
        return END

prompt = hub.pull("hwchase17/openai-functions-agent")

# Choose the LLM that will drive the agent
llm = ChatOpenAI(model=openai_model_name)

# Construct the OpenAI Functions agent
agent_runnable = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent_runnable, tools=tools, verbose=True, return_intermediate_steps=True
)

workflow = StateGraph(PlanExecute)

# Add the plan node
workflow.add_node("planner", plan_step)

# Add the execution step
workflow.add_node("agent", execute_step)

# Add the feedback step
workflow.add_node("feedback", feedback_step)

workflow.set_entry_point("planner")

# From plan we go to agent
workflow.add_edge("planner", "agent")

workflow.add_conditional_edges(
    "agent",
    # Next, we pass in the function that will determine which node is called next.
    feedback_router,
    {
        "feedback": "feedback",
        "agent": "agent",
        END: END
    }
)

# From feedback we go to agent
workflow.add_edge("feedback", "agent")


app = workflow.compile()


def generate_sparql(input_question: str) -> str:
    results = icl_db.similarity_search_with_score(input_question, k=return_N)

    example = "--- Successful example for in context learning ---"

    for result in results[:return_N]:
        idx = result[0].metadata['seq_num'] - 1
        question = json_data[idx]["question"]
        sparql = json_data[idx]["sparql"]

        example += f"""

Input: {question}
Output: {sparql}

"""
        
        example += "--- End example ---"

    agent_result = app.invoke(
        {"input": input_question, "chat_history": [SystemMessage(content=f"""{system_prompt[lang]}      
        {example}""")],
        "gave_feedback": False}
    )
  
    sparql_result = agent_result['chat_history'][-1].content

    query = post_process(sparql_result)

    return query

if __name__ == "__main__":   
  text = "Who is the author of the book 'The Great Gatsby'?"         
  
  query = generate_sparql(text)
        
  print(f"Input: {text}")
  print(f"Output: {query}")

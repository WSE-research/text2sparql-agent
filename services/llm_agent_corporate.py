from langchain import hub
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

from typing import List

import os
import json

from services.llm_utils import el, Plan
from services.ld_utils import execute, post_process
from model.agent import PlanExecute
from prompts.corporate import (
    system_prompt,
    last_task,
    planner_prompt_dct,
    feedback_step_dict
)


class LLMAgentCorporate:
    """
    Implementation of an LLM agent that converts natural language to SPARQL over corporate Eccenca knowledge graph.
    This will be replaced with an actual LLM implementation later.
    """
    
    def __init__(
            self,
            openai_model_name: str = "gpt-4o-2024-05-13",
            embedding_model_name: str = "intfloat/multilingual-e5-large",
            return_N: int = 5,
            tools: List = [el],
            lang: str = "en"
        ):
        """Initialize the LLM agent with any required configurations"""
        self.model_name = "text-to-sparql-mock"
        self.sparql_endpoint = "http://141.57.8.18:40201/corporate/sparql"
        self.lang = lang
        self.embedding_model_name = embedding_model_name
        self.openai_model_name = openai_model_name

        ### START Initialize embeddings
        model_kwargs = {'device': 'cpu'}
        encode_kwargs = {'normalize_embeddings': False}
        self.hf_embeddings = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )
        ### END Initialize embeddings

        ### START Load ICL VDB
        icl_file_path = f"./data/datasets/qald_9_plus_train_dbpedia_{lang}.json"
        with open(icl_file_path, "r", encoding='utf-8') as f:
            self.icl_json_data = json.load(f)

        icl_faiss_vdb = icl_file_path.split("/")[-1].replace(".json", "")
        icl_faiss_vdb_path = os.path.join(".", "data", "experience-pool", icl_faiss_vdb)
        self.return_N = return_N
        self.icl_db = FAISS.load_local(icl_faiss_vdb_path, self.hf_embeddings, allow_dangerous_deserialization = True)
        ### END Load ICL VDB

        ### START Initialize agent
        self.tools = tools
        self.plan_llm = ChatOpenAI(
            model=openai_model_name,
            temperature=0
        ).with_structured_output(Plan)

        prompt = hub.pull("hwchase17/openai-functions-agent")

        # Choose the LLM that will drive the agent
        self.llm = ChatOpenAI(model=openai_model_name)

        # Construct the OpenAI Functions agent
        self.agent_runnable = create_tool_calling_agent(self.llm, tools, prompt)

        self.agent_executor = AgentExecutor(
            agent=self.agent_runnable, tools=tools, verbose=True, return_intermediate_steps=True
        )

        self.app = None

        ### EMD Initialize agent

    def _plan_step(self, state: PlanExecute):
        try:
            plan = self.plan_llm.invoke(planner_prompt_dct[self.lang].format(objective=state["input"]))
            return {"plan": plan.steps + [last_task]}
        except Exception as e:
            plan = [last_task]
            return {"plan": plan}
        
    def _execute_step(self, state: PlanExecute):
        if state["gave_feedback"]:
            task = state["feedback_task"]
        else:
            task = state["plan"].pop(0)

        try:
            agent_response = self.agent_executor.invoke({"input": task, "chat_history": state['chat_history']})
            state['chat_history'].append(AIMessage(agent_response['output'])) # update chat history
        except Exception as e:
            state['chat_history'].append(AIMessage(str(e)))
            agent_response = {"output": str(e), "intermediate_steps": "No"}

        return {
            "past_steps": [task, agent_response["output"]],
            "intermediate_steps": [task, agent_response["intermediate_steps"]],
            "gave_feedback": state["gave_feedback"]
        }

    def _feedback_step(self, state: PlanExecute):
        task = feedback_step_dict[self.lang]
        try:
            feedback = execute(query=state['chat_history'][-1].content, endpoint_url=self.sparql_endpoint)
            if type(feedback) == dict and "error" not in feedback.keys():
                feedback = json.dumps(feedback['results']['bindings'][:3])
        except Exception as e:
            feedback = str(e)
        
        return {
            "feedback_task": str(task.format(question=state["input"], query=state['chat_history'][-1].content, feedback=feedback, last_task=last_task)),
            "gave_feedback": True
        }
    
    def _init_workflow(self):
        workflow = StateGraph(PlanExecute)

        # Add the plan node
        workflow.add_node("planner", self._plan_step)

        # Add the execution step
        workflow.add_node("agent", self._execute_step)

        # Add the feedback step
        workflow.add_node("feedback", self._feedback_step)

        workflow.set_entry_point("planner")

        # From plan we go to agent
        workflow.add_edge("planner", "agent")

        workflow.add_conditional_edges(
            "agent",
            # Next, we pass in the function that will determine which node is called next.
            self._feedback_router,
            {
                "feedback": "feedback",
                "agent": "agent",
                END: END
            }
        )

        # From feedback we go to agent
        workflow.add_edge("feedback", "agent")


        self.app = workflow.compile()

        return True

    def _feedback_router(self, state: PlanExecute):
        if len(state["plan"]) > 0:
            return "agent"
        if len(state["plan"]) == 0 and state["gave_feedback"] == False:
            return "feedback"
        if len(state["plan"]) == 0 and state["gave_feedback"] == True:
            return END
  
    def generate_sparql(self, input_question: str) -> str:
        """
        Convert a natural language question to a SPARQL query
        
        Args:
            question: The natural language question
            dataset: The dataset URL to query against
            
        Returns:
            A SPARQL query string
        """
        if self.app is None:
            self._init_workflow()

        results = self.icl_db.similarity_search_with_score(input_question, k=self.return_N)

        example = "--- Successful example for in context learning ---"

        for result in results[:self.return_N]:
            idx = result[0].metadata['seq_num'] - 1
            question = self.icl_json_data[idx]["question"]
            sparql = self.icl_json_data[idx]["sparql"]

            example += f"""

    Input: {question}
    Output: {sparql}

    """
            
            example += "--- End example ---"

        agent_result = self.app.invoke(
            {"input": input_question, "chat_history": [SystemMessage(content=f"""{system_prompt[self.lang]}      
            {example}""")],
            "gave_feedback": False}
        )
    
        sparql_result = agent_result['chat_history'][-1].content

        generated_query = post_process(sparql_result)

        return generated_query




if __name__ == "__main__":   
    dbpedia_agent = LLMAgentCorporate(
        openai_model_name="gpt-4o-2024-05-13",
        embedding_model_name="intfloat/multilingual-e5-large",
        return_N=5,
        tools=[el],
        lang="en"
    )

    text = "Who is the author of the book 'The Great Gatsby'?"         

    query = dbpedia_agent.generate_sparql(text)
        
    print(f"Input: {text}")
    print(f"Output: {query}")

from fastapi import FastAPI, HTTPException
from typing import List
# from services.llm_agent import LLMAgent
from services.llm_agent_dbpedia import LLMAgentDBpedia
from services.llm_agent_corporate import LLMAgentCorporate


__version__ = "0.1.0"

app = FastAPI(
    title="KGQAgent Text2SPARQL API",
    description="API for converting natural language questions to SPARQL queries using LLMs.",
    version=__version__
)

KNOWN_DATASETS: List[str] = [
    "https://text2sparql.aksw.org/2025/dbpedia/",
    "https://text2sparql.aksw.org/2025/corporate/"
]

dbpedia_agent = LLMAgentDBpedia()
corporate_agent = LLMAgentCorporate()

@app.get("/api")
async def get_answer(question: str, dataset: str):
    """
    Process a natural language question and convert it to SPARQL query for the specified dataset.
    
    Args:
        question: The natural language question to process
        dataset: The dataset URL to query against
        
    Returns:
        JSON with the dataset, original question, and generated SPARQL query
    """
    if dataset not in KNOWN_DATASETS:
        raise HTTPException(status_code=404, detail="Unknown dataset. Please use one of the known datasets.")
    
    if "dbpedia" in dataset:
        sparql_query = dbpedia_agent.generate_sparql(question)
    elif "corporate" in dataset:
        sparql_query = corporate_agent.generate_sparql(question)
    else:
        raise HTTPException(status_code=404, detail="Unknown dataset. Please use one of the known datasets.")
    
    return {
        "dataset": dataset,
        "question": question,
        "query": sparql_query
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

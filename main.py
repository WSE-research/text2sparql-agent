from fastapi import FastAPI, HTTPException
from typing import List
# from services.llm_agent import LLMAgent
from services import llm_agent_dbpedia


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

# llm_agent = LLMAgent()

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
    
    # Call the LLM agent to generate SPARQL
    sparql_query = llm_agent_dbpedia.generate_sparql(question)
    
    return {
        "dataset": dataset,
        "question": question,
        "query": sparql_query
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

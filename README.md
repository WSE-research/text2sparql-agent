# TEXT2SPARQL Agent

A FastAPI service that converts natural language questions to SPARQL queries using LLM technology.

## Setup

1. Clone this repository
2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```
3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the API

Start the FastAPI server:

```bash
uvicorn main:app --reload
```

The API will be available at http://localhost:8000

## API Usage

### Convert text question to SPARQL

```
GET /?question=Who is the president of the United States?&dataset=https://text2sparql.aksw.org/2025/dbpedia/
```

Parameters:
- `question`: The natural language question
- `dataset`: One of the supported dataset URLs

Example response:
```json
{
  "dataset": "https://text2sparql.aksw.org/2025/dbpedia/",
  "question": "Who is the president of the United States?",
  "query": "PREFIX dbo: <http://dbpedia.org/ontology/>\nPREFIX dbr: <http://dbpedia.org/resource/>\nSELECT ?person WHERE {\n  ?person a dbo:Person .\n  ?person ?relation ?entity .\n}"
}
```

## Supported Datasets

- `https://text2sparql.aksw.org/2025/dbpedia/`
- `https://text2sparql.aksw.org/2025/corporate/`

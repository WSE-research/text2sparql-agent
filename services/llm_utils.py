import json
import logging
import ast
import random
import requests

from typing import List

from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool



logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
logging.getLogger().setLevel(logging.INFO)

KNOWN_EAT_MAPPINGS = [
    ["http://www.w3.org/2001/XMLSchema#integer", "integer"],
    ["http://www.w3.org/2001/XMLSchema#boolean", "boolean"],
    ["http://www.w3.org/2001/XMLSchema#date", "date"],
    ["http://www.w3.org/2001/XMLSchema#dateTime", "dateTime"],
    ["http://www.w3.org/2001/XMLSchema#time", "time"],
    ["http://www.w3.org/2001/XMLSchema#string", "string", "literal"],
    ["http://www.w3.org/2001/XMLSchema#anyURI", "uri", "resource", "http://www.w3.org/2000/01/rdf-schema#Resource",
        "http://www.w3.org/2000/01/rdf-schema#List", "http://www.w3.org/2000/01/rdf-schema#Container", "http://www.w3.org/2000/01/rdf-schema#Collection", "http://www.w3.org/2000/01/rdf-schema#Bag", "http://www.w3.org/2000/01/rdf-schema#Set"],
    ["http://www.w3.org/2001/XMLSchema#double", "http://www.w3.org/2001/XMLSchema#decimal",
        "http://www.w3.org/2001/XMLSchema#float", "double", "decimal", "float"],
]

class Plan(BaseModel):
    """Plan to follow in future"""

    steps: List[str] = Field(
        description="different steps to follow, should be in sorted order"
    )
    
class NELInput(BaseModel):
    ne_list: list = Field(description="should be a list of named entities (strings) to be linked to the Knowledge Graph URIs")

class RELInput(BaseModel):
    rel_list: list = Field(description="should be a list of relations (strings) to be linked to the Knowledge Graph  URIs")

@tool("wikidata_el", args_schema=NELInput)
def el(ne_list: str) -> list:
    """Performs entity linking to Wikidata based on the provided list of named entity strings. Returns list of dict with linking candidates: [{"label": "URI"}]"""
    nel_list = []
    N = 5
    for ne in ne_list[:N]:
        entities, relations = [[], []] # search_entity(query=ne)
        falcon_relations, falcon_entities = [[], []] # falcon_rel(query=ne)
        relations += falcon_relations
        
        nel_list += entities
        nel_list += falcon_entities
        nel_list += relations

    return nel_list

def get_freebase_entities(query: str, is_relation: bool) -> list:
    """
    Make a GET request to the Freebase entity service and return the parsed response
    """
    try:
        if is_relation:
            url = f"http://141.57.8.18:9199/relations/?query={query}"
        else:
            url = f"http://141.57.8.18:9199/entities/?query={query}"
        headers = {'accept': 'application/json'}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Error fetching entities: {response.status_code}")
            return []
    except Exception as e:
        logging.error(f"Exception in get_freebase_entities: {str(e)}")
        return []

@tool("freebase_el", args_schema=NELInput)
def el_freebase(ne_list: str) -> list:
    """Performs entity linking to Freebase based on the provided list of named entity strings. Returns list of dict with linking candidates: [{"label": "URI"}]"""
    nel_list = []
    N = 5
    for ne in ne_list[:N]:
        entities = get_freebase_entities(ne, False)
        for entity in entities:
            nel_list.append({
                "label": entity.get("label", ""),
                "uri": entity.get("uri", ""),
                "score": entity.get("score", 0),
                "extra_score": entity.get("extra_score", 0)
            })

    return nel_list

@tool("freebase_rel", args_schema=RELInput)
def rel_freebase(rel_list: str) -> list:
    """Performs relation linking to Freebase based on the provided list of relations strings. Returns list of dict with linking candidates: [{"label": "URI"}]"""
    nel_list = []
    N = 5
    for rel in rel_list[:N]:
        relations = get_freebase_entities(rel, True)
        for relation in relations:
            nel_list.append({
                "label": relation.get("label", ""),
                "uri": relation.get("uri", ""),
                "score": relation.get("score", 0),
                "extra_score": relation.get("extra_score", 0)
            })

    return nel_list


def nel(ne_list: str) -> list:
    """Performs entity linking to Wikidata based on the provided list of named entity strings. Returns list of dict with linking candidates: [{"label": "URI"}]"""
    nel_list = []
    N = 5
    for ne in ne_list[:N]:
        entities, relations = [[], []] # search_entity(query=ne)
        falcon_relations, falcon_entities = [[], []] # falcon_rel(query=ne)
        relations += falcon_relations
        
        nel_list += entities
        nel_list += falcon_entities
        nel_list += relations

    return nel_list

def find_first_correct_item(results, json_data):
    for r in results:
        idx = r[0].metadata['seq_num']
        
        if json_data[idx-1]['precision'] == 1 and json_data[idx-1]['recall'] == 1:
            return idx - 1
        # TODO: check score
        
    return None

def find_random_item(results, json_data):    
    return random.randint(0, len(json_data) - 1)

def find_first_incorrect_item(results, json_data):
    for r in results:
        idx = r[0].metadata['seq_num']
        
        if json_data[idx-1]['precision'] == 0 and json_data[idx-1]['recall'] == 0:
            return idx - 1
        # TODO: check score
        
    return None

def find_random_correct_item(results, json_data):
    idx_list = []
    for r in results:
        idx = r[0].metadata['seq_num']
        
        if json_data[idx-1]['precision'] == 1 and json_data[idx-1]['recall'] == 1:
            idx_list.append(idx - 1)
        # TODO: check score

    if len(idx_list) > 0:
        return random.choice(idx_list)
        
    return None

def find_random_incorrect_item(results, json_data):
    idx_list = []
    for r in results:
        idx = r[0].metadata['seq_num']
        
        if json_data[idx-1]['precision'] == 0 and json_data[idx-1]['recall'] == 0:
            idx_list.append(idx - 1)
        # TODO: check score

    if len(idx_list) > 0:
        return random.choice(idx_list)
        
    return None

def construct_shot(idx, json_data):
    shot = "" # f"Input question: {json_data[idx]['past_steps'][0]}"
    step_num = 1
    for step in json_data[idx]['past_steps']:
        if type(step) == str:
            step = step.replace("\n", "")
            shot += f"Step {step_num}: {step}\n"
            step_num += 1
        elif type(step) == dict:
            log = step['log'].replace("\n", "")
            shot += f"Action: {log}\n"
        elif type(step) == list and len(step) == 0:
            shot += f"Action: Call plain LLM\n"
        else:
            pass
        
    return shot

def eat_json_answer_template(question, eat, confidence):
    return {
        "question": question,
        "expected_answer_type": {
            "eat": eat,
            "confidence": confidence
        }
    }

expected_answer_type_questions_and_expected_answer_types = [
    {"question": "Show me the birthday of Friedrich Schiller", "expected_answer_type": eat_json_answer_template(
        "Show me the birthday of Friedrich Schiller", "http://www.w3.org/2001/XMLSchema#date", 0.95)},
    {"question": "What is the capital of Germany?", "expected_answer_type": eat_json_answer_template(
        "What is the capital of Germany?", "http://www.w3.org/2000/01/rdf-schema#Resource", 0.95)},
    {"question": "What is the population of Berlin?", "expected_answer_type": eat_json_answer_template(
        "What is the population of Berlin?", "http://www.w3.org/2001/XMLSchema#integer", 0.95)},
    {"question": "What is the speed of light?", "expected_answer_type": eat_json_answer_template(
        "What is the speed of light?", "http://www.w3.org/2001/XMLSchema#decimal", 0.95)},
    {"question": "Is the capital of Germany Berlin?", "expected_answer_type": eat_json_answer_template(
        "Is the capital of Germany Berlin?", "http://www.w3.org/2001/XMLSchema#boolean", 0.95)},
]

def get_expected_answer_type(text, llm):
    """
    Perform Expected Answer Type (EAT) Analysis on the given text using a language model.
    Args:
        text (str): The input text to analyze for expected answer type.
    Returns:
        resource:datatype. If the response cannot be parsed as JSON, an empty list is returned.
    Example:
        >>> get_expected_answer_type("Show me the birthday of Friedrich Schiller")
        ["xsd:date"]
    Note:
        This function uses a language model to perform a EAT analysis and expects the model to return the recognized 
        expected answer type in a structured JSON format. If the response is not valid JSON, an error is logged and an empty list is returned.
    """

    # example_string = "Show me the birthday of Friedrich Schiller"
    # assistant_docstring = """["xsd:date"]"""

    logging.info(
        "get_expected_answer_type: Calling OpenAI API for question: '%s'", text)

    if text is None or text == "":
        logging.error("get_expected_answer_type: Text is None or empty")
        raise ValueError("Text is None or empty")

    messages = [
        (
            "system",
            """You are a Expected Answer Type Tool.
    Recognize named the expected answer type of the given question and output as RDF datatype and your confidence score.
    **Output ONLY the structured data.**
    Below is a text for you to analyze."""
        ),
        (
            "human", 
            expected_answer_type_questions_and_expected_answer_types[0]["question"]
        ),
        (
            "assistant",
            f"{expected_answer_type_questions_and_expected_answer_types[0]['expected_answer_type']}"
        ),
        (
            "human",
            expected_answer_type_questions_and_expected_answer_types[1]["question"]
        ),
        (
            "assistant",
            f"{expected_answer_type_questions_and_expected_answer_types[1]['expected_answer_type']}"
        ),
        (
            "human", 
            expected_answer_type_questions_and_expected_answer_types[2]["question"]
        ),
        (
            "assistant",
            f"{expected_answer_type_questions_and_expected_answer_types[2]['expected_answer_type']}"
        ),
        (
            "human", 
            text
        )
    ]

    result_text = llm.invoke(messages).content

    # parse the result
    try:
        # load JSON data from result_text using ' as the quote character
        result = ast.literal_eval(result_text)
        logging.info("LLM EAT result for question '%s': %s", text, result)
    except json.JSONDecodeError:
        logging.error("JSONDecodeError: %s", result_text)
        return ["None"]

    eat = result.get("expected_answer_type", {}).get("eat", None)
    confidence = result.get("expected_answer_type", {}).get("confidence", None)

    if eat is None:
        logging.error("LLM EAT result contains invalid eat: %s", result)
        raise ValueError("LLM EAT result contains invalid eat: %s", result)
    if confidence is None:
        logging.error("LLM EAT result contains invalid confidence: %s", result)
        raise ValueError(
            "LLM EAT result contains invalid confidence: %s", result)

    return result

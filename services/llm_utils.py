from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool
from typing import List
import random
# from ld_utils import search_entity, falcon_rel


class Plan(BaseModel):
    """Plan to follow in future"""

    steps: List[str] = Field(
        description="different steps to follow, should be in sorted order"
    )
    
class NELInput(BaseModel):
    ne_list: list = Field(description="should be a list of named entities (strings) to be linked to the Wikidata URIs")

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
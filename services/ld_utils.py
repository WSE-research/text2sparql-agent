import json
import requests
from fuzzywuzzy import fuzz
from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib.plugins.sparql.parser import parseQuery


prefixes_list = [
    {"rdf": "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>"},
    {"rdfs": "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>"},
    {"foaf": "PREFIX foaf: <http://xmlns.com/foaf/0.1/>"},
    {"schema": "PREFIX schema: <http://schema.org/>"},
    {"skos": "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>"},
    {"xsd": "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>"},
    {"pv": "PREFIX pv: <http://ld.company.org/prod-vocab/>"},
    {"ecc": "PREFIX ecc: <https://ns.eccenca.com/>"},
    {"void": "PREFIX void: <http://rdfs.org/ns/void#>"},
    {"vann": "PREFIX vann: <http://purl.org/vocab/vann/>"},
    {"dbp": "PREFIX dbp: <http://dbpedia.org/property/>"},
    {"dbo": "PREFIX dbo: <http://dbpedia.org/ontology/>"},
    {"dbr": "PREFIX dbr: <http://dbpedia.org/resource/>"},
]



def search_entity(query: str, lang: str = "en", similarity: int = 90, search_limit: int = 3):
  wdt_search_url = "https://www.wikidata.org/w/api.php?action=wbsearchentities&search={search}&format=json&language={lang}&uselang={lang}&type=item&limit={search_limit}"
  try:
    response = requests.get(wdt_search_url.format(search=query, lang=lang, search_limit=search_limit), timeout=20)
    data = response.json()
    ne_list = []
    rel_list = []
    for entity in data["search"]:
        wdt_label = entity["label"]
        wdt_id = entity["id"]

        if fuzz.partial_ratio(query.lower(), wdt_label.lower()) > similarity:
            relations = get_relations(wdt_id)
            if len(relations) > 0:
              rel_list += [{wdt_label: f"http://www.wikidata.org/prop/direct/{r}"} for r in relations]
            else:
              ne_list.append({wdt_label: f"http://www.wikidata.org/entity/{wdt_id}"})
    return ne_list, rel_list
  except Exception as e:
    print(str(e))
    return [], []

def falcon_rel(query: str):
  try:
    FALCON_URL = "http://localhost:8000/process"
    response = requests.post(FALCON_URL, data=json.dumps({"text": query}), timeout=30)
    data = response.json()
    rel_list = []
    for relation in data[f"relations_wikidata"]:
      rel_list.append({relation["label"]: relation["URI"]})
    
    ent_list = []
    for entity in data["entities_wikidata"]:
       ent_list.append({entity["label"]: entity["URI"]})
    return rel_list, ent_list
  except Exception as e:
    print(str(e))
    return [], []
  
def extract_code_blocks(text):
    import re
    pattern = r'```sparql(.*?)```'
    code_blocks = re.findall(pattern, text, re.DOTALL)
    
    if len(code_blocks) > 0:
        return code_blocks
    else:
        pattern = r'```(.*?)```'
        code_blocks = re.findall(pattern, text, re.DOTALL)
        return code_blocks

def post_process(result):
    blocks = extract_code_blocks(result)
    if len(blocks) > 0:
        query = blocks[0].strip()
    else:
        query = result.strip()
    
    parse_object = parseQuery(query)
    query_prefixes = [prefix.prefix for prefix in parse_object[0]] if len(parse_object[0]) > 0 else []
    query = '\n'.join([list(pref.values())[0] for pref in prefixes_list if list(pref.keys())[0] not in query_prefixes]) + '\n' + query

    return query

def execute(query: str, endpoint_url: str = 'http://141.57.8.18:40201/dbpedia/sparql'):
    try:
        query = post_process(query)
        parse_object = parseQuery(query)

        query_prefixes = [prefix.prefix for prefix in parse_object[0]] if len(parse_object[0]) > 0 else []

        query = '\n'.join([list(pref.values())[0] for pref in prefixes_list if list(pref.keys())[0] not in query_prefixes]) + '\n' + query
        
        sparql = SPARQLWrapper(endpoint_url)
        sparql.timeout = 5
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        response = sparql.query().convert()
        return response
    except Exception as e:
        e = str(e)
        print(e)
        if 'MalformedQueryException' in e or 'bad formed' in e:
            return {'error': str(e)}
        return  {'error': str(e)}

def get_relations(uri):
  sparql = f"""
  SELECT ?uri {{
    <http://www.wikidata.org/entity/{uri}> <http://www.wikidata.org/prop/direct/P1687> ?uri
  }}
  """

  results = transform_sparql_json_to_dataframe(execute(sparql))
  if results.shape[0] > 0:
    return [res.split("/")[-1] for res in results.uri]
  else:
    return []
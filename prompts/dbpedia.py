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
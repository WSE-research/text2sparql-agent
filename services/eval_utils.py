def precision(relevant_items: list, retrieved_items: list, compare_func = None) -> float:
    """
    Precision (P) is the fraction of retrieved documents that are relevant

    Args:
        relevant_items (list): A list of relevant items for a user request
        retrieved_items (list): A list of retrieved items for a user request
        compare_func (function, optional): Function, how to compare the items. Defaults to "a == b".

    Returns:
        float: precision score
    """

    if relevant_items == [] and retrieved_items == []:
        return 1.0
    
    if not compare_func:
        def is_equal(a, b):
            return a == b
        compare_func = is_equal

    relevant_items_retrieved = 0

    for relevant in relevant_items:
        for retrieved in retrieved_items:
            if compare_func(relevant, retrieved):
                relevant_items_retrieved += 1
                break
    
    precision_score = relevant_items_retrieved/len(retrieved_items) if len(retrieved_items) > 0 else 0
    
    return precision_score

def recall(relevant_items: list, retrieved_items: list, compare_func = None) -> float:
    """
    Recall (R) is the fraction of relevant documents that are retrieved

    Args:
        relevant_items (list): A list of relevant items for a user request
        retrieved_items (list): A list of retrieved items for a user request
        compare_func (function, optional): Function, how to compare the items. Defaults to "a == b".

    Returns:
        float: recall score
    """

    if relevant_items == [] and retrieved_items == []:
        return 1.0

    if not compare_func:
        def is_equal(a, b):
            return a == b
        compare_func = is_equal

    relevant_items_retrieved = 0

    for relevant in relevant_items:
        for retrieved in retrieved_items:
            if compare_func(relevant, retrieved):
                relevant_items_retrieved += 1
                break
    
    recall_score = relevant_items_retrieved/len(relevant_items) if len(relevant_items) > 0 else 0
    
    return recall_score

def is_equal(a, b):
    try:
        a = list(a.values())[0]
        b = list(b.values())[0]

        return a['type'] == b['type'] and a['value'] == b['value']
    except Exception as e:
        return False

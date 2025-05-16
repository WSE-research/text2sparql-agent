import json

from services.ld_utils import execute
from services.eval_utils import precision, recall, is_equal


with open('data/evaluation/corporate_answers.json', 'r', encoding='utf-8') as f:
    predicted_answers = json.load(f)

with open('data/evaluation/corporate_ground_truth.json', 'r', encoding='utf-8') as f:
    gt_answers = json.load(f)

assert len(predicted_answers) == len(gt_answers), "The number of predicted answers and ground truth answers must be the same."

for predicted, ground_truth in zip(predicted_answers, gt_answers):
    sparql_result = execute(predicted['query'])
    if type(sparql_result) == dict and 'error' in sparql_result.keys():
        sparql_result = execute(predicted['query'])
    gt_result = execute(ground_truth['query'])

    if type(gt_result) == dict and 'error' in gt_result.keys():
        continue
    elif type(sparql_result) == dict and 'error' in sparql_result.keys():
        pr = 0
        rec = 0
    else:
        try:
            sparql_result['results']['bindings'] = sparql_result['results']['bindings']
            pr = precision(gt_result['results']['bindings'], sparql_result['results']['bindings'], compare_func=is_equal)
            rec = recall(gt_result['results']['bindings'], sparql_result['results']['bindings'], compare_func=is_equal)
        except:
            pr = 0
            rec = 0
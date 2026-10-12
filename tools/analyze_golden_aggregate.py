"""Private aggregate error analysis after predictions have been frozen."""
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path

from tools import golden_gap_runner as gap
from tools.evaluate_human_labels import _load_gold

ANSWERS=Path('/Users/haniframadhan/Documents/Codex/2026-10-05/task/human-evaluation/golden_50_human_labels_completed.csv')
FROZEN_SHA='42bbc688c71648206cde882c7d4eb72f8ecf8c5154298f5520ce645427228d44'


def analyze():
    frozen=gap.OUT/'predictions50_frozen.jsonl'
    if gap.digest(frozen)!=FROZEN_SHA:
        raise ValueError('frozen predictions changed after scoring')
    gold=_load_gold(str(gap.BLANK),str(ANSWERS),50,gap.BLANK_SHA)
    predicted={}
    with frozen.open(encoding='utf-8') as f:
        for line in f:
            row=json.loads(line)
            if row['review_id'] in predicted:raise ValueError('duplicate frozen ID')
            predicted[row['review_id']]=row
    if set(predicted)!=set(gold):raise ValueError('frozen prediction coverage differs')
    topic=defaultdict(Counter);severity_errors=Counter();topic_support=Counter()
    exact_topic=exact_intent=exact_severity=0
    for rid,human in gold.items():
        row=predicted[rid]
        topic[human['topic']][row['topic']]+=1
        topic_support[human['topic']]+=1
        exact_topic+=row['topic']==human['topic']
        exact_intent+=row['intent']==human['intent']
        exact_severity+=row['severity']==human['severity']
        severity_errors[abs(row['severity']-human['severity'])]+=1
    with ANSWERS.open(newline='',encoding='utf-8-sig') as f:
        human_rows=list(csv.DictReader(f))
    if len(human_rows)!=50 or any(r['review_id'] not in gold for r in human_rows):
        raise ValueError('human answer identity differs')
    human_review=Counter(r['needs_review'].strip().lower() for r in human_rows)
    if set(human_review)-{'true','false'}:raise ValueError('human review flags differ')
    report={'schema_version':'golden-50-aggregate-error-v1',
        'frozen_predictions_sha256':FROZEN_SHA,'human_answer_rows':50,
        'topic_exact':exact_topic,'intent_exact':exact_intent,
        'severity_exact':exact_severity,
        'severity_absolute_error_distribution':dict(sorted(severity_errors.items())),
        'topic_support':dict(sorted(topic_support.items())),
        'topic_confusion':{k:dict(sorted(v.items())) for k,v in sorted(topic.items())},
        'human_needs_review':dict(sorted(human_review.items())),
        'case_level_data_in_report':False,
        'evidence_quote_accuracy':'not scored by this four-field evaluator',
        'independence_limit':'eight exact-text development overlaps; prior golden influence on historical prompt decisions not ruled out'}
    gap.private_write(gap.OUT/'evaluation50_detailed_aggregate.json',report)
    return {'rows':50,'topic_exact':exact_topic,'intent_exact':exact_intent,
        'severity_exact':exact_severity,'human_review_flags':human_review.get('true',0),
        'report_sha256':gap.digest(gap.OUT/'evaluation50_detailed_aggregate.json')}


if __name__=='__main__':print(json.dumps(analyze(),sort_keys=True))

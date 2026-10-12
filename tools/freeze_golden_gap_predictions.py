"""Freeze 50 source-only predictions before any human-answer scoring."""
import hashlib
import json
import os
import sqlite3

from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.schema import validate_completed
from tools import golden_gap_runner as gap


def freeze():
    plan,source=gap.load_plan()
    old={}
    with gap.ORIGINAL.open(encoding='utf-8') as f:
        for line in f:
            row=json.loads(line)
            if row['review_id'] in old:raise ValueError('duplicate prior prediction')
            old[row['review_id']]=row
    if len(old)!=9 or set(old)&{r['review_id'] for r in plan['rows']}:
        raise ValueError('prior prediction partition differs')
    db=sqlite3.connect('file:'+str(gap.LEDGER)+'?mode=ro',uri=True)
    rows=[];provenance={}
    try:
        for rid,s in source.items():
            source_hash=gap.row_sha256([s[k] for k in gap.SOURCE_FIELDS])
            if rid in old:
                row=old[rid]
                provenance['prior_accepted']=provenance.get('prior_accepted',0)+1
            else:
                label=db.execute('''SELECT source_sha,label_json,provenance,origin_id
                    FROM golden_gap_labels WHERE review_id=?''',(rid,)).fetchone()
                ev=db.execute('''SELECT evidence_json,provenance,origin_id,config_sha
                    FROM golden_gap_evidence WHERE review_id=?''',(rid,)).fetchone()
                if label is None or ev is None or label[0]!=source_hash:
                    raise ValueError('gap prediction incomplete or source identity differs')
                labels=json.loads(label[1]);evidence=json.loads(ev[0])
                validate_evidence(s['review_text'],evidence)
                row={'review_id':rid,'source_sha256':source_hash,'status':'completed',
                    'topic':labels['topic'],'intent':labels['intent'],
                    'sentiment':labels['sentiment'],'severity':labels['severity'],
                    'entities':evidence['entities'],'evidence_quote':evidence['evidence_quote'],
                    'needs_review':labels['needs_review'],'label_config':gap.LABEL_SHA}
                if label[2]=='exact_text_cache':
                    if not label[3] or ev[2]!=label[3]:raise ValueError('cache provenance differs')
                    row['cache_source_id']=label[3]
                provenance[label[2]]=provenance.get(label[2],0)+1
            if row['source_sha256']!=source_hash:
                raise ValueError('prediction source hash differs')
            errors=validate_completed(row,source={'review_id':rid,
                'review_text':s['review_text'],'row_sha256':source_hash})
            if errors:raise ValueError('prediction schema fails: '+errors[0])
            rows.append(row)
    finally:db.close()
    if len(rows)!=50:raise ValueError('frozen prediction count differs')
    target=gap.OUT/'predictions50_frozen.jsonl'
    temp=target.with_name(target.name+'.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
        f.flush();os.fsync(f.fileno())
    new_sha=gap.digest(temp)
    if target.exists() and gap.digest(target)!=new_sha:
        temp.unlink();raise ValueError('frozen prediction bytes would change')
    os.replace(temp,target)
    gap.private_write(gap.OUT/'predictions50_frozen_manifest.json',{
        'schema_version':'golden-predictions-50-frozen-v1',
        'predictions_sha256':new_sha,'count':50,'provenance_counts':provenance,
        'source_sha256':gap.BLANK_SHA,'plan_sha256':gap.PLAN_SHA,
        'gold_answers_read':False})
    return {'count':50,'sha256':new_sha,'provenance_counts':provenance}


if __name__=='__main__':print(json.dumps(freeze(),sort_keys=True))

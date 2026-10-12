"""Fill saved accepted fields in private 110k grading candidate only.

No statuses, source IDs, hashes, labels, or human corrections are inferred.
The original candidate is snapshotted before replacement.
"""
import gzip
import json
import os
from pathlib import Path
import shutil

from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.schema import validate_completed
from tools import golden_gap_runner as gap

DEST=gap.ROOT/'local/grading_v4_submission_candidate'
BACKUP=gap.ROOT/'local/grading_checker_20261012/records_before_schema_fix.jsonl.gz'


def repair():
    target=DEST/'records.jsonl.gz'
    manifest_path=DEST/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    before=gap.digest(target)
    if BACKUP.exists() and gap.digest(BACKUP)!=before:
        raise ValueError('original candidate backup differs')
    if not BACKUP.exists():
        fd=os.open(BACKUP,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as out,target.open('rb') as src:shutil.copyfileobj(src,out)
    handoff=json.loads(gap.HANDOFF.read_text())
    accepted={r['review_id']:r for r in handoff['records']}
    excluded={r['review_id']:r for r in handoff['excluded']}
    if len(accepted)!=100229 or len(excluded)!=9771:
        raise ValueError('private handoff partition differs')
    temp=target.with_name('records.jsonl.gz.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    counts={'completed':0,'quarantined':0,'other_nonaccepted':0}
    with os.fdopen(fd,'wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as out:
        with gzip.open(target,'rt',encoding='utf-8') as src:
            for line in src:
                row=json.loads(line)
                rid=row['review_id']
                if row['status']=='completed':
                    saved=accepted.get(rid)
                    if saved is None or row['source_sha256']!=saved['source_sha256']:
                        raise ValueError('accepted source identity differs')
                    labels=saved['labels'];evidence=saved['evidence']
                    row.update(sentiment=labels['sentiment'],entities=evidence['entities'],
                        needs_review=labels['needs_review'],
                        label_config=saved['provenance']['label']['config_sha256'])
                    source={'review_id':rid,'review_text':saved['source']['review_text'],
                        'row_sha256':saved['source_sha256']}
                    validate_evidence(source['review_text'],{'entities':row['entities'],
                        'evidence_quote':row['evidence_quote']})
                    errors=validate_completed(row,source=source)
                    if errors:raise ValueError('saved accepted candidate schema differs: '+errors[0])
                    counts['completed']+=1
                elif row['status']=='quarantined':
                    saved=excluded.get(rid)
                    if saved is None or row['source_sha256']!=saved['source_sha256']:
                        raise ValueError('quarantined source identity differs')
                    if not isinstance(saved['reason'],str) or not saved['reason'].strip():
                        raise ValueError('saved quarantine reason missing')
                    row['reason']=saved['reason']
                    counts['quarantined']+=1
                else:
                    if rid not in excluded or row['source_sha256']!=excluded[rid]['source_sha256']:
                        raise ValueError('nonaccepted source identity differs')
                    counts['other_nonaccepted']+=1
                out.write((json.dumps(row,sort_keys=True,ensure_ascii=False)+'\n').encode('utf-8'))
        out.flush()
        raw.flush();os.fsync(raw.fileno())
    if counts!={'completed':100229,'quarantined':1791,'other_nonaccepted':7980}:
        temp.unlink();raise ValueError('candidate state partition differs')
    os.replace(temp,target)
    manifest['file_sha256']['records.jsonl.gz']=gap.digest(target)
    manifest['record_schema_adapter']={
        'source':'byte-pinned accepted 100k handoff',
        'previous_candidate_sha256':before,
        'completed_fields_added':['sentiment','entities','needs_review','label_config'],
        'quarantine_field_added':'saved reason',
        'nonaccepted_statuses_preserved':True,
        'human_label_corrections_preserved':True,
        'source_hashes_preserved':True,
    }
    gap.private_write(manifest_path,manifest)
    return {'counts':counts,'records_sha256':manifest['file_sha256']['records.jsonl.gz'],
        'backup_sha256':gap.digest(BACKUP),'manifest_sha256':gap.digest(manifest_path)}


if __name__=='__main__':print(json.dumps(repair(),sort_keys=True))

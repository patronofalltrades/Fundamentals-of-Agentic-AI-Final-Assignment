"""Expose only actual direct, unified exact-text cache origins in candidate."""
import gzip
import json
import os
from pathlib import Path
import shutil

from tools import golden_gap_runner as gap

DEST=gap.ROOT/'local/grading_v4_submission_candidate'
BACKUP=gap.ROOT/'local/grading_checker_20261012/records_before_cache_provenance.jsonl.gz'
FIELDS=('topic','intent','sentiment','severity','entities','evidence_quote','needs_review','label_config')


def add():
    target=DEST/'records.jsonl.gz'
    before=gap.digest(target)
    if BACKUP.exists() and gap.digest(BACKUP)!=before:
        raise ValueError('cache provenance backup differs')
    if not BACKUP.exists():
        fd=os.open(BACKUP,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as out,target.open('rb') as src:shutil.copyfileobj(src,out)
    handoff=json.loads(gap.HANDOFF.read_text())
    saved={r['review_id']:r for r in handoff['records']}
    with gzip.open(target,'rt',encoding='utf-8') as f:
        records=[json.loads(line) for line in f]
    by={r['review_id']:r for r in records if r['status']=='completed'}
    if len(records)!=110000 or len(by)!=100229:
        raise ValueError('candidate partition differs')
    corrected=set(json.loads((DEST/'run.json').read_text())['human_label_corrections'])
    added=0
    for row in records:
        if row['status']!='completed' or row['review_id'] in corrected:
            continue
        source=saved[row['review_id']]
        label=source['provenance']['label'];evidence=source['provenance']['evidence']
        origin_id=label.get('cache_source_id')
        if not origin_id or origin_id!=evidence.get('cache_source_id'):
            continue
        origin=saved.get(origin_id);candidate=by.get(origin_id)
        if not origin or not candidate or origin_id in corrected or \
                origin['provenance']['label'].get('cache_source_id') or \
                origin['provenance']['evidence'].get('cache_source_id') or \
                not origin['provenance']['label'].get('request_key') or \
                not origin['provenance']['evidence'].get('request_key'):
            continue
        if source['source']['review_text']!=origin['source']['review_text'] or \
                any(row.get(k)!=candidate.get(k) for k in FIELDS):
            continue
        row['cache_source_id']=origin_id
        added+=1
    temp=target.with_name('records.jsonl.gz.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as out:
        for row in records:
            out.write((json.dumps(row,sort_keys=True,ensure_ascii=False)+'\n').encode('utf-8'))
        out.flush();raw.flush();os.fsync(raw.fileno())
    os.replace(temp,target)
    manifest_path=DEST/'manifest.json';manifest=json.loads(manifest_path.read_text())
    manifest['file_sha256']['records.jsonl.gz']=gap.digest(target)
    manifest['cache_provenance_scope']={
        'direct_unified_exact_text_origins_added':added,
        'split_or_indirect_origins_not_rewritten':True,
        'human_corrections_excluded_from_cache_mapping':True,
        'previous_candidate_sha256':before,
    }
    gap.private_write(manifest_path,manifest)
    return {'direct_unified_cache_reuses':added,
            'records_sha256':manifest['file_sha256']['records.jsonl.gz'],
            'manifest_sha256':gap.digest(manifest_path)}


if __name__=='__main__':print(json.dumps(add(),sort_keys=True))

"""Export existing main-run request metadata; no inference or raw responses."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from spotify_pipeline import jev
from tools import deepinfra_recheck100

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/Users/haniframadhan/Documents/Codex/2026-10-07/task-2/spotify-batch10-canary/local/project_budget.db')
DEST = ROOT / 'local/grading_v4_submission_candidate'
LABEL_SHA='0bda2b8478fab805c56f033227017f6f37da9feb7da6b6a79b98b859cb10c647'
PARTS = (
    ('checkpoint_requests','checkpoint_request_members',4184),
    ('next5000_requests','next5000_members',4417),
    ('scale_requests','scale_members',71196),
)


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1048576),b''):h.update(part)
    return h.hexdigest()


def export():
    db=sqlite3.connect('file:'+str(SOURCE)+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    for table in ('checkpoint_labels','next5000_labels','scale_labels'):
        if {r[0] for r in db.execute('SELECT DISTINCT config_sha FROM '+table)}!={LABEL_SHA}:
            raise ValueError('saved label configuration differs')
    temp=DEST/'calls.jsonl.tmp'
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    counts={}
    keys=set()
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:
            for table,members,expected in PARTS:
                roster={}
                for key,rid in db.execute('SELECT request_key,review_id FROM '+members+' ORDER BY rowid'):
                    roster.setdefault(key,[]).append(rid)
                rows=db.execute('SELECT * FROM '+table+' ORDER BY rowid')
                count=0
                for row in rows:
                    row=dict(row)
                    key=row['request_key']
                    if key in keys:raise ValueError('duplicate main request key')
                    keys.add(key)
                    ids=roster.pop(key,None)
                    if not ids or len(ids)>50 or len(set(ids))!=len(ids):
                        raise ValueError('call members missing, duplicated, or unbounded')
                    reserve=db.execute('''SELECT budget,status,reserved_nusd,charged_nusd,
                        created_utc,settled_utc FROM reservations WHERE request_key=?''',(key,)).fetchone()
                    if reserve is None:raise ValueError('call has no shared reservation')
                    budget,status,held,charge,created,settled=reserve
                    if (row['stage']=='jev' and budget!='jev') or \
                            (row['stage']=='evidence' and budget!='openrouter'):
                        raise ValueError('call budget or stage differs')
                    request_status=row['status']
                    if request_status not in ('succeeded','partial_succeeded','quarantined_metered','uncertain'):
                        raise ValueError('unexpected saved request status')
                    record={
                        'request_id':key,'role':'enrich','source_ledger':table,
                        'stage':row['stage'],'phase':None,'phase_available':False,
                        'outcome':request_status,'reservation_status':status,
                        'review_ids':ids,'review_count':len(ids),
                        'model':jev.MODEL if row['stage']=='jev' else deepinfra_recheck100.MODEL,
                        # All three saved label tables use the one frozen Jev
                        # config. Evidence has its own request config below.
                        'label_config':row['config_sha'] if row['stage']=='jev' else LABEL_SHA,
                        'request_config_sha256':row['config_sha'],
                        'request_sha256':row.get('request_sha'),
                        'provider_response_id':row.get('response_id'),
                        'input_tokens':row['input_tokens'],
                        'output_tokens':row['output_tokens'],
                        'reasoning_tokens':row['reasoning_tokens'],
                        'request_seconds':row['elapsed_seconds'],
                        'reserved_nusd':held,'charged_nusd':charge,
                        'created_utc':created,'settled_utc':settled,
                        'error_class':row['error_class'],
                    }
                    out.write(json.dumps(record,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n')
                    count+=1
                if roster or count!=expected:raise ValueError('source request count or member join differs')
                counts[table]=count
            out.flush();os.fsync(out.fileno())
        target=DEST/'calls.jsonl'
        os.replace(temp,target)
        manifest_path=DEST/'manifest.json'
        manifest=json.loads(manifest_path.read_text())
        manifest['file_sha256']['calls.jsonl']=sha(target)
        manifest['calls_scope']={
            'source':'saved shared project budget request tables',
            'request_counts':counts,
            'total_requests':sum(counts.values()),
            'roles_present':['enrich'],
            'phase_available':False,
            'group_and_memo_provider_calls':'unavailable',
            'unknown_usage_and_cost':'preserved as null',
            'request_seconds':'per-call elapsed time; not total wall time',
            'golden_gap_calls_included':False,
        }
        manifest['checkpoint_scope']={
            'main_run_checkpoint_before':'unavailable',
            'main_run_checkpoint_after':'unavailable',
            'golden_gap_checkpoints_are_separate':True,
        }
        temp_manifest=DEST/'manifest.json.tmp'
        fd=os.open(temp_manifest,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(manifest,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(temp_manifest,manifest_path)
        return {'counts':counts,'sha256':manifest['file_sha256']['calls.jsonl'],
                'manifest_sha256':sha(manifest_path)}
    finally:
        db.close()
        if temp.exists():temp.unlink()


if __name__=='__main__':print(json.dumps(export(),sort_keys=True))

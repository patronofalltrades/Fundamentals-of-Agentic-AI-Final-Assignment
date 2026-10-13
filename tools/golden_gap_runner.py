"""One-attempt, source-only golden prediction gap. Private local execution.

No inference is made by import or --check. A reserved request is never replayed.
Only the pinned 36 Jev calls and two 25/12 evidence batches are admitted.
"""

import argparse
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time

from spotify_pipeline import jev
from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.config import config_hash
from spotify_pipeline.contract import SOURCE_FIELDS, row_sha256, text_sha256
from spotify_pipeline.jev_pilot import NANODOLLARS_PER_INPUT_TOKEN, RESERVATION_NANODOLLARS
from spotify_pipeline.project_budget import ProjectBudget
from tools import deepinfra_batch10_canary as canary
from tools import openrouter_extractor_benchmark as benchmark
from tools import scale100k_batch25 as evidence
from tools.checkpoint5000_dispatch import legacy_paths
from tools.checkpoint5000_orchestrate import JEV_ACCOUNT, JEV_SERVICE, verify_jev_price

ROOT = Path(__file__).resolve().parents[1]
CANARY = Path('/Users/haniframadhan/Documents/Codex/2026-10-07/task-2/spotify-batch10-canary')
BLANK = Path('/Users/haniframadhan/Documents/Codex/2026-09-29/le/work/capstone_data/golden_50_to_label.csv')
PLAN = ROOT / 'local/golden_gap_dryrun_20261012.json'
ORIGINAL = CANARY / 'local/golden50_accepted_overlap_predictions.jsonl'
HANDOFF = CANARY / 'local/accepted100k_dashboard_handoff.json'
LEDGER = CANARY / 'local/project_budget.db'
OUT = ROOT / 'local/golden_gap_run_20261012'
PLAN_SHA = '99f64f07dbe399239bfb2aa26bc87c1d930bd88936c68b90c3d42c4ba4045a15'
BLANK_SHA = '1a125c3e509f58b0246ba16d0ea332675a53ffadb1928be4338a0bd7053a11c7'
LABEL_SHA = '0bda2b8478fab805c56f033227017f6f37da9feb7da6b6a79b98b859cb10c647'
MAX_INCREMENT_NUSD = 120_000_000
MAX_COMBINED_NUSD = 10_000_000_000
PREFIX = 'golden-gap-20261012-'


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for part in iter(lambda: f.read(1048576), b''):
            h.update(part)
    return h.hexdigest()


def private_write(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, sort_keys=True, ensure_ascii=False)
            f.write('\n')
            f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists(): temp.unlink()


def append_call(value):
    path = OUT / 'calls.jsonl'
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(json.dumps(value, sort_keys=True) + '\n')
        f.flush(); os.fsync(f.fileno())


def load_plan():
    if digest(PLAN) != PLAN_SHA or digest(BLANK) != BLANK_SHA:
        raise ValueError('pinned plan or blank source changed')
    plan = json.loads(PLAN.read_text())
    if plan['blank_source_sha256'] != BLANK_SHA or plan['frozen_label_config_sha256'] != LABEL_SHA \
            or config_hash(jev.label_config()) != LABEL_SHA:
        raise ValueError('source or label configuration differs')
    if plan['counts'] != {'new_once': 36, 'reuse_saved': 4, 'retry_known_partial_evidence': 1}:
        raise ValueError('run scope differs')
    rows = plan['rows']
    if len(rows) != 41 or len({r['review_id'] for r in rows}) != 41:
        raise ValueError('plan IDs differ')
    source = {}
    with BLANK.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames[:6]) != SOURCE_FIELDS:
            raise ValueError('blank source columns differ')
        for row in reader:
            if any((row[k] or '').strip() for k in reader.fieldnames[6:]):
                raise ValueError('source is no longer blank; refuse human answers')
            source[row['review_id']] = {k: row[k] for k in SOURCE_FIELDS}
    if len(source) != 50:
        raise ValueError('blank source count differs')
    for r in rows:
        s = source[r['review_id']]
        if row_sha256([s[k] for k in SOURCE_FIELDS]) != r['source_sha256'] or \
                text_sha256(s['review_text']) != r['text_sha256']:
            raise ValueError('planned source identity differs')
        if r['action'] == 'new_once' and r['prior_attempts']:
            raise ValueError('new call has prior attempts')
        if r['action'] == 'retry_known_partial_evidence' and \
                sorted((a['stage'], a['status']) for a in r['prior_attempts']) != \
                [('evidence', 'partial_succeeded'), ('jev', 'succeeded')]:
            raise ValueError('known partial history differs')
    return plan, source


def budget_paths():
    paths = legacy_paths()
    for name in ('batch_v1', 'batch_v2'):
        paths[name] = str(CANARY / paths[name])
    return paths


def init_tables(db):
    db.execute('''CREATE TABLE IF NOT EXISTS golden_gap_labels(
        review_id TEXT PRIMARY KEY,source_sha TEXT NOT NULL,label_json TEXT NOT NULL,
        provenance TEXT NOT NULL,origin_id TEXT,request_key TEXT)''')
    db.execute('''CREATE TABLE IF NOT EXISTS golden_gap_evidence(
        review_id TEXT PRIMARY KEY,evidence_json TEXT NOT NULL,provenance TEXT NOT NULL,
        origin_id TEXT,request_key TEXT,config_sha TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS golden_gap_calls(
        request_key TEXT PRIMARY KEY,stage TEXT NOT NULL,status TEXT NOT NULL,
        ids_json TEXT NOT NULL,response_json TEXT,error_class TEXT)''')
    db.commit()


def exposure_check(budget, next_amount=0):
    db = budget.db
    rows = list(db.execute('''SELECT status,reserved_nusd,charged_nusd FROM reservations
        WHERE request_key LIKE ?''', (PREFIX + '%',)))
    incremental = sum(charged if status in ('succeeded','quarantined_metered') and charged is not None
        else max(reserved, charged or 0) for status,reserved,charged in rows)
    if incremental + next_amount > MAX_INCREMENT_NUSD or \
            budget.exposure('jev') + budget.exposure('openrouter') + next_amount >= MAX_COMBINED_NUSD:
        raise ValueError('approved incremental or combined exposure limit reached')
    return incremental


def cache_import(budget, plan, source):
    db = budget.db
    wanted = {r['review_id']: r for r in plan['rows'] if r['action'] == 'reuse_saved'}
    handoff = json.loads(HANDOFF.read_text())
    direct = {}
    for item in handoff['records']:
        if item['review_id'] in {r['cache_source_id'] for r in wanted.values()}:
            direct[item['review_id']] = item
    if len(direct) != 4:
        raise ValueError('four direct cache origins required')
    for rid,r in wanted.items():
        origin = direct[r['cache_source_id']]
        s = source[rid]
        if origin['source']['review_text'] != s['review_text'] or \
                origin['provenance']['label'].get('config_sha256') != LABEL_SHA:
            raise ValueError('cache text or label configuration differs')
        ev = origin['evidence']
        validate_evidence(s['review_text'], ev)
        cfg = origin['provenance']['evidence'].get('config_sha256')
        if cfg != evidence.config_sha():
            raise ValueError('cache evidence configuration differs')
        label = origin['labels']
        with db:
            db.execute('''INSERT OR IGNORE INTO golden_gap_labels VALUES (?,?,?,?,?,NULL)''',
                (rid,r['source_sha256'],json.dumps(label,sort_keys=True),'exact_text_cache',r['cache_source_id']))
            db.execute('''INSERT OR IGNORE INTO golden_gap_evidence VALUES (?,?,?,?,NULL,?)''',
                (rid,json.dumps(ev,sort_keys=True),'exact_text_cache',r['cache_source_id'],cfg))
    r = next(r for r in plan['rows'] if r['action'] == 'retry_known_partial_evidence')
    original = sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True)
    try:
        saved = original.execute('''SELECT label_json,config_sha FROM scale_labels
            WHERE review_id=?''',(r['review_id'],)).fetchone()
        src = original.execute('''SELECT review_text,source_sha FROM scale_rows
            WHERE review_id=?''',(r['review_id'],)).fetchone()
    finally: original.close()
    if saved is None or src != (source[r['review_id']]['review_text'],r['source_sha256']) or saved[1] != LABEL_SHA:
        raise ValueError('known partial saved label differs')
    with db:
        db.execute('''INSERT OR IGNORE INTO golden_gap_labels VALUES (?,?,?,?,?,NULL)''',
            (r['review_id'],r['source_sha256'],saved[0],'saved_direct',None))


def snapshot(budget, path, status):
    db = budget.db
    counts = {
        'labels': db.execute('SELECT COUNT(*) FROM golden_gap_labels').fetchone()[0],
        'evidence': db.execute('SELECT COUNT(*) FROM golden_gap_evidence').fetchone()[0],
        'calls': dict(db.execute('SELECT status,COUNT(*) FROM golden_gap_calls GROUP BY status')),
    }
    private_write(path, {'status':status,'plan_sha256':PLAN_SHA,'counts':counts,
        'incremental_exposure_nusd':exposure_check(budget),
        'jev_exposure_nusd':budget.exposure('jev'),
        'openrouter_exposure_nusd':budget.exposure('openrouter')})


def call_once(budget, stage, rows, body, key, transport, attempt_tag=None):
    ids = [r['review_id'] for r in rows]
    if attempt_tag not in (None,'approved-uncertain-retry-1'):
        raise ValueError('unapproved attempt tag')
    request_key = PREFIX + stage + ('-'+attempt_tag if attempt_tag else '') + '-' + \
        hashlib.sha256(json.dumps(ids).encode()).hexdigest()
    amount = RESERVATION_NANODOLLARS if stage == 'jev' else evidence.reservation_nusd()
    exposure_check(budget, amount)
    if budget.db.execute("SELECT 1 FROM reservations WHERE status='reserved' LIMIT 1").fetchone():
        raise ValueError('an active or ambiguous paid request exists; stop')
    if budget.db.execute('SELECT 1 FROM golden_gap_calls WHERE request_key=?',(request_key,)).fetchone():
        raise ValueError('this request was already attempted; no replay')
    def reserve_record(db):
        db.execute("INSERT INTO golden_gap_calls VALUES (?,?,'reserved',?,NULL,NULL)",
            (request_key,stage,json.dumps(ids)))
    budget.reserve(request_key,'jev' if stage=='jev' else 'openrouter',amount,reserve_record)
    snapshot(budget,OUT/'checkpoints'/ (request_key + '.before.json'),'reserved_before_dispatch')
    started=time.monotonic()
    try:
        response=transport(stage,body,key)
        if stage=='jev':
            label=jev.parse_response(response).__dict__
            charge=label['input_tokens']*NANODOLLARS_PER_INPUT_TOKEN
            if charge>amount: raise ValueError('Jev usage exceeds reservation')
            inp,out=label['input_tokens'],label['output_tokens']
            accepted={ids[0]:label}; invalid={}
        else:
            inp,out,_,charge=evidence.measured_usage(response)
            accepted,invalid=evidence.inspect(response,rows)
        status='succeeded' if not invalid and len(accepted)==len(rows) else 'quarantined_metered'
        raw=json.dumps(response,ensure_ascii=False)
        def finish(db):
            db.execute('''UPDATE golden_gap_calls SET status=?,response_json=? WHERE request_key=?''',
                (status,raw,request_key))
            if status=='succeeded':
                for rid,item in accepted.items():
                    if stage=='jev':
                        db.execute('''INSERT INTO golden_gap_labels VALUES (?,?,?,?,NULL,?)''',
                            (rid,rows[0]['source_sha256'],json.dumps(item,sort_keys=True),'direct',request_key))
                    else:
                        db.execute('''INSERT INTO golden_gap_evidence VALUES (?,?,?,?,?,?)''',
                            (rid,json.dumps(item,sort_keys=True),'direct',None,request_key,
                             evidence.config_for_size(len(rows))))
        budget.settle(request_key,status,charge,finish)
        append_call({'request_key':request_key,'stage':stage,'status':status,'count':len(rows),
            'input_tokens':inp,'output_tokens':out,'charged_nusd':charge,
            'elapsed_seconds':round(time.monotonic()-started,3)})
        snapshot(budget,OUT/'checkpoints'/ (request_key + '.after.json'),status)
        if status!='succeeded':raise ValueError('metered response incomplete; no retry')
    except Exception as exc:
        current=budget.db.execute('SELECT status FROM reservations WHERE request_key=?',(request_key,)).fetchone()
        if current == ('reserved',):
            error=type(exc).__name__
            budget.uncertain(request_key,lambda db: db.execute('''UPDATE golden_gap_calls
                SET status='uncertain',error_class=? WHERE request_key=?''',(error,request_key)))
            append_call({'request_key':request_key,'stage':stage,'status':'uncertain',
                'count':len(rows),'charged_nusd':None,'error_class':error})
            snapshot(budget,OUT/'checkpoints'/ (request_key + '.after.json'),'uncertain')
        raise


def transport(stage, body, key):
    if stage=='jev': return jev.post_systemone(body,key)
    return benchmark.request_json('https://openrouter.ai/api/v1/chat/completions',body,key)


def run(check_only=False):
    plan,source=load_plan()
    OUT.mkdir(mode=0o700,parents=True,exist_ok=True)
    lease=open(OUT/'run.lock','a+b')
    try:
        fcntl.flock(lease.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        lease.close()
        raise ValueError('another golden gap runner is active') from None
    try:
        return _run_locked(plan,source,check_only)
    finally:
        lease.close()


def _run_locked(plan,source,check_only):
    with ProjectBudget(str(LEDGER),budget_paths()) as budget:
        init_tables(budget.db)
        cache_import(budget,plan,source)
        exposure_check(budget)
        if check_only:
            return {'status':'offline_check_ok','counts':plan['counts'],
                    'incremental_exposure_nusd':exposure_check(budget)}
        verify_jev_price(); benchmark.verify_route('deepinfra')
        jev_key=canary.keychain_secret(timeout_seconds=90,service=JEV_SERVICE,account=JEV_ACCOUNT)
        jev.check_model_access(jev_key)
        openrouter_key=canary.keychain_secret(timeout_seconds=90)
        canary.verify_project_key(openrouter_key,evidence.reservation_nusd())
        if not (OUT/'checkpoint_before.json').exists():
            snapshot(budget,OUT/'checkpoint_before.json','ready_before_run')
        for r in (r for r in plan['rows'] if r['action']=='new_once'):
            if budget.db.execute('SELECT 1 FROM golden_gap_labels WHERE review_id=?',(r['review_id'],)).fetchone():continue
            call_once(budget,'jev',[r],jev.build_request(source[r['review_id']]['review_text']),jev_key,transport)
        jev_key=None
        work=[r for r in plan['rows'] if r['action']!='reuse_saved']
        if len(work)!=37:raise ValueError('evidence scope differs')
        for batch in (work[:25],work[25:]):
            if all(budget.db.execute('SELECT 1 FROM golden_gap_evidence WHERE review_id=?',(r['review_id'],)).fetchone() for r in batch):continue
            rows=[]
            for r in batch:
                label=budget.db.execute('SELECT label_json FROM golden_gap_labels WHERE review_id=?',(r['review_id'],)).fetchone()
                if label is None:raise ValueError('evidence label missing')
                rows.append({'review_id':r['review_id'],'review_text':source[r['review_id']]['review_text'],
                    'source_sha256':r['source_sha256'],'labels':json.loads(label[0])})
            call_once(budget,'evidence',rows,evidence.payload(rows),openrouter_key,transport)
        openrouter_key=None
        snapshot(budget,OUT/'checkpoint_after.json','complete')
        return {'status':'complete','labels':budget.db.execute('SELECT COUNT(*) FROM golden_gap_labels').fetchone()[0],
                'evidence':budget.db.execute('SELECT COUNT(*) FROM golden_gap_evidence').fetchone()[0],
                'incremental_exposure_nusd':exposure_check(budget)}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    print(json.dumps(run(check_only=args.check),sort_keys=True))

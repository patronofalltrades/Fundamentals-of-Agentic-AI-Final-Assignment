"""Private 110k checker diagnostic from saved source manifests.

This is not the course's full-file reference: the original 660k CSV is
currently a macOS dataless file and cannot be read by the official generator.
"""
import json
import os
from pathlib import Path

from tools import golden_gap_runner as gap

CANARY=gap.CANARY/'local'
DEST=gap.ROOT/'local/grading_checker_20261012/scoped_reference.json'
CANDIDATE=gap.ROOT/'local/grading_v4_submission_candidate'
INPUTS=(('checkpoint5000_manifest.json',5000),('next5000_manifest.json',5000),
        ('scale100k_manifest_v2.json',90000),('scale100k_extension_100001_120000.json',10000))


def build():
    rows={}
    for name,count in INPUTS:
        data=json.loads((CANARY/name).read_text())
        selected=data['rows'][:count]
        if len(selected)!=count:raise ValueError('source manifest selection differs')
        for item in selected:
            rid=item['review_id']
            if rid in rows:raise ValueError('duplicate selected ID')
            rows[rid]={'source_sha256':item['source_sha256'],
                       'review_text':item.get('review_text',item.get('text'))}
    if len(rows)!=110000 or any(not isinstance(r['review_text'],str) for r in rows.values()):
        raise ValueError('selected source text missing')
    handoff=json.loads((CANARY/'accepted100k_dashboard_handoff.json').read_text())
    selected_ids={r['review_id'] for r in handoff['records']}|{r['review_id'] for r in handoff['excluded']}
    if set(rows)!=selected_ids:raise ValueError('selected ID partition differs from handoff')
    for record in handoff['records']:
        source=rows[record['review_id']]
        if source['source_sha256']!=record['source_sha256'] or \
                source['review_text']!=record['source']['review_text']:
            raise ValueError('accepted source identity differs')
    for record in handoff['excluded']:
        if rows[record['review_id']]['source_sha256']!=record['source_sha256']:
            raise ValueError('excluded source hash differs')
    declared=json.loads((CANDIDATE/'run.json').read_text())
    ref={'version':'a5-audit-v1',
         'analysis_sha256':declared['analysis_sha256'],
         'ingestion':json.loads((CANDIDATE/'ingestion.json').read_text()),
         'rows':rows}
    gap.private_write(DEST,ref)
    return {'selected_rows':len(rows),'sha256':gap.digest(DEST),
            'full_source_verified_now':False,
            'analysis_sha256_source':'candidate declaration, not reconstructed selected CSV'}


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))

"""Add truthful course-adapter fields to the private 110k run declaration."""
import json
import os
from tools import golden_gap_runner as gap

DEST=gap.ROOT/'local/grading_v4_submission_candidate'
BACKUP=gap.ROOT/'local/grading_checker_20261012/run_before_course_adapter.json'


def repair():
    target=DEST/'run.json'
    run=json.loads(target.read_text())
    if run.get('version')=='a5-audit-v1':
        return {'status':'unchanged','run_sha256':gap.digest(target)}
    if run.get('version')!='spotify-grouping-v4-20261012':
        raise ValueError('unexpected source run version')
    if BACKUP.exists() and gap.digest(BACKUP)!=gap.digest(target):
        raise ValueError('original run backup differs')
    if not BACKUP.exists():
        fd=os.open(BACKUP,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(target.read_bytes())
    run['pipeline_version']=run['version']
    run['version']='a5-audit-v1'
    run['analysis_count']=110000
    run['classification_input_fields']=['review_text']
    run['analysis_identity_scope']='analysis_sha256 is pinned original full-source CSV identity; no selected analysis CSV was generated'
    run['checker_scope_limit']='course checker unchanged; full 660622-ID requirement remains unresolved by this 110000-ID candidate'
    gap.private_write(target,run)
    manifest_path=DEST/'manifest.json';manifest=json.loads(manifest_path.read_text())
    manifest['file_sha256']['run.json']=gap.digest(target)
    manifest['course_adapter_scope']={
        'selected_ids':110000,'accepted_ids':100229,
        'original_full_source_ids':660622,
        'analysis_sha256_is_full_source_identity':True,
        'selected_analysis_csv_available':False,
        'official_full_reference_pass_claimed':False,
    }
    gap.private_write(manifest_path,manifest)
    return {'run_sha256':gap.digest(target),'manifest_sha256':gap.digest(manifest_path)}


if __name__=='__main__':print(json.dumps(repair(),sort_keys=True))

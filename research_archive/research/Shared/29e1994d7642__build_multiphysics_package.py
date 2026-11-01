"""Build the distributable Rev1.7 CAD/multiphysics preparation package."""
from __future__ import annotations
import hashlib, json, shutil, zipfile
from pathlib import Path

BASE=Path(__file__).resolve().parent
DIST=BASE/'Tomahawk_Rev1_7_Multiphysics_Package'
ARCHIVE=BASE/'Tomahawk_Rev1_7_Multiphysics_Package.zip'

FILES=[
 'Tomahawk_Rev1_7_Multiphysics_CAD_Export.py','tomahawk_entire_model.py',
 'tomahawk_multiphysics_run.py','full_model_source.py','build_standalone.py',
 'test_full_model.py','Tomahawk_Rev1_7_Multiphysics_Package_README.md',
 'Tomahawk_Whole_Model_README.md','Tomahawk_Rev1_5_Run_Instructions.md',
 'build_multiphysics_package.py',
 'Tomahawk_Rev1_4_G1_Tight_Roundtrip.py','Tomahawk_Rev1_5_G1_Union_Sweep_Export.py',
 'Tomahawk_Rev1_6_Automated_Native_Sweep.py']
TEMPLATE_DIR=BASE/'solver_templates'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def main():
    if DIST.exists(): shutil.rmtree(DIST)
    DIST.mkdir()
    copied=[]
    for name in FILES:
        src=BASE/name
        if not src.is_file(): raise FileNotFoundError(src)
        dst=DIST/name; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst); copied.append(dst)
    for src in sorted(TEMPLATE_DIR.glob('*')):
        if src.is_file():
            dst=DIST/'solver_templates'/src.name; dst.parent.mkdir(exist_ok=True); shutil.copy2(src,dst); copied.append(dst)
    manifest={'package_version':'REV1.7-MULTIPHYSICS-PREP-1.0','purpose':'CAD preparation and fail-closed external solver handoff',
              'physics_solvers_included':False,'files':{p.relative_to(DIST).as_posix():sha(p) for p in sorted(copied)}}
    (DIST/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(ARCHIVE,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(DIST.rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(DIST).as_posix())
    with zipfile.ZipFile(ARCHIVE) as z:
        assert z.testzip() is None
    print(json.dumps({'directory':str(DIST),'archive':str(ARCHIVE),'file_count':len(list(DIST.rglob('*'))),'archive_sha256':sha(ARCHIVE)},indent=2))

if __name__=='__main__': main()

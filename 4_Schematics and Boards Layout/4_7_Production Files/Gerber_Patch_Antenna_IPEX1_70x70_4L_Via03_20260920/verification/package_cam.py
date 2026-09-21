"""Build and fully read back the fabrication ZIP, with deterministic flat contents."""
from pathlib import Path
import hashlib, json, shutil, zipfile
OUT=Path(__file__).resolve().parent.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((OUT/'verification/export_manifest.json').read_text(encoding='utf8'))
audit=json.loads((OUT/'verification/gerber_readback_audit.json').read_text(encoding='utf8'))
assert audit['source_hashes_still_match'] and audit['physical_connectivity']['shorts_between_nets']==0
source=Path(manifest['source_project'])
for name,digest in manifest['source_hashes'].items(): assert sha(source/name)==digest
assert sha(OUT/'source/Phased_Array_Ant_IPEX1.kicad_pcb')==manifest['exported_board_sha256']
shutil.copy2(OUT/'fabrication_requirements.json',OUT/'source/fabrication_requirements.json')
job=json.loads((OUT/'cam/Phased_Array_Ant_IPEX1-job.gbrjob').read_text())
assert job['GeneralSpecs']['BoardThickness']==1 and job['GeneralSpecs']['Finish']=='OSP'
assert [l['Thickness'] for l in job['MaterialStackup'] if l['Type']=='Copper']==[.035,.0175,.0175,.035]
assert all('Thickness' not in l for l in job['MaterialStackup'] if l['Type']=='Dielectric')
files=sorted((OUT/'cam').iterdir())+[OUT/'README_制造说明.txt',OUT/'fabrication_requirements.json']
assert len(files)==15 and all(f.is_file() for f in files)
checks=OUT/'SHA256SUMS.txt'
checks.write_text(''.join(sha(f)+'  '+f.name+'\n' for f in files),encoding='utf8')
files.append(checks)
archive=OUT/'Phased_Array_Ant_IPEX1_70x70_4L_Gerber_20260920.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in files: z.write(f,f.name)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist())==len(files)==16
    assert set(z.namelist())=={f.name for f in files}
    for f in files: assert hashlib.sha256(z.read(f.name)).hexdigest()==sha(f)
report={'archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),'files':{f.name:sha(f) for f in files},'zip_crc_and_all_file_hashes_verified':True,'source_pcb_sha256':manifest['source_hashes']['Phased_Array_Ant_IPEX1.kicad_pcb'],'refilled_export_pcb_sha256':manifest['exported_board_sha256'],'scope':'Bare PCB fabrication; RF performance not validated; dielectric thickness proposal required from board fabricator.'}
(OUT/'verification/package_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False,indent=2))

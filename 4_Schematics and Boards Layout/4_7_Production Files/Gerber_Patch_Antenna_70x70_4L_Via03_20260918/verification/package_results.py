from pathlib import Path
import hashlib
import json
import tempfile
import zipfile

out=Path(__file__).resolve().parent.parent
base=out.parent/'Gerber_Patch_Antenna_70x70_4L_20260918'
name='Phased_Array_Ant_70x70_4L_Via03'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(base/'Phased_Array_Ant_70x70_4L_Gerber.zip') == '5578b5f0e56d0b0365d1d8d166a99c45e8dfd25ed91c8a52844280a0ac7a1c15'
audit=json.loads((out/'verification/gerber_readback_audit.json').read_text(encoding='utf8'))
assert audit['physical_connectivity']['all_17_nets_connected']
assert audit['drill_readback']['PTH_0.2mm']==0
assert audit['drill_readback']['PTH_0.3mm']==28
assert audit['enlarged_via_clearance']['minimum_measured_mm']>=0.1
files=sorted(p for p in (out/'cam').iterdir() if p.suffix in {'.gtl','.g1','.g2','.gbl','.gts','.gbs','.gto','.gbo','.gm1','.drl','.gbrjob'})
assert len(files)==12
files.append(out/'README_制造说明.md')
manifest={p.name:sha(p) for p in files}
checksums=out/'SHA256SUMS_Gerber.txt'
checksums.write_text('\n'.join(f'{v}  {k}' for k,v in manifest.items())+'\n',encoding='utf8')
files.append(checksums)
zpath=out/f'{name}_Gerber.zip'
with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files:
        z.write(p,p.name)
check_dir=out/'verification/zip_readback'
check_dir.mkdir(exist_ok=True)
with zipfile.ZipFile(zpath) as z:
    assert z.testzip() is None
    assert len(z.infolist())==14
    z.extractall(check_dir)
for filename,digest in manifest.items():
    assert sha(check_dir/filename)==digest
result={'zip':str(zpath),'sha256':sha(zpath),'members':14,'fresh_extraction_hash_check':True,
        'previous_zip_unchanged':True,'file_manifest':manifest}
(out/'verification/package_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k!='file_manifest'},ensure_ascii=False,indent=2))

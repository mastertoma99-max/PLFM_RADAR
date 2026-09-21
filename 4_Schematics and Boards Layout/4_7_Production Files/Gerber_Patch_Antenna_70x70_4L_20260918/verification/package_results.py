from pathlib import Path
import hashlib
import json
import shutil
import zipfile

out = Path(__file__).resolve().parent.parent
root = out.parents[1].parent
name = 'Phased_Array_Ant_70x70_4L'
original = root / '4_Schematics and Boards Layout/4_6_Schematics/Antennas/Patch/4x4/Phased_Array_Ant.brd'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(original) == '6d23e7cc4e6d95c0f24957db893b5fbe539984da62e5cb00274a3205890b6aa1'
assert sha(original) == sha(out / 'source/Phased_Array_Ant_original_6L.brd')
audit = json.loads((out / 'verification/gerber_readback_audit.json').read_text(encoding='utf8'))
assert audit['physical_connectivity']['all_17_nets_connected']
assert audit['drill_readback']['total_holes'] == 32

extensions = {'.gtl','.g1','.g2','.gbl','.gts','.gbs','.gto','.gbo','.gm1','.drl','.gbrjob'}
cam = sorted(p for p in (out / 'cam').iterdir() if p.suffix in extensions)
assert len(cam) == 12, [p.name for p in cam]
for p in (out / 'cam').glob('*drl_map.svg'):
    shutil.copy2(p, out / 'preview' / p.name)
manifest = {p.name: sha(p) for p in cam}
manifest['README_制造说明.md'] = sha(out / 'README_制造说明.md')
checksum = out / 'SHA256SUMS_Gerber.txt'
checksum.write_text('\n'.join(f'{digest}  {filename}' for filename,digest in manifest.items())+'\n',encoding='utf8')
zip_path = out / f'{name}_Gerber.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
    for p in cam:
        z.write(p,p.name)
    z.write(out/'README_制造说明.md','README_制造说明.md')
    z.write(checksum,checksum.name)
with zipfile.ZipFile(zip_path) as z:
    assert z.testzip() is None
    for filename,digest in manifest.items():
        assert hashlib.sha256(z.read(filename)).hexdigest() == digest
result = {'zip':str(zip_path),'zip_sha256':sha(zip_path),'zip_members':14,
          'source_original_unchanged':True,'file_manifest':manifest}
(out/'verification/package_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))

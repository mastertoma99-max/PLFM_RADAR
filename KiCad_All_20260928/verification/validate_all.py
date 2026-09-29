"""Read every delivered top-level schematic and PCB using KiCad CLI."""
from pathlib import Path
import collections, concurrent.futures, hashlib, json, subprocess, sys

OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parent
CLI=r'D:\3_Software\KiCAD\bin\kicad-cli.exe'
def run(args):
    r=subprocess.run([CLI]+list(map(str,args)),capture_output=True,encoding='utf-8',errors='replace')
    return {'returncode':r.returncode,'output':r.stdout+r.stderr}
def check(pro):
    d=pro.parent;name=pro.stem;sch=d/(name+'.kicad_sch')
    preview=OUT/'verification/previews'/name;preview.mkdir(parents=True,exist_ok=True)
    svg=run(['sch','export','svg','--exclude-drawing-sheet','-o',preview,sch])
    ercpath=OUT/'verification/ERC'/(name+'.json');ercpath.parent.mkdir(exist_ok=True)
    erc=run(['sch','erc','--format','json','-o',ercpath,sch])
    violations=[]
    if ercpath.is_file():
        data=json.loads(ercpath.read_text(encoding='utf-8'))
        for sheet in data.get('sheets',[]):violations+=sheet.get('violations',[])
    result={'project':name,'schematic_svg':svg,'rendered_sheets':len(list(preview.glob('*.svg'))),'erc_command':erc,'erc_counts_by_type':dict(collections.Counter(v.get('type','unknown') for v in violations)),'erc_counts_by_severity':dict(collections.Counter(v.get('severity','unknown') for v in violations))}
    pcb=d/(name+'.kicad_pcb')
    if pcb.exists():result['pcb_svg']=run(['pcb','export','svg','--mode-single','-l','F.Cu,Edge.Cuts','-o',OUT/'verification/pcb_previews'/(name+'.svg'),pcb])
    print(name,'sch',svg['returncode'],'sheets',result['rendered_sheets'],'pcb',result.get('pcb_svg',{}).get('returncode','n/a'),'ERC',result['erc_counts_by_severity'],flush=True)
    return result
if __name__=='__main__':
    (OUT/'verification/pcb_previews').mkdir(exist_ok=True)
    projects=sorted((OUT/'Hardware').glob('*/*.kicad_pro'))+sorted((OUT/'Simulations').glob('*/*.kicad_pro'))
    previous=[]
    if '--sim-only' in sys.argv:
        previous=[r for r in json.loads((OUT/'verification/final_validation.json').read_text(encoding='utf-8'))['projects'] if 'pcb_svg' in r]
        projects=[p for p in projects if p.parent.parent.name=='Simulations']
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(check,projects))
    results=previous+results
    unchanged=[]
    for row in json.loads((OUT/'source_inventory.json').read_text(encoding='utf-8')):
        for record in [row]+([row['board']] if 'board' in row else []):
            p=ROOT/record['path'];unchanged.append({'path':record['path'],'unchanged':hashlib.sha256(p.read_bytes()).hexdigest()==record['sha256']})
    report={'projects':results,'source_hashes':unchanged,'all_sources_unchanged':all(x['unchanged'] for x in unchanged)}
    (OUT/'verification/final_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert len(results)==14
    assert all(x['schematic_svg']['returncode']==0 and x.get('pcb_svg',{'returncode':0})['returncode']==0 for x in results)
    assert report['all_sources_unchanged']

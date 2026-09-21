"""Freeze the current IPEX1 source, check and export with installed KiCad 10."""
from pathlib import Path
import collections, hashlib, json, shutil, subprocess
import pcbnew as p

OUT=Path(__file__).resolve().parent.parent
ROOT=next(x for x in OUT.parents if (x/'.git').exists())
SRC=ROOT/'4_Schematics and Boards Layout/4_6_Schematics/Antennas/Patch/4x4/Phased_Array_Ant_IPEX1'
NAME='Phased_Array_Ant_IPEX1'
CLI=r'D:\3_Software\KiCAD\bin\kicad-cli.exe'
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
for d in ['source','cam','verification','preview']:(OUT/d).mkdir(parents=True,exist_ok=True)
manifest={}
files=[NAME+'.kicad_pcb',NAME+'.kicad_sch',NAME+'.kicad_pro','PLFM_RF.kicad_sym','sym-lib-table','fp-lib-table','README_修改说明.md','REVIEW_A2_复核说明.md','fabrication_requirements.json']
files += [str(f.relative_to(SRC)) for d in ['PLFM_RF.pretty','datasheets'] for f in (SRC/d).rglob('*') if f.is_file()]
for name in files:
    dst=OUT/'source'/name
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(SRC/name,dst)
    manifest[name]=sha(SRC/name)
board=OUT/'source'/f'{NAME}.kicad_pcb'
shutil.copy2(board,OUT/'verification/source_board_before_refill.kicad_pcb')
def run(*args):
    r=subprocess.run([CLI,*map(str,args)],cwd=OUT/'source',capture_output=True)
    print(r.stdout.decode('utf-8',errors='replace'),end='',flush=True)
    if r.returncode:raise RuntimeError(r.stderr.decode('utf-8',errors='replace'))
run('pcb','drc','--format','json','--all-track-errors','--severity-all','--schematic-parity','--refill-zones','--save-board','--exit-code-violations','-o',OUT/'verification/drc.json',board)
run('sch','erc','--format','json','--exit-code-violations','-o',OUT/'verification/erc.json',OUT/'source'/f'{NAME}.kicad_sch')
run('sch','export','netlist','--format','kicadxml','-o',OUT/'verification/schematic_netlist.xml',OUT/'source'/f'{NAME}.kicad_sch')
run('pcb','export','gerbers','--layers','F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts','--subtract-soldermask','--use-drill-file-origin','--precision','6','-o',OUT/'cam',board)
run('pcb','export','drill','--format','excellon','--drill-origin','plot','--excellon-units','mm','--excellon-zeros-format','decimal','--excellon-separate-th','--generate-report','--report-path',OUT/'verification/drill_report.txt','--generate-map','--map-format','svg','-o',OUT/'cam',board)
run('pcb','export','ipcd356','-o',OUT/'cam'/f'{NAME}.d356',board)

b=p.LoadBoard(str(board))
assert b.GetCopperLayerCount()==4
origin=b.GetDesignSettings().GetAuxOrigin()
xy=lambda v:[round(p.ToMM(v.x-origin.x),6),round(p.ToMM(origin.y-v.y),6)]
nodes={'origin_kicad_mm':[p.ToMM(origin.x),p.ToMM(origin.y)],'pads':[],'vias':[],'npth':[],'connectors':[]}
widths=collections.Counter()
for fp in b.GetFootprints():
    if fp.GetReference().startswith('J'):nodes['connectors'].append({'ref':fp.GetReference(),'xy':xy(fp.GetPosition()),'value':fp.GetValue()})
    for pad in fp.Pads():
        x,y=xy(pad.GetPosition())
        if pad.GetNetname():
            nodes['pads'].append({'ref':fp.GetReference(),'pad':pad.GetNumber(),'net':pad.GetNetname(),'layer':'F_Cu' if pad.GetLayerSet().Contains(p.F_Cu) else 'B_Cu','x':x,'y':y,'size_mm':[p.ToMM(pad.GetSize().x),p.ToMM(pad.GetSize().y)]})
        elif pad.GetDrillSize().x:
            nodes['npth'].append({'x':x,'y':y,'drill':round(p.ToMM(pad.GetDrillSize().x),6)})
for t in b.GetTracks():
    if isinstance(t,p.PCB_VIA):
        assert t.TopLayer()==p.F_Cu and t.BottomLayer()==p.B_Cu
        x,y=xy(t.GetPosition())
        nodes['vias'].append({'net':t.GetNetname(),'x':x,'y':y,'drill':round(p.ToMM(t.GetDrillValue()),6),'diameter':round(p.ToMM(t.GetWidth(p.F_Cu)),6)})
    else:widths[round(p.ToMM(t.GetWidth()),6)]+=1
assert len(nodes['connectors'])==16 and all(x['value']=='818000368' for x in nodes['connectors'])
assert len(nodes['pads'])==64 and len(nodes['vias'])==60 and len(nodes['npth'])==4
assert all(v['drill']==.3 for v in nodes['vias'])
(OUT/'verification/physical_net_nodes.json').write_text(json.dumps(nodes,indent=2),encoding='utf-8')
for name,digest in manifest.items():assert sha(SRC/name)==digest, f'Source changed during export: {name}'
report={'source_project':str(SRC),'source_hashes':manifest,'source_files_unchanged':True,'kicad_version':p.GetBuildVersion(),
        'exported_board_sha256':sha(board),'copper_layers':4,'board_size_mm':[70,70],
        'gerber_drill_origin':'Auxiliary origin; board lower-left = (0,0), unmirrored top-view coordinates',
        'trace_widths_mm_counts':dict(widths),'via_diameters_mm_counts':dict(collections.Counter(v['diameter'] for v in nodes['vias'])),
        'pth_count':60,'npth_count':4,'drill_mm':.3,
        'manufacturing_parameters':{'material':'FR4','finished_board_thickness_mm':1.0,'outer_copper_oz':1.0,'inner_copper_oz':0.5,'finish':'OSP','layer_order':['F.Cu','In1.Cu','In2.Cu','B.Cu'],'individual_dielectric_thickness':'fabricator to propose; not specified'}}
(OUT/'verification/export_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
for f in (OUT/'cam').glob('*drl_map.svg'):shutil.move(str(f),str(OUT/'preview'/f.name))
print(json.dumps(report,indent=2),flush=True)

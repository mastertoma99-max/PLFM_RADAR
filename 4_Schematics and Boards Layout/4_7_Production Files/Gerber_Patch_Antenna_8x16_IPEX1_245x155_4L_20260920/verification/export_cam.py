"""Freeze the 8x16 IPEX source and export bare-PCB CAM with installed KiCad."""
from pathlib import Path
import collections, hashlib, json, shutil, subprocess
import wx, pcbnew as p

APP = wx.App(False)
OUT = Path(__file__).resolve().parents[1]
ROOT = next(x for x in OUT.parents if (x/'.git').exists())
SRC = ROOT/'4_Schematics and Boards Layout/4_6_Schematics/Antennas/Patch/8x16/KiCad_8x16_IPEX1'
NAME = 'Patch_Anetnna_16_8_IPEX1'
CLI = r'D:\3_Software\KiCAD\bin\kicad-cli.exe'
sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
for d in ['source', 'cam', 'verification', 'preview']:
    (OUT/d).mkdir(parents=True, exist_ok=True)
files = [NAME+s for s in ['.kicad_pcb','.kicad_sch','.kicad_pro','.kicad_dru']]
files += ['PLFM_RF.kicad_sym','sym-lib-table','fp-lib-table','README_修改说明.md']
files += [str(f.relative_to(SRC)) for d in ['PLFM_RF.pretty','datasheets'] for f in (SRC/d).rglob('*') if f.is_file()]
manifest = {}
for rel in files:
    dst = OUT/'source'/rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC/rel, dst)
    manifest[rel] = sha(SRC/rel)
boardpath = OUT/'source'/f'{NAME}.kicad_pcb'
shutil.copy2(boardpath, OUT/'verification/source_board_as_received.kicad_pcb')
shutil.copy2(OUT/'source'/f'{NAME}.kicad_pro',OUT/'verification/source_project_as_received.kicad_pro')

def run(label, *args):
    r = subprocess.run([CLI, *map(str,args)], cwd=OUT/'source', capture_output=True)
    log = r.stdout.decode('utf8', errors='replace')+r.stderr.decode('utf8', errors='replace')
    (OUT/'verification'/f'{label}.log').write_text(log, encoding='utf8')
    print(label, 'exit', r.returncode, log[-1000:], flush=True)
    if r.returncode:
        raise RuntimeError(label)

# Enable the five inherited ignored DRC categories in the export copy only.
propath = OUT/'source'/f'{NAME}.kicad_pro'
pro = json.loads(propath.read_text(encoding='utf8'))
severities = pro['board']['design_settings']['rule_severities']
enabled = {k:v for k,v in severities.items() if v=='ignore'}
for k in enabled: severities[k]='warning'
propath.write_text(json.dumps(pro,ensure_ascii=False,indent=2),encoding='utf8')

board = p.LoadBoard(str(boardpath))
assert board.GetCopperLayerCount()==4
edges = [g for g in board.GetDrawings() if g.GetLayer()==p.Edge_Cuts]
points = [v for g in edges for v in [g.GetStart(), g.GetEnd()]]
xmin,xmax = min(v.x for v in points),max(v.x for v in points)
ymin,ymax = min(v.y for v in points),max(v.y for v in points)
assert (xmax-xmin,ymax-ymin)==(p.FromMM(245),p.FromMM(155))
board.GetDesignSettings().SetAuxOrigin(p.VECTOR2I(xmin,ymax))
p.SaveBoard(str(boardpath),board)
run('drc','pcb','drc','--format','json','--all-track-errors','--severity-all','--schematic-parity','--refill-zones','--save-board','-o',OUT/'verification/drc.json',boardpath)
run('erc','sch','erc','--format','json','-o',OUT/'verification/erc.json',OUT/'source'/f'{NAME}.kicad_sch')
run('netlist','sch','export','netlist','--format','kicadxml','-o',OUT/'verification/schematic_netlist.xml',OUT/'source'/f'{NAME}.kicad_sch')
run('gerber','pcb','export','gerbers','--layers','F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts','--subtract-soldermask','--use-drill-file-origin','--precision','6','-o',OUT/'cam',boardpath)
run('drill','pcb','export','drill','--format','excellon','--drill-origin','plot','--excellon-units','mm','--excellon-zeros-format','decimal','--excellon-separate-th','--generate-report','--report-path',OUT/'verification/drill_report.txt','--generate-map','--map-format','svg','-o',OUT/'cam',boardpath)
run('ipc356','pcb','export','ipcd356','-o',OUT/'cam'/f'{NAME}.d356',boardpath)

b = p.LoadBoard(str(boardpath))
origin = b.GetDesignSettings().GetAuxOrigin()
xy = lambda v:[round(p.ToMM(v.x-origin.x),6),round(p.ToMM(origin.y-v.y),6)]
vec = lambda v:[v.x,v.y]
def physical_snapshot(b):
    """Ignore only plot origin, display state and regenerated zone-fill caches."""
    return {
        'tracks':sorted((t.m_Uuid.AsString(),t.GetNetname(),t.GetLayer(),vec(t.GetStart()),vec(t.GetEnd()),t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,p.PCB_VIA) else 0) for t in b.GetTracks()),
        'pads':sorted((f.GetReference(),q.GetNumber(),q.GetNetname(),q.GetAttribute(),vec(q.GetPosition()),vec(q.GetSize()),vec(q.GetDrillSize()),q.GetLayerSet().FmtBin()) for f in b.GetFootprints() for q in f.Pads()),
        'drawings':sorted((g.m_Uuid.AsString(),g.GetLayer(),g.GetShape(),vec(g.GetStart()),vec(g.GetEnd()),g.GetWidth(),g.GetNetname()) for g in b.GetDrawings() if isinstance(g,p.PCB_SHAPE)),
        'zones':sorted((z.GetLayer(),z.GetNetname(),[vec(z.Outline().COutline(0).CPoint(i)) for i in range(z.Outline().COutline(0).PointCount())]) for z in b.Zones()),
        'layers':b.GetCopperLayerCount(), 'thickness':b.GetDesignSettings().GetBoardThickness()
    }
before = p.LoadBoard(str(SRC/f'{NAME}.kicad_pcb'))
assert physical_snapshot(before)==physical_snapshot(b)
nodes = {'origin_kicad_mm':[p.ToMM(origin.x),p.ToMM(origin.y)],'pads':[],'vias':[],'npth':[],'connectors':[],'patches':[]}
for f in b.GetFootprints():
    if f.GetReference().startswith('J'):
        nodes['connectors'].append({'ref':f.GetReference(),'xy':xy(f.GetPosition()),'value':f.GetValue()})
    for q in f.Pads():
        x,y = xy(q.GetPosition())
        if q.GetNetname():
            nodes['pads'].append({'ref':f.GetReference(),'pad':q.GetNumber(),'net':q.GetNetname(),'layer':'F_Cu','x':x,'y':y,'size_mm':[p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y)]})
            assert q.GetAttribute()==p.PAD_ATTRIB_SMD and q.GetLayerSet().Contains(p.F_Cu)
        elif q.GetDrillSize().x:
            assert q.GetAttribute()==p.PAD_ATTRIB_NPTH
            nodes['npth'].append({'x':x,'y':y,'drill':round(p.ToMM(q.GetDrillSize().x),6)})
widths = collections.Counter()
for t in b.GetTracks():
    if isinstance(t,p.PCB_VIA):
        assert t.TopLayer()==p.F_Cu and t.BottomLayer()==p.B_Cu
        x,y=xy(t.GetPosition())
        nodes['vias'].append({'net':t.GetNetname(),'x':x,'y':y,'drill':round(p.ToMM(t.GetDrillValue()),6),'diameter':round(p.ToMM(t.GetWidth(p.F_Cu)),6)})
    else: widths[round(p.ToMM(t.GetWidth()),6)]+=1
for g in b.GetDrawings():
    if g.GetLayer()==p.F_Cu:
        assert isinstance(g,p.PCB_SHAPE) and g.GetShape()==p.SHAPE_T_RECT and g.IsSolidFill()
        a,c=xy(g.GetStart()),xy(g.GetEnd())
        nodes['patches'].append({'net':g.GetNetname(),'bounds':[min(a[0],c[0]),min(a[1],c[1]),max(a[0],c[0]),max(a[1],c[1])]})
assert len(nodes['pads'])==48 and len(nodes['vias'])==127 and len(nodes['npth'])==4 and len(nodes['patches'])==128
assert all(v['net']=='GND' for v in nodes['vias'])
assert all(v['value']=='818000368' for v in nodes['connectors'])
(OUT/'verification/physical_net_nodes.json').write_text(json.dumps(nodes,indent=2),encoding='utf8')
drc = json.loads((OUT/'verification/drc.json').read_text(encoding='utf8'))
assert not [v for v in drc['violations'] if v['severity']=='error']
assert not drc['unconnected_items'] and not drc['schematic_parity'] and not drc['ignored_checks']
for rel,digest in manifest.items(): assert sha(SRC/rel)==digest
report = {'source_project':str(SRC),'source_hashes':manifest,'source_files_unchanged':True,'physical_geometry_unchanged':True,'kicad_version':p.GetBuildVersion(),
    'exported_board_sha256':sha(boardpath),'copper_layers':4,'board_size_mm':[245,155],'origin':'lower left (0,0), unmirrored top view',
    'trace_widths_mm_counts':dict(widths),'via_object_count':127,'via_drill_counts':dict(collections.Counter(v['drill'] for v in nodes['vias'])),
    'unique_via_positions':len({(v['x'],v['y'],v['drill']) for v in nodes['vias']}),'npth':nodes['npth'],
    'originally_ignored_DRC_checks_enabled_as_warnings':enabled,'drc_warning_counts':dict(collections.Counter(v['type'] for v in drc['violations'])),
    'unconfirmed_CAD_board_thickness_mm':p.ToMM(b.GetDesignSettings().GetBoardThickness()),'manufacturing_parameters':'material, thickness, copper weights, finish, dielectric thicknesses and impedance requirements TBD'}
(OUT/'verification/export_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
for f in (OUT/'cam').glob('*drl_map.svg'): shutil.move(str(f),str(OUT/'preview'/f.name))
print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},ensure_ascii=False,indent=2),flush=True)

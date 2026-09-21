"""Create a separate 198x155 mm layout candidate, keeping all 16 RF columns."""
from pathlib import Path
import collections, hashlib, json, math, shutil, subprocess
import wx, pcbnew as p
APP=wx.App(False)
OUT=Path(__file__).resolve().parents[1]
SRC=OUT.parent/'KiCad_8x16_IPEX1'
OLD='Patch_Anetnna_16_8_IPEX1'
NAME=OLD+'_198x155'
CLI=r'D:\3_Software\KiCAD\bin\kicad-cli.exe'
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
for d in ['verification','preview','verification/cam_readback']:(OUT/d).mkdir(parents=True,exist_ok=True)
source_hashes={}
for suffix in ['.kicad_pcb','.kicad_sch','.kicad_pro','.kicad_dru']:
    f=SRC/(OLD+suffix);source_hashes[f.name]=sha(f)
    shutil.copy2(f,OUT/(NAME+suffix))
for f in ['sym-lib-table','fp-lib-table','PLFM_RF.kicad_sym']:
    shutil.copy2(SRC/f,OUT/f);source_hashes[f]=sha(SRC/f)
for dirname in ['PLFM_RF.pretty','datasheets']:shutil.copytree(SRC/dirname,OUT/dirname,dirs_exist_ok=True)
schpath=OUT/(NAME+'.kicad_sch')
s=schpath.read_text(encoding='utf8').replace('(project "'+OLD+'"','(project "'+NAME+'"')
s=s.replace('All 128 patch copper rectangles, array spacing and the 4-layer board are retained.',
    '198 x 155 mm layout candidate: 128 original-size patches, 12 mm column pitch, 4 layers. RF validation pending.')
schpath.write_text(s,encoding='utf8')
propath=OUT/(NAME+'.kicad_pro')
pro=json.loads(propath.read_text(encoding='utf8').replace(OLD+'.kicad_sch',NAME+'.kicad_sch').replace(OLD+'.kicad_pro',NAME+'.kicad_pro'))
for k,v in pro['board']['design_settings']['rule_severities'].items():
    if v=='ignore':pro['board']['design_settings']['rule_severities'][k]='warning'
pro['text_variables']['LAYOUT_REVISION']='198x155, 12 mm column pitch; RF validation pending'
propath.write_text(json.dumps(pro,ensure_ascii=False,indent=2),encoding='utf8')
b=p.LoadBoard(str(OUT/(NAME+'.kicad_pcb')))
source=p.LoadBoard(str(SRC/(OLD+'.kicad_pcb')))
original_ipex=json.loads((SRC/'verification/build_audit.json').read_text(encoding='utf8'))
ipex_via_column={v['uuid']:c['column']-1 for c in original_ipex['changes'] for v in c['ground_vias']}
patches=[g for g in b.GetDrawings() if g.GetLayer()==p.F_Cu]
edges=[g for g in b.GetDrawings() if g.GetLayer()==p.Edge_Cuts]
left=min(g.GetStart().x for g in edges);top=min(g.GetStart().y for g in edges);bottom=max(g.GetStart().y for g in edges)
assert max(g.GetStart().x for g in edges)-left==p.FromMM(245)
oldcenters=sorted({(g.GetStart().x+g.GetEnd().x)//2 for g in patches})
assert len(oldcenters)==16
newcenters=[left+p.FromMM(9+12*i) for i in range(16)]
deltas=[new-old for new,old in zip(newcenters,oldcenters)]
net_col={g.GetNetname():oldcenters.index((g.GetStart().x+g.GetEnd().x)//2) for g in patches}
nearest=lambda x:min(range(16),key=lambda i:abs(x-oldcenters[i]))
changes=[]
for g in b.GetDrawings():
    if g.GetLayer()==p.F_Cu:g.Move(p.VECTOR2I(deltas[net_col[g.GetNetname()]],0))
    elif g.GetLayer()==p.Edge_Cuts:
        for get,setter in [(g.GetStart,g.SetStart),(g.GetEnd,g.SetEnd)]:
            q=get()
            if q.x>left+p.FromMM(200):q=p.VECTOR2I(q.x-p.FromMM(47),q.y)
            setter(q)
    elif isinstance(g,p.PCB_TEXT):g.Move(p.VECTOR2I(deltas[nearest(g.GetPosition().x)],0))
for f in b.GetFootprints():
    if f.GetReference().startswith('J'):
        sig=next(q for q in f.Pads() if q.GetNumber()=='1').GetNetname();i=net_col[sig]
        old=f.GetPosition();f.Move(p.VECTOR2I(deltas[i],0))
        changes.append({'ref':f.GetReference(),'column':i+1,'net':sig,'old_center_mm':[p.ToMM(old.x-left),p.ToMM(bottom-old.y)],'new_center_mm':[p.ToMM(f.GetPosition().x-left),p.ToMM(bottom-f.GetPosition().y)]})
    elif f.GetPosition().x>left+p.FromMM(200):f.Move(p.VECTOR2I(-p.FromMM(47),0))
via_moves=[]
for t in b.GetTracks():
    if isinstance(t,p.PCB_VIA):
        old=t.GetPosition();u=t.m_Uuid.AsString()
        if u in ipex_via_column:
            i=ipex_via_column[u];t.Move(p.VECTOR2I(deltas[i],0));method='rigid connector-column translation'
        else:
            x=newcenters[0]+round((old.x-oldcenters[0])*12/14.34)
            t.SetPosition(p.VECTOR2I(x,old.y));method='original ground-via X redistribution; diameter unchanged'
        via_moves.append({'uuid':u,'old_xy':[p.ToMM(old.x-left),p.ToMM(bottom-old.y)],'new_xy':[p.ToMM(t.GetPosition().x-left),p.ToMM(bottom-t.GetPosition().y)],'method':method})
    else:
        i=net_col[t.GetNetname()] if t.GetNetname()!='GND' else nearest((t.GetStart().x+t.GetEnd().x)//2)
        t.Move(p.VECTOR2I(deltas[i],0))
for z in b.Zones():
    outline=z.Outline()
    assert outline.OutlineCount()==1 and outline.HoleCount(0)==0
    chain=outline.COutline(0)
    points=[p.VECTOR2I(chain.CPoint(i).x,chain.CPoint(i).y) for i in range(chain.PointCount())]
    for i,q in enumerate(points):
        if q.x>left+p.FromMM(200):outline.SetVertex(i,p.VECTOR2I(q.x-p.FromMM(47),q.y))
b.GetDesignSettings().SetAuxOrigin(p.VECTOR2I(left,bottom))
title=b.GetTitleBlock();title.SetTitle('8x16 IPEX antenna - 198 x 155 mm layout candidate');title.SetRevision('IPEX1-COMPACT-A1');title.SetDate('2026-09-21')
title.SetComment(0,'12 mm column pitch. RF validation and fabrication stackup pending.')
p.SaveBoard(str(OUT/(NAME+'.kicad_pcb')),b)
def run(label,*args):
    r=subprocess.run([CLI,*map(str,args)],cwd=OUT,capture_output=True)
    log=r.stdout.decode('utf8',errors='replace')+r.stderr.decode('utf8',errors='replace')
    (OUT/'verification'/f'{label}.log').write_text(log,encoding='utf8')
    print(label,r.returncode,log[-500:],flush=True)
    if r.returncode:raise RuntimeError(label)
run('drc','pcb','drc','--format','json','--all-track-errors','--severity-all','--schematic-parity','--refill-zones','--save-board','-o',OUT/'verification/drc.json',OUT/(NAME+'.kicad_pcb'))
run('erc','sch','erc','--format','json','-o',OUT/'verification/erc.json',schpath)
run('netlist','sch','export','netlist','--format','kicadxml','-o',OUT/'verification/schematic_netlist.xml',schpath)
run('gerber_readback','pcb','export','gerbers','--layers','F.Cu,In1.Cu,In2.Cu,B.Cu,Edge.Cuts','--use-drill-file-origin','-o',OUT/'verification/cam_readback',OUT/(NAME+'.kicad_pcb'))
run('svg','pcb','export','svg','--layers','F.Cu,Edge.Cuts','--mode-single','--page-size-mode','2','--exclude-drawing-sheet','-o',OUT/'preview/PCB_top.svg',OUT/(NAME+'.kicad_pcb'))

# Independent source-versus-candidate geometry invariants.
final=p.LoadBoard(str(OUT/(NAME+'.kicad_pcb')))
olditems={g.m_Uuid.AsString():g for g in source.GetDrawings() if g.GetLayer()==p.F_Cu}
for g in final.GetDrawings():
    if g.GetLayer()!=p.F_Cu:continue
    a=olditems[g.m_Uuid.AsString()]
    assert g.GetEnd()-g.GetStart()==a.GetEnd()-a.GetStart()
    assert g.GetStart().y==a.GetStart().y and g.GetEnd().y==a.GetEnd().y
    assert g.GetNetname()==a.GetNetname() and g.IsSolidFill() and g.GetWidth()==a.GetWidth()
oldtracks={t.m_Uuid.AsString():t for t in source.GetTracks()}
for t in final.GetTracks():
    a=oldtracks[t.m_Uuid.AsString()]
    assert t.GetNetname()==a.GetNetname()
    if isinstance(t,p.PCB_VIA):
        assert t.GetDrillValue()==a.GetDrillValue() and t.GetWidth(p.F_Cu)==a.GetWidth(p.F_Cu)
        assert t.GetPosition().y==a.GetPosition().y
    else:
        assert t.GetWidth()==a.GetWidth() and t.GetLayer()==a.GetLayer()
        assert t.GetEnd()-t.GetStart()==a.GetEnd()-a.GetStart()
oldfps={f.GetReference():f for f in source.GetFootprints()}
for f in final.GetFootprints():
    old=oldfps[f.GetReference()]
    assert f.GetValue()==old.GetValue() and f.GetLayer()==old.GetLayer() and f.GetOrientationDegrees()==old.GetOrientationDegrees()
    oldpads={q.GetNumber():q for q in old.Pads()}
    for q in f.Pads():
        a=oldpads[q.GetNumber()]
        assert q.GetPosition()-f.GetPosition()==a.GetPosition()-old.GetPosition()
        assert q.GetSize()==a.GetSize() and q.GetDrillSize()==a.GetDrillSize() and q.GetNetname()==a.GetNetname()
for name,digest in source_hashes.items():assert sha(SRC/name)==digest
origin=final.GetDesignSettings().GetAuxOrigin()
xy=lambda v:[round(p.ToMM(v.x-origin.x),6),round(p.ToMM(origin.y-v.y),6)]
nodes={'pads':[],'vias':[],'patches':[]}
for f in final.GetFootprints():
    for q in f.Pads():
        if q.GetNetname():
            x,y=xy(q.GetPosition());nodes['pads'].append({'ref':f.GetReference(),'pad':q.GetNumber(),'net':q.GetNetname(),'x':x,'y':y})
for t in final.GetTracks():
    if isinstance(t,p.PCB_VIA):
        x,y=xy(t.GetPosition());nodes['vias'].append({'net':t.GetNetname(),'x':x,'y':y,'drill':p.ToMM(t.GetDrillValue()),'diameter':p.ToMM(t.GetWidth(p.F_Cu))})
for g in final.GetDrawings():
    if g.GetLayer()==p.F_Cu:
        a,c=xy(g.GetStart()),xy(g.GetEnd());nodes['patches'].append({'net':g.GetNetname(),'bounds':[min(a[0],c[0]),min(a[1],c[1]),max(a[0],c[0]),max(a[1],c[1])]})
(OUT/'verification/physical_net_nodes.json').write_text(json.dumps(nodes,indent=2),encoding='utf8')
drc=json.loads((OUT/'verification/drc.json').read_text(encoding='utf8'))
report={'source_project':str(SRC),'source_hashes':source_hashes,'source_unchanged':True,'board_size_mm':[198,155],'column_pitch_mm':12,
    'patch_count':128,'connector_count':16,'left_and_right_patch_margin_mm':5.07,'individual_patch_dimensions_and_vertical_positions_unchanged':True,
    'feed_segment_lengths_widths_and_relative_shapes_unchanged':True,'via_drills_diameters_and_Y_unchanged':True,'copper_layers':final.GetCopperLayerCount(),
    'connector_moves':sorted(changes,key=lambda c:c['column']),'via_moves':via_moves,'DRC_counts':dict(collections.Counter((v['severity']+':'+v['type']) for v in drc['violations'])),
    'unconnected':len(drc['unconnected_items']),'schematic_parity':len(drc['schematic_parity']),'RF_status':'Layout candidate; ideal array-factor estimate only; full-wave RF validation not performed.'}
(OUT/'verification/compact_layout_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k not in ['source_hashes','connector_moves','via_moves']},ensure_ascii=False,indent=2))

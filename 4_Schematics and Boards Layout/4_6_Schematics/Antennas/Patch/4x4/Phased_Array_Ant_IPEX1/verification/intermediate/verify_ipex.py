from pathlib import Path
import json, hashlib, collections, xml.etree.ElementTree as E
import pcbnew as p

ROOT=next(d for d in Path(__file__).resolve().parents if (d/'.git').exists() and (d/'4_Schematics and Boards Layout').exists())
OUT=ROOT/'4_Schematics and Boards Layout/4_6_Schematics/Antennas/Patch/4x4/Phased_Array_Ant_IPEX1'
audit=json.loads((OUT/'verification/build_audit.json').read_text(encoding='utf-8'))
old=p.LoadBoard(audit['source_board'])
new=p.LoadBoard(str(OUT/'Phased_Array_Ant_IPEX1.kicad_pcb'))
mm=lambda v: round(p.ToMM(v),6)
xy=lambda v:[mm(v.x),mm(v.y)]
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
assert sha(audit['source_board'])==audit['source_board_sha256']
assert sha(audit['source_schematic'])==audit['source_schematic_sha256']
assert sha(OUT/'datasheets/ECT_818000368_SPEC_E.pdf')==audit['datasheet_sha256']
def pads(b,kind):
 return sorted([[f.GetReference(),pad.GetNumber(),pad.GetNetname(),xy(pad.GetPosition()),xy(pad.GetSize()),xy(pad.GetDrillSize()),pad.GetLayerSet().FmtBin()]
  for f in b.GetFootprints() if kind(f.GetReference()) for pad in f.Pads()])
assert pads(old,lambda r:r.startswith('U$'))==pads(new,lambda r:r.startswith('U$'))
assert pads(old,lambda r:r.startswith('UNK_HOLE'))==pads(new,lambda r:r.startswith('UNK_HOLE'))
def geom(b):
 return sorted([[type(s).__name__,s.GetLayer(),xy(s.GetStart()),xy(s.GetEnd()),mm(s.GetWidth())] for s in b.GetDrawings() if isinstance(s,p.PCB_SHAPE)])
assert geom(old)==geom(new)
def tr(t):
 return [type(t).__name__,t.GetNetname(),t.GetLayer(),xy(t.GetStart()),xy(t.GetEnd()),mm(t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth()),mm(t.GetDrillValue()) if isinstance(t,p.PCB_VIA) else 0]
before={t.m_Uuid.AsString():tr(t) for t in old.GetTracks()}
after={t.m_Uuid.AsString():tr(t) for t in new.GetTracks()}
removed=[before[k] for k in before.keys()-after.keys()]
added=[after[k] for k in after.keys()-before.keys()]
changed=[(before[k],after[k]) for k in before.keys()&after.keys() if before[k]!=after[k]]
assert len(removed)==45 and all(t[0]=='PCB_TRACK' and t[1]=='GND' and t[2]==p.B_Cu for t in removed)
assert len(added)==64 and collections.Counter(t[0] for t in added)=={'PCB_VIA':32,'PCB_TRACK':32}
assert all(t[1]=='GND' for t in added)
assert len(changed)==16 and all(a[0]=='PCB_TRACK' and a[2]==p.B_Cu and a[1].startswith('N$') for a,b in changed)
assert all(a[1:3]==b[1:3] and a[4:]==b[4:] for a,b in changed)
vias=[t for t in new.GetTracks() if isinstance(t,p.PCB_VIA)]
assert len(vias)==60 and all(mm(v.GetDrillValue())==.3 for v in vias)
assert all(v.TopLayer()==p.F_Cu and v.BottomLayer()==p.B_Cu for v in vias)
assert len([v for v in vias if v.GetNetname().startswith('N$')])==16
assert new.GetCopperLayerCount()==4
net=E.parse(OUT/'verification/schematic_netlist.xml')
net_nodes={n.attrib['name']:sorted((z.attrib['ref'],z.attrib['pin']) for z in n.findall('node')) for n in net.findall('.//nets/net')}
expected={'GND':sorted((f'J{i}',pin) for i in range(1,17) for pin in ['2','3'])}
for i in range(1,17):expected[f'N${i}']=[(f'J{i}','1'),(f'U${i}','P$1')]
assert net_nodes==expected,(net_nodes,expected)
actual={}
for f in new.GetFootprints():
 for pad in f.Pads():
  if pad.GetNetname():actual.setdefault(pad.GetNetname(),[]).append((f.GetReference(),pad.GetNumber()))
assert {k:sorted(v) for k,v in actual.items()}==expected
for f in new.GetFootprints():
 if not f.GetReference().startswith('J'):continue
 assert f.GetValue()=='818000368' and f.GetLayer()==p.B_Cu
 assert set(x.GetNumber() for x in f.Pads())=={'1','2','3'}
 for pad in f.Pads():
  assert xy(pad.GetSize())==([1,1.05] if pad.GetNumber()=='1' else [1.05,2.2])
  pos=pad.GetPosition()-f.GetPosition()
  assert xy(pos)==({'1':[0,-1.525],'2':[-1.475,0],'3':[1.475,0]}[pad.GetNumber()])
  assert pad.GetLayerSet().Contains(p.B_Cu) and not pad.GetLayerSet().Contains(p.F_Cu)
 assert f.GetPath().AsString()=='/'+audit['root_uuid']+'/'+audit['symbol_uuids'][f.GetReference()]
drc=json.loads((OUT/'verification/drc.json').read_text(encoding='utf-8'))
assert not drc['violations'] and not drc['unconnected_items'] and not drc['schematic_parity']
erc=json.loads((OUT/'verification/erc.json').read_text(encoding='utf-8'))
assert all(not s.get('violations') for s in erc['sheets'])
result={'source_hashes_unchanged':True,'datasheet_copy_identical':True,'antenna_pad_geometry_layers_and_nets_identical':True,
 'board_outline_and_drawings_identical':True,'mounting_holes_identical':True,'copper_layers':4,
 'source_signal_vias_and_top_signal_tracks_unchanged':True,'signals':16,'all_nets':17,
 'replaced_connectors':16,'connector_pad_dimensions_and_bottom_mirroring_verified':True,
 'schematic_to_pcb_all_net_nodes_exact_match':True,'schematic_uuids_linked_to_board':True,
 'pth_count':60,'all_pth_drills_mm':.3,'new_ground_vias':32,'changed_bottom_signal_tracks':len(changed),
 'erc_violations':0,'drc_violations':0,'unconnected_items':0,'schematic_parity_issues':0,
 'drc_disabled_checks_inherited_or_default':drc['ignored_checks'],
 'rf_validation':'Not performed; connector datasheet rated DC-6GHz while patch is labelled 10.5GHz'}
(OUT/'verification/final_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))

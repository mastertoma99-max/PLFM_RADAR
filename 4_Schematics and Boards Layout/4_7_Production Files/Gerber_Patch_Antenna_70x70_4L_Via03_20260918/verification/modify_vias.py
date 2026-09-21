"""Create a separate 0.3 mm signal-via revision from the verified four-layer copy."""
from pathlib import Path
import collections
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
import pcbnew as pcb
import wx

OUT = Path(__file__).resolve().parent.parent
BASE = OUT.parent / 'Gerber_Patch_Antenna_70x70_4L_20260918'
NAME = 'Phased_Array_Ant_70x70_4L_Via03'
OLDNAME = 'Phased_Array_Ant_70x70_4L'
for folder in ('source', 'cam', 'verification', 'preview'):
    (OUT / folder).mkdir(exist_ok=True)
app = wx.App(False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
source = BASE / f'source/{OLDNAME}.brd'
pcb_source = BASE / f'source/{OLDNAME}.kicad_pcb'
old_archive = BASE / f'{OLDNAME}_Gerber.zip'
assert sha(old_archive) == '5578b5f0e56d0b0365d1d8d166a99c45e8dfd25ed91c8a52844280a0ac7a1c15'
text = source.read_text(encoding='utf8')
pattern = r'(<via\b[^>]*\bdrill=")0\.2("[^>]*/>)'
revised, count = re.subn(pattern, lambda m: m[1]+'0.3'+m[2].replace('/>', ' diameter="0.6"/>'), text)
assert count == 16
eagle_out = OUT / f'source/{NAME}.brd'
eagle_out.write_text(revised, encoding='utf8', newline='\n')
old_xml, new_xml = ET.fromstring(text), ET.fromstring(revised)
changes = []
for sig in new_xml.findall('./drawing/board/signals/signal'):
    for v in sig.findall('via'):
        if v.get('diameter') == '0.6':
            changes.append({'net':sig.get('name'), 'x':float(v.get('x')), 'y':float(v.get('y')),
                            'old_drill_mm':0.2, 'new_drill_mm':0.3,
                            'old_pad_mm':0.4, 'new_pad_mm':0.6,
                            'new_nominal_radial_annulus_mm':0.15})
            v.set('drill', '0.2')
            del v.attrib['diameter']
assert ET.tostring(old_xml) == ET.tostring(new_xml), 'Unexpected change outside 16 vias'

board = pcb.LoadBoard(str(pcb_source))
before = []
for v in board.GetTracks():
    if isinstance(v, pcb.PCB_VIA) and v.GetDrillValue() == pcb.FromMM(0.2):
        assert all(v.GetWidth(l) == pcb.FromMM(0.4) for l in (pcb.F_Cu, pcb.In1_Cu, pcb.In2_Cu, pcb.B_Cu))
        before.append((v.GetNetname(), v.GetPosition().x, v.GetPosition().y))
        v.SetDrill(pcb.FromMM(0.3))
        for layer in (pcb.F_Cu, pcb.In1_Cu, pcb.In2_Cu, pcb.B_Cu):
            v.SetWidth(layer, pcb.FromMM(0.6))
assert len(before) == 16
counts = collections.Counter((v.GetDrillValue(),v.GetWidth(pcb.F_Cu)) for v in board.GetTracks() if isinstance(v,pcb.PCB_VIA))
assert counts == {(300000,600000):16, (300000,500000):12}, counts
new_pcb = OUT / f'source/{NAME}.kicad_pcb'
assert pcb.SaveBoard(str(new_pcb), board)
project = json.loads((BASE/f'source/{OLDNAME}.kicad_pro').read_text(encoding='utf8'))
project['meta']['filename'] = NAME+'.kicad_pro'
(OUT/f'source/{NAME}.kicad_pro').write_text(json.dumps(project,indent=2),encoding='utf8')

# Independently import modified EAGLE to check its signal wires and vias agree.
imported = pcb.PCB_IO_MGR.Load(pcb.PCB_IO_MGR.EAGLE, str(eagle_out), pcb.BOARD())
def route_signature(b):
    result = []
    for t in b.GetTracks():
        if isinstance(t,pcb.PCB_VIA):
            result.append(('via',t.GetNetname(),t.GetPosition().x,t.GetPosition().y,t.GetDrillValue(),
                           *(t.GetWidth(l) for l in (pcb.F_Cu,pcb.In1_Cu,pcb.In2_Cu,pcb.B_Cu))))
        else:
            result.append(('track',t.GetNetname(),t.GetLayer(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,t.GetWidth()))
    return sorted(result)
assert route_signature(board) == route_signature(imported)

nodes = {'pads':[], 'vias':[]}
for fp in board.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname():
            nodes['pads'].append({'ref':fp.GetReference(),'pad':p.GetNumber(),'net':p.GetNetname(),
                'x':p.GetPosition().x/1e6,'y':-p.GetPosition().y/1e6,
                'layer':'B_Cu' if p.GetLayerSet().Contains(pcb.B_Cu) else 'F_Cu'})
for v in board.GetTracks():
    if isinstance(v,pcb.PCB_VIA):
        nodes['vias'].append({'net':v.GetNetname(),'x':v.GetPosition().x/1e6,
                             'y':-v.GetPosition().y/1e6,'drill':v.GetDrillValue()/1e6})
(OUT/'verification/physical_net_nodes.json').write_text(json.dumps(nodes,indent=2),encoding='utf8')
shutil.copy2(BASE/'verification/drc_4L.json',OUT/'verification/drc_Via02_reference.json')
report = {'baseline_eagle':str(source),'baseline_eagle_sha256':sha(source),
          'baseline_kicad_sha256':sha(pcb_source),'baseline_zip_sha256':sha(old_archive),
          'modified_eagle_sha256':sha(eagle_out), 'modified_vias':changes,
          'eagle_only_16_via_hole_and_pad_sizes_changed':True,
          'modified_eagle_vs_kicad_all_tracks_and_vias_match':True,
          'layers':4,'via_extent':'through all four copper layers',
          'PTH_holes_0.3mm':28, 'NPTH_holes_3.2mm':4,
          'ground_vias_unchanged':'12 x 0.3 mm hole / 0.5 mm pad',
          'material_and_thickness':'TBD; no RF equivalence or simulation asserted'}
(OUT/'verification/via_change_audit.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2),flush=True)

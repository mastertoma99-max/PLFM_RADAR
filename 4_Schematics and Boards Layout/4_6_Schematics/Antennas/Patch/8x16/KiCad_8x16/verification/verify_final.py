"""Read-only verification of final imported files and their source."""
from pathlib import Path
import collections
import hashlib
import json
import xml.etree.ElementTree as ET
import pcbnew as pcb
import wx

OUT = Path(__file__).resolve().parents[1]
NAME = 'Patch_Anetnna_16_8'
app = wx.App(False)
board = pcb.LoadBoard(str(OUT / (NAME + '.kicad_pcb')))
baseline = pcb.LoadBoard(str(OUT / 'verification/native_import' / (NAME + '.kicad_pcb')))
def xy(p):
    return (p.x, p.y)
def snapshot(b):
    return {
        'tracks_and_vias': sorted((type(t).__name__, xy(t.GetStart()), xy(t.GetEnd()), t.GetLayer(), t.GetWidth(pcb.F_Cu) if isinstance(t, pcb.PCB_VIA) else t.GetWidth(), t.GetDrillValue() if isinstance(t, pcb.PCB_VIA) else 0) for t in b.GetTracks()),
        'pads': sorted((fp.GetReference(), p.GetNumber(), xy(p.GetPosition()), xy(p.GetSize()), xy(p.GetDrillSize()), p.GetShape(), p.GetOrientationDegrees(), str(p.GetLayerSet().FmtHex())) for fp in b.GetFootprints() for p in fp.Pads()),
        'footprints': sorted((fp.GetReference(), fp.GetValue(), xy(fp.GetPosition()), fp.GetOrientationDegrees(), fp.GetLayer()) for fp in b.GetFootprints()),
    }
assert snapshot(board) == snapshot(baseline)
patches = [g for g in board.GetDrawings() if g.GetLayer() == pcb.F_Cu]
assert len(patches) == 128
assert all(g.GetShape() == pcb.SHAPE_T_RECT and g.IsSolidFill() and g.GetWidth() == 0 and g.GetNetname() for g in patches)
assert sorted(collections.Counter(g.GetNetname() for g in patches).values()) == [8] * 16
assert board.GetCopperLayerCount() == 4
drc = json.loads((OUT / 'verification/drc.json').read_text(encoding='utf-8'))
assert not drc['unconnected_items']
assert not [v for v in drc['violations'] if v['severity'] == 'error']
netlist = ET.parse(OUT / 'verification/netlist.xml')
ground = netlist.find('./nets/net[@name="GND"]')
source = ET.parse(OUT.parent / (NAME + '.brd')).find('./drawing/board')
expected_ground = {(p.attrib['element'], p.attrib['pad']) for p in source.findall('./signals/signal[@name="GND"]/contactref')}
assert expected_ground == {(n.attrib['ref'], n.attrib['pin']) for n in ground.findall('node')}
assert len(netlist.findall('./components/comp')) == 16
audit = json.loads((OUT / 'verification/import_audit.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((OUT.parent / (NAME + suffix)).read_bytes()).hexdigest() == expected for suffix, expected in audit['source_hashes'].items())
result = {
    'source_hashes_unchanged': True,
    'track_via_pad_footprint_geometry_unchanged_from_native_import': True,
    '128_exact_rectangles_16_nets_8_patches_each': True,
    'source_ground_contacts_match_schematic': True,
    'drc_errors': 0, 'drc_unconnected': 0,
    'drc_warnings': dict(collections.Counter(v['type'] for v in drc['violations'])),
    'output_sha256': {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in OUT.iterdir() if f.suffix in ('.kicad_pcb', '.kicad_sch', '.kicad_pro')},
}
(OUT / 'verification/final_verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))

"""Read-only geometry, library, connectivity and rule-check verification."""
from pathlib import Path
import collections
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import pcbnew as pcb
import wx

APP = wx.App(False)
OUT = Path(__file__).resolve().parents[1]
NAME = 'Patch_Anetnna_16_8_IPEX1'
audit = json.loads((OUT / 'verification/build_audit.json').read_text(encoding='utf-8'))
source = pcb.LoadBoard(audit['source_board'])
board = pcb.LoadBoard(str(OUT / (NAME + '.kicad_pcb')))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(audit['source_board']) == audit['source_board_sha256']
assert sha(audit['source_schematic']) == audit['source_schematic_sha256']
assert sha(OUT / 'datasheets/ECT_818000368_SPEC_E.pdf') == audit['datasheet_sha256']
assert sha(OUT / 'PLFM_RF.pretty/ECT_818000368_IPEX1_1.25mm.kicad_mod') == audit['footprint_sha256'] == sha(audit['footprint_source'])
xy = lambda v: (v.x, v.y)
def drawing_snapshot(b):
    rows = []
    for g in b.GetDrawings():
        if isinstance(g, pcb.PCB_SHAPE):
            rows.append((g.m_Uuid.AsString(), g.GetLayer(), g.GetShape(), xy(g.GetStart()), xy(g.GetEnd()), g.GetWidth(), g.IsSolidFill(), g.GetNetname()))
        else:
            rows.append((g.m_Uuid.AsString(), g.GetLayer(), g.GetText(), xy(g.GetPosition())))
    return sorted(rows)
assert drawing_snapshot(source) == drawing_snapshot(board)
patches = [g for g in board.GetDrawings() if g.GetLayer() == pcb.F_Cu]
assert len(patches) == 128
assert sorted(collections.Counter(p.GetNetname() for p in patches).values()) == [8] * 16
def zone_snapshot(b):
    result = []
    for z in b.Zones():
        chain = z.Outline().COutline(0)
        result.append((z.GetLayer(), z.GetNetname(), [xy(chain.CPoint(i)) for i in range(chain.PointCount())]))
    return sorted(result)
assert zone_snapshot(source) == zone_snapshot(board)
def via_snapshot(b):
    return {v.m_Uuid.AsString(): (xy(v.GetPosition()), v.GetNetname(), v.GetDrillValue(), v.GetWidth(pcb.F_Cu), v.TopLayer(), v.BottomLayer()) for v in b.GetTracks() if isinstance(v, pcb.PCB_VIA)}
old_vias, new_vias = via_snapshot(source), via_snapshot(board)
assert len(old_vias) == 95 and len(new_vias) == 127
assert all(new_vias[key] == value for key, value in old_vias.items())
added_vias = {key: value for key, value in new_vias.items() if key not in old_vias}
assert len(added_vias) == 32
assert all(v[1:] == ('GND', pcb.FromMM(0.4), pcb.FromMM(0.8), pcb.F_Cu, pcb.B_Cu) for v in added_vias.values())
def track_snapshot(b):
    return {t.m_Uuid.AsString(): (t.GetNetname(), t.GetLayer(), xy(t.GetStart()), xy(t.GetEnd()), t.GetWidth()) for t in b.GetTracks() if not isinstance(t, pcb.PCB_VIA)}
old_tracks, new_tracks = track_snapshot(source), track_snapshot(board)
assert set(old_tracks) <= set(new_tracks)
changed = [(value, new_tracks[key]) for key, value in old_tracks.items() if new_tracks[key] != value]
assert len(changed) == 16 and len(new_tracks) == 80
assert all(a[:2] == b[:2] and a[3:] == b[3:] and a[2][0] == b[2][0] and a[2][1] - b[2][1] == pcb.FromMM(3.0) for a, b in changed)
def holes(b):
    return sorted((f.GetReference(), p.GetAttribute(), xy(p.GetPosition()), xy(p.GetSize()), xy(p.GetDrillSize())) for f in b.GetFootprints() if not f.GetReference().startswith('J') for p in f.Pads())
assert holes(source) == holes(board)
assert board.GetCopperLayerCount() == source.GetCopperLayerCount() == 4
assert board.GetDesignSettings().GetBoardThickness() == source.GetDesignSettings().GetBoardThickness()
expected = {'GND': []}
fps = {f.GetReference(): f for f in board.GetFootprints() if f.GetReference().startswith('J')}
assert len(fps) == 16
for c in audit['changes']:
    f = fps[c['ref']]
    assert f.GetValue() == '818000368' and f.GetLayer() == pcb.F_Cu
    assert abs(abs(f.GetOrientationDegrees()) - 180) < 1e-9
    assert f.GetPath().AsString() == '/' + audit['root_uuid'] + '/' + audit['symbol_uuids'][c['ref']]
    assert [round(pcb.ToMM(v), 6) for v in xy(f.GetPosition())] == c['center_mm']
    assert set(p.GetNumber() for p in f.Pads()) == {'1', '2', '3'}
    for p in f.Pads():
        n = p.GetNumber()
        expected_size = (1.0, 1.05) if n == '1' else (1.05, 2.2)
        expected_offset = {'1': (0, -1.525), '2': (1.475, 0), '3': (-1.475, 0)}[n]
        assert xy(p.GetSize()) == tuple(pcb.FromMM(v) for v in expected_size)
        assert xy(p.GetPosition() - f.GetPosition()) == tuple(pcb.FromMM(v) for v in expected_offset)
        assert p.GetLayerSet().Contains(pcb.F_Cu) and p.GetLayerSet().Contains(pcb.F_Paste) and p.GetLayerSet().Contains(pcb.F_Mask)
        assert not p.GetLayerSet().Contains(pcb.B_Cu)
        assert p.GetNetname() == (c['signal_net'] if n == '1' else 'GND')
    expected[c['signal_net']] = [(c['ref'], '1')]
    expected['GND'].extend([(c['ref'], '2'), (c['ref'], '3')])
actual = collections.defaultdict(list)
for f in fps.values():
    for p in f.Pads():
        actual[p.GetNetname()].append((f.GetReference(), p.GetNumber()))
netlist = ET.parse(OUT / 'verification/schematic_netlist.xml')
schematic = {n.attrib['name']: sorted((i.attrib['ref'], i.attrib['pin']) for i in n.findall('node')) for n in netlist.findall('./nets/net')}
expected = {net: sorted(nodes) for net, nodes in expected.items()}
assert expected == schematic == {net: sorted(nodes) for net, nodes in actual.items()}
drc = json.loads((OUT / 'verification/drc.json').read_text(encoding='utf-8'))
erc = json.loads((OUT / 'verification/erc.json').read_text(encoding='utf-8'))
assert not drc['unconnected_items'] and not drc['schematic_parity']
assert not [v for v in drc['violations'] if v['severity'] == 'error']
erc_violations = [v for s in erc['sheets'] for v in s.get('violations', [])]
assert len(erc_violations) == 16 and all(v['type'] == 'isolated_pin_label' and v['severity'] == 'warning' for v in erc_violations)
uuid_counts = collections.Counter(re.findall(r'\(uuid\s+"([^"]+)"\)', (OUT / (NAME + '.kicad_pcb')).read_text(encoding='utf-8')))
assert all(count == 1 for count in uuid_counts.values()), 'Duplicated PCB object UUID'
result = {
    'source_files_unchanged': True, 'datasheet_and_footprint_hash_verified': True,
    'all_128_patch_copper_and_board_drawings_unchanged': True,
    'board_outline_mounting_holes_copper_layers_thickness_and_zone_outlines_unchanged': True,
    'all_95_original_vias_unchanged': True,
    'connectors_replaced': 16, 'connector_center_side_pad_geometry_and_orientation_verified': True,
    'ground_vias_added': 32, 'new_via_drill_diameter_mm': [0.4, 0.8],
    'original_feeds_trimmed_only_within_3mm_of_connector_centers': 16,
    'schematic_pcb_all_17_nets_48_pad_nodes_match': True,
    'drc_errors': 0, 'unconnected_items': 0, 'schematic_parity_issues': 0,
    'drc_warnings': dict(collections.Counter(v['type'] for v in drc['violations'])),
    'erc_errors': 0, 'erc_warnings': dict(collections.Counter(v['type'] for v in erc_violations)),
    'rf_validation': 'Not performed. Connector DC-6GHz specification does not qualify it at 10.5GHz.',
}
(OUT / 'verification/final_verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))

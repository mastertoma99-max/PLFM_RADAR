"""Run with the installed KiCad 10 Python. Read-only against the original design."""
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
ROOT = OUT.parents[1].parent
ORIGINAL = ROOT / '4_Schematics and Boards Layout/4_6_Schematics/Antennas/Patch/4x4/Phased_Array_Ant.brd'
NAME = 'Phased_Array_Ant_70x70_4L'
app = wx.App(False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(board):
    tracks = []
    for t in board.GetTracks():
        row = [type(t).__name__, t.GetNetname(), t.GetLayer(),
               t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y,
               t.GetWidth(pcb.F_Cu) if isinstance(t, pcb.PCB_VIA) else t.GetWidth()]
        if isinstance(t, pcb.PCB_VIA):
            row += [t.GetDrillValue()]
        tracks.append(row)
    pads = []
    fps = []
    for fp in board.GetFootprints():
        fps.append([fp.GetReference(), fp.GetValue(), fp.GetPosition().x, fp.GetPosition().y,
                    fp.GetOrientationDegrees(), fp.GetLayer()])
        for p in fp.Pads():
            pads.append([fp.GetReference(), p.GetNumber(), p.GetNetname(),
                         p.GetPosition().x, p.GetPosition().y,
                         p.GetSize().x, p.GetSize().y, p.GetShape(),
                         p.GetDrillSize().x, p.GetDrillSize().y,
                         p.GetOrientationDegrees()])
    return {'tracks_and_vias': sorted(tracks), 'pads': sorted(pads), 'footprints': sorted(fps)}


def import_board(path):
    # KiCad 10.0.0's CLI import crashes at SaveBoard when no initialized BOARD is
    # supplied. Importing into a new BOARD retains initialized default net settings.
    target = pcb.BOARD()
    return pcb.PCB_IO_MGR.Load(pcb.PCB_IO_MGR.EAGLE, str(path), target)


source = ORIGINAL.read_text(encoding='utf-8')
tree = ET.fromstring(source)
assert not tree.findall('.//*[@layer="3"]')
assert not tree.findall('.//*[@layer="14"]')
assert source.count('value="(1+2*3+14*15+16)"') == 1
backup = OUT / 'source/Phased_Array_Ant_original_6L.brd'
shutil.copy2(ORIGINAL, backup)
modified = source.replace('value="(1+2*3+14*15+16)"', 'value="(1+2*15+16)"')
for num in (3, 14):
    modified = re.sub(r'(<layer number="%d"[^>]*active=")yes("/>)' % num,
                      r'\g<1>no\2', modified)
modified = modified.replace('PCBWay_6L_100um-Track', 'Antenna_4L_100um_Stackup_TBD')
modified = modified.replace('for 6 layers standard', 'for 4 layers - material and thickness TBD')
four_eagle = OUT / f'source/{NAME}.brd'
four_eagle.write_text(modified, encoding='utf-8', newline='\n')
new_tree = ET.fromstring(modified)
for section in ('plain', 'libraries', 'elements', 'signals'):
    assert ET.tostring(tree.find(f'./drawing/board/{section}')) == ET.tostring(new_tree.find(f'./drawing/board/{section}'))

original = import_board(backup)
four = import_board(four_eagle)
print('Imported original and four-layer copy', flush=True)
assert original.GetCopperLayerCount() == 6 and four.GetCopperLayerCount() == 4
assert snapshot(original) == snapshot(four), 'Import changed physical geometry or nets'
print('Geometry identity verified', flush=True)

# Carry over documented EAGLE clearances that the KiCad import does not preserve.
# Keep copper-edge, polygon thickness, via tenting, and mask expansion explicit.
params = {e.attrib['name']: e.attrib['value'] for e in tree.findall('./drawing/board/designrules/param')}
report = {'source': str(ORIGINAL), 'source_sha256': sha(ORIGINAL),
          'modified_eagle_sha256': sha(four_eagle), 'tool': pcb.GetBuildVersion(),
          'original_copper_layers': 6, 'new_copper_layers': 4,
          'removed_eagle_layers': [3, 14], 'remaining_eagle_layers': [1, 2, 15, 16],
          'exact_eagle_geometry_and_net_sections_unchanged': True,
          'six_vs_four_import_geometry_and_net_identity': True,
          'material_and_finished_thickness': 'TBD by user/fabricator; not specified for fabrication',
          'inherited_eagle_mtIsolate_not_fabrication_spec': params['mtIsolate'],
          'inherited_eagle_mtCopper_not_fabrication_spec': params['mtCopper'],
          'counts': {'footprints_including_4_mounting_holes': len(list(four.GetFootprints())),
                     'pads_including_npth': len(list(four.GetPads())),
                     'tracks_and_vias': len(list(four.GetTracks())),
                     'zones': len(list(four.Zones()))}}

for board, name, folder in ((original, 'original_6L', OUT / 'verification'),
                            (four, NAME, OUT / 'source')):
    print('Processing', name, flush=True)
    ds = board.GetDesignSettings()
    ds.m_CopperEdgeClearance = pcb.FromMM(0.3)
    ds.m_MinClearance = pcb.FromMM(0.1)
    ds.m_TrackMinWidth = pcb.FromMM(0.1)
    ds.m_MinThroughDrill = pcb.FromMM(0.3)  # Preserve source minimum: 0.2 mm vias may be existing violations.
    ds.m_ViasMinSize = pcb.FromMM(0.4)
    ds.m_ViasMinAnnularWidth = pcb.FromMM(0.1)
    ds.m_SolderMaskExpansion = pcb.FromMM(0.0508)
    restored = 0
    for fp in board.GetFootprints():
        if not fp.GetReference().startswith('J'):
            continue
        ground_pads = [p for p in fp.Pads() if p.GetNumber() in ('2', '3', '4')]
        assert len(ground_pads) == 3 and all(p.GetNetname() == 'GND' for p in ground_pads)
        for item in fp.GraphicalItems():
            if item.GetLayer() == pcb.B_Cu:
                assert isinstance(item, pcb.PCB_SHAPE)
                # EAGLE package copper is physically joined to GND pads 2/3/4.
                # Import retains geometry but loses its implicit net assignment.
                item.SetNet(ground_pads[0].GetNet())
                restored += 1
    assert restored == 16
    for z in board.Zones():
        z.SetLocalClearance(pcb.FromMM(0.1))
        z.SetMinThickness(pcb.FromMM(0.2))
        z.SetThermalReliefGap(pcb.FromMM(0.2))
        z.SetThermalReliefSpokeWidth(pcb.FromMM(0.2))
    nc = ds.m_NetSettings.GetNetClassByName('Default')
    nc.SetClearance(pcb.FromMM(0.1))
    print('Rules configured', flush=True)
    board.BuildConnectivity()
    # Fill using the CLI after saving, so KiCad supplies a complete PROJECT context.
    board_file = folder / f'{name}.kicad_pcb'
    assert pcb.SaveBoard(str(board_file), board)
    # A sibling project file is necessary for CLI DRC/export to reload the rules.
    project = {'meta': {'filename': f'{name}.kicad_pro', 'version': 1},
               'board': {'design_settings': {'rules': {
                   'min_clearance': 0.1, 'min_track_width': 0.1,
                   'min_through_hole_diameter': 0.3, 'min_via_annular_width': 0.1,
                   'min_via_diameter': 0.4,
                   'min_copper_edge_clearance': 0.3,
                   'solder_mask_clearance': 0.0508}}},
               'net_settings': {'classes': [{'name': 'Default', 'clearance': 0.1,
                                            'track_width': 0.1, 'via_diameter': 0.6,
                                            'via_drill': 0.3}], 'version': 4}}
    (folder / f'{name}.kicad_pro').write_text(json.dumps(project, indent=2), encoding='utf-8')

# Compare the source wires and vias against the independently parsed imported items.
layer_map = {1: pcb.F_Cu, 2: pcb.In1_Cu, 15: pcb.In2_Cu, 16: pcb.B_Cu}
expected_tracks = []
expected_vias = []
for sig in tree.findall('./drawing/board/signals/signal'):
    for w in sig.findall('wire'):
        assert 'curve' not in w.attrib
        expected_tracks.append([sig.attrib['name'], layer_map[int(w.attrib['layer'])],
                                round(float(w.attrib['x1'])*1e6), round(-float(w.attrib['y1'])*1e6),
                                round(float(w.attrib['x2'])*1e6), round(-float(w.attrib['y2'])*1e6),
                                round(float(w.attrib['width'])*1e6)])
    for v in sig.findall('via'):
        expected_vias.append([sig.attrib['name'], round(float(v.attrib['x'])*1e6),
                              round(-float(v.attrib['y'])*1e6), round(float(v.attrib['drill'])*1e6)])
actual_tracks, actual_vias = [], []
for t in four.GetTracks():
    if isinstance(t, pcb.PCB_VIA):
        actual_vias.append([t.GetNetname(), t.GetPosition().x, t.GetPosition().y, t.GetDrillValue()])
    else:
        actual_tracks.append([t.GetNetname(), t.GetLayer(),t.GetStart().x,t.GetStart().y,
                              t.GetEnd().x,t.GetEnd().y,t.GetWidth()])
assert sorted(expected_tracks) == sorted(actual_tracks)
assert sorted(expected_vias) == sorted(actual_vias)
assert sorted(z.GetLayer() for z in four.Zones()) == [pcb.In1_Cu, pcb.In2_Cu]
report['eagle_vs_kicad_all_101_wires_exact'] = True
report['eagle_vs_kicad_all_28_vias_exact'] = True
report['zone_layers_verified'] = ['In1.Cu', 'In2.Cu']
report['restored_imported_connector_ground_polygon_nets'] = 16
report['drill_counts'] = {'PTH_0.2mm': 16, 'PTH_0.3mm': 12, 'NPTH_3.2mm': 4}
net_nodes = {'pads': [], 'vias': []}
for fp in four.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname():
            net_nodes['pads'].append({'ref': fp.GetReference(), 'pad': p.GetNumber(),
                'net': p.GetNetname(), 'x': p.GetPosition().x / 1e6, 'y': -p.GetPosition().y / 1e6,
                'layer': 'B_Cu' if p.GetLayerSet().Contains(pcb.B_Cu) else 'F_Cu'})
for via in four.GetTracks():
    if isinstance(via, pcb.PCB_VIA):
        net_nodes['vias'].append({'net': via.GetNetname(), 'x': via.GetPosition().x / 1e6,
            'y': -via.GetPosition().y / 1e6, 'drill': via.GetDrillValue() / 1e6})
(OUT / 'verification/physical_net_nodes.json').write_text(json.dumps(net_nodes, indent=2), encoding='utf8')
report['note'] = 'KiCad board thickness defaults to 1.6 mm for visualization only. It is not a fabrication instruction. Do not infer laminate from importer defaults.'
(OUT / 'verification/geometry_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)

"""Finish and audit the native KiCad 10 EAGLE import; run with KiCad Python."""
from pathlib import Path
import collections
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
import pcbnew as pcb
import wx

OUT = Path(__file__).resolve().parents[1]
SRC = OUT.parent
NAME = 'Patch_Anetnna_16_8'
BACKUP = OUT / 'verification/native_import'
BACKUP.mkdir(exist_ok=True)
for file in OUT.iterdir():
    if file.is_file() and (file.suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_sch', '.kicad_sym', '.kicad_dru') or file.name == 'sym-lib-table'):
        target = BACKUP / file.name
        if not target.exists():
            shutil.copy2(file, target)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def parse(text):
    stack = [[]]
    for token in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text):
        if token == '(':
            child = []
            stack[-1].append(child)
            stack.append(child)
        elif token == ')':
            stack.pop()
        else:
            stack[-1].append(json.loads(token) if token.startswith('"') else token)
    assert len(stack) == 1
    return stack[0][0]

def children(node, name):
    return [item for item in node if isinstance(item, list) and item and item[0] == name]

def child(node, name):
    return children(node, name)[0]

app = wx.App(False)
board = pcb.LoadBoard(str(BACKUP / (NAME + '.kicad_pcb')))
original = ET.parse(SRC / (NAME + '.brd')).find('./drawing/board')
source_elements = {e.attrib['name']: e for e in original.findall('elements/element')}
fps = {f.GetReference(): f for f in board.GetFootprints() if f.GetReference() in source_elements}
assert len(fps) == len(source_elements) == 16
anchor = source_elements['J17'].attrib
offset_x = fps['J17'].GetPosition().x - round(float(anchor['x']) * 1e6)
offset_y = fps['J17'].GetPosition().y + round(float(anchor['y']) * 1e6)
def xy(x, y):
    return (round(float(x) * 1e6) + offset_x, -round(float(y) * 1e6) + offset_y)
def pt(v):
    return (v.x, v.y)
layers = {1: pcb.F_Cu, 2: pcb.In1_Cu, 3: pcb.In2_Cu, 16: pcb.B_Cu, 20: pcb.Edge_Cuts, 29: pcb.F_Mask}

tracks = [t for t in board.GetTracks() if not isinstance(t, pcb.PCB_VIA)]
vias = [t for t in board.GetTracks() if isinstance(t, pcb.PCB_VIA)]
def track_key(t):
    return (t.GetLayer(), tuple(sorted((pt(t.GetStart()), pt(t.GetEnd())))), t.GetWidth())
expected_tracks = []
net_map = {}
for signal in original.findall('signals/signal'):
    for wire in signal.findall('wire'):
        a = wire.attrib
        assert 'curve' not in a
        key = (layers[int(a['layer'])], tuple(sorted((xy(a['x1'], a['y1']), xy(a['x2'], a['y2'])))), round(float(a['width']) * 1e6))
        expected_tracks.append(key)
        hits = [t for t in tracks if track_key(t) == key]
        assert len(hits) == 1
        net_map[signal.attrib['name']] = hits[0].GetNetname()
assert collections.Counter(expected_tracks) == collections.Counter(track_key(t) for t in tracks)
expected_vias = [(xy(v.attrib['x'], v.attrib['y']), round(float(v.attrib['drill']) * 1e6), s.attrib['name']) for s in original.findall('signals/signal') for v in s.findall('via')]
actual_vias = sorted((pt(v.GetPosition()), v.GetDrillValue(), v.GetNetname()) for v in vias)
assert len(expected_vias) == len(actual_vias)
via_max_rounding_nm = 0
for expected, actual in zip(sorted(expected_vias), actual_vias):
    assert expected[1:] == actual[1:]
    delta = max(abs(expected[0][i] - actual[0][i]) for i in (0, 1))
    assert delta <= 1  # EAGLE importer truncates coordinates to integer nanometres.
    via_max_rounding_nm = max(via_max_rounding_nm, delta)
for ref, fp in fps.items():
    assert pt(fp.GetPosition()) == xy(source_elements[ref].attrib['x'], source_elements[ref].attrib['y'])

def zone_vertices(z):
    outline = z.Outline()
    assert outline.OutlineCount() == 1 and outline.HoleCount(0) == 0
    chain = outline.COutline(0)
    return sorted(pt(chain.CPoint(i)) for i in range(chain.PointCount()))

rectangles = original.findall('plain/rectangle')
patch_zones = [z for z in board.Zones() if z.GetLayer() == pcb.F_Cu]
expected_rectangles = []
for r in rectangles:
    a = r.attrib
    assert a['layer'] == '1' and not a.get('rot')
    expected_rectangles.append(sorted(xy(x, y) for x in (a['x1'], a['x2']) for y in (a['y1'], a['y2'])))
assert sorted(expected_rectangles) == sorted(zone_vertices(z) for z in patch_zones)
assert len(rectangles) == len(patch_zones) == 128

# EAGLE plain copper rectangles are conductors. Native import turns them into
# unassigned zones, which would clear away from the feed tracks during filling.
# Restore only unambiguous overlaps with the existing vertical feed conductors.
for z in patch_zones:
    vertices = zone_vertices(z)
    xmin, xmax = min(p[0] for p in vertices), max(p[0] for p in vertices)
    ymin, ymax = min(p[1] for p in vertices), max(p[1] for p in vertices)
    hits = [t for t in tracks if t.GetLayer() == pcb.F_Cu and t.GetStart().x == t.GetEnd().x and xmin <= t.GetStart().x <= xmax and max(min(t.GetStart().y, t.GetEnd().y), ymin) <= min(max(t.GetStart().y, t.GetEnd().y), ymax)]
    assert hits and len(set(t.GetNetname() for t in hits)) == 1
    # Keep EAGLE's exact rectangular copper, including its square corners.
    # A filled KiCad zone rounds corners by half its minimum thickness.
    shape = pcb.PCB_SHAPE(board)
    shape.SetShape(pcb.SHAPE_T_RECT)
    shape.SetStart(pcb.VECTOR2I(xmin, ymin))
    shape.SetEnd(pcb.VECTOR2I(xmax, ymax))
    shape.SetLayer(pcb.F_Cu)
    shape.SetWidth(0)
    shape.SetFilled(True)
    shape.SetNet(hits[0].GetNet())
    board.Add(shape)
    board.Remove(z)

for ref, fp in fps.items():
    signal_pad = [p for p in fp.Pads() if p.GetNumber() == '1']
    assert len(signal_pad) == 1
    p = signal_pad[0]
    hits = []
    for t in tracks:
        assert t.GetStart().x == t.GetEnd().x
        dx = abs(p.GetPosition().x - t.GetStart().x)
        dy = max(min(t.GetStart().y, t.GetEnd().y) - p.GetPosition().y, p.GetPosition().y - max(t.GetStart().y, t.GetEnd().y), 0)
        if dx * dx + dy * dy <= ((p.GetSize().x + t.GetWidth()) / 2) ** 2:
            hits.append(t)
    assert hits and len(set(t.GetNetname() for t in hits)) == 1
    p.SetNet(hits[0].GetNet())

# Replace the spurious blank top-level sheet with the actual single EAGLE sheet.
sch = (BACKUP / (NAME + '_1.kicad_sch')).read_text(encoding='utf-8')
sch_tree = parse(sch)
root_uuid = child(sch_tree, 'uuid')[1]
project = json.loads((BACKUP / (NAME + '.kicad_pro')).read_text(encoding='utf-8'))
old_sheet_uuid = next(s['uuid'] for s in project['schematic']['top_level_sheets'] if s['filename'] == NAME + '_1.kicad_sch')
sch = sch.replace('/' + old_sheet_uuid, '/' + root_uuid)
(OUT / (NAME + '.kicad_sch')).write_text(sch, encoding='utf-8', newline='\n')
project['schematic']['top_level_sheets'] = [{'filename': NAME + '.kicad_sch', 'name': '', 'uuid': root_uuid}]
project['schematic']['page_layout_descr_file'] = ''
project['sheets'] = [[root_uuid, '']]
project['text_variables'] = {'IMPORT_NOTE': 'EAGLE 8x16 import; fabrication stackup unconfirmed'}
if (OUT / (NAME + '_1.kicad_sch')).exists():
    (OUT / (NAME + '_1.kicad_sch')).unlink()  # Native import copy preserved above.

# Bundle the existing connector footprint locally; no external library is needed.
libname = NAME
libdir = OUT / (libname + '.pretty')
libdir.mkdir(exist_ok=True)
prototype = pcb.FOOTPRINT(fps['J17'])
prototype.SetPosition(pcb.VECTOR2I(0, 0))
prototype.SetReference('REF**')
prototype.SetPath(pcb.KIID_PATH())
for pad in prototype.Pads():
    pad.SetNetCode(0)
prototype.SetFPID(pcb.LIB_ID(libname, '1420731211'))
pcb.PCB_IO_MGR.FindPlugin(pcb.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(libdir), prototype)
(OUT / 'fp-lib-table').write_text('(fp_lib_table\n  (version 7)\n  (lib (name "' + libname + '")(type "KiCad")(uri "${KIPRJMOD}/' + libname + '.pretty")(options "")(descr "Imported original EAGLE connector"))\n)\n', encoding='utf-8')
symbols = {}
for s in children(sch_tree, 'symbol'):
    props = {p[1]: p[2] for p in children(s, 'property')}
    if props.get('Reference') in fps:
        symbols[props['Reference']] = child(s, 'uuid')[1]
assert set(symbols) == set(fps)
for ref, fp in fps.items():
    fp.SetFPID(pcb.LIB_ID(libname, '1420731211'))
    fp.SetPath(pcb.KIID_PATH('/' + root_uuid + '/' + symbols[ref]))

# Preserve geometry while making the EAGLE DRC minima explicit in KiCad.
params = {p.attrib['name']: p.attrib['value'] for p in original.findall('designrules/param')}
def mm(value):
    return float(value[:-2]) if value.endswith('mm') else float(value[:-3]) * 0.0254
rules = project['board']['design_settings']['rules']
rules.update({'min_clearance': mm(params['mdWireWire']), 'min_track_width': mm(params['msWidth']), 'min_through_hole_diameter': mm(params['msDrill']), 'min_copper_edge_clearance': mm(params['mdCopperDimension'])})
(OUT / (NAME + '.kicad_pro')).write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding='utf-8')
board.BuildConnectivity()
assert pcb.SaveBoard(str(OUT / (NAME + '.kicad_pcb')), board)
saved = pcb.LoadBoard(str(OUT / (NAME + '.kicad_pcb')))
assert collections.Counter(track_key(t) for t in tracks) == collections.Counter(track_key(t) for t in saved.GetTracks() if not isinstance(t, pcb.PCB_VIA))
saved_patches = [g for g in saved.GetDrawings() if g.GetLayer() == pcb.F_Cu and isinstance(g, pcb.PCB_SHAPE)]
assert all(g.GetShape() == pcb.SHAPE_T_RECT and g.IsSolidFill() and g.GetWidth() == 0 for g in saved_patches)
assert sorted(expected_rectangles) == sorted(sorted((x, y) for x in (g.GetStart().x, g.GetEnd().x) for y in (g.GetStart().y, g.GetEnd().y)) for g in saved_patches)
outline = [g for g in saved.GetDrawings() if g.GetLayer() == pcb.Edge_Cuts]
assert len(outline) == 4
expected_edges = sorted(tuple(sorted((xy(w.attrib['x1'], w.attrib['y1']), xy(w.attrib['x2'], w.attrib['y2'])))) for w in original.findall('plain/wire') if w.attrib['layer'] == '20')
assert expected_edges == sorted(tuple(sorted((pt(g.GetStart()), pt(g.GetEnd())))) for g in outline)
holes = [p for p in saved.GetPads() if p.GetAttribute() == pcb.PAD_ATTRIB_NPTH]
assert sorted((pt(p.GetPosition()), p.GetDrillSize().x) for p in holes) == sorted((xy(h.attrib['x'], h.attrib['y']), round(float(h.attrib['drill']) * 1e6)) for h in original.findall('plain/hole'))
report = {
    'tool': pcb.GetBuildVersion(),
    'source_hashes': {s: sha(SRC / (NAME + s)) for s in ('.brd', '.sch')},
    'dimensions_mm': [245, 155], 'copper_layers': saved.GetCopperLayerCount(),
    'layer_mapping': {'1': 'F.Cu', '2': 'In1.Cu', '3': 'In2.Cu', '16': 'B.Cu'},
    'counts': {'patches': len(patch_zones), 'connectors': len(fps), 'tracks': len(tracks), 'vias': len(vias), 'npth_holes': len(holes), 'zones': len(list(saved.Zones()))},
    'exact_source_geometry_checks': {'tracks': True, 'via_drills': True, 'patch_rectangles': True, 'connector_positions': True, 'outline_centerlines': True, 'npth_centers_and_drills': True},
    'via_center_max_import_rounding_nm': via_max_rounding_nm,
    'coordinate_transform_nm': {'x_offset': offset_x, 'y_offset': offset_y, 'y_inverted': True},
    'native_import_merged_touching_wire_nets': net_map,
    'restored_patch_copper_rectangles_and_nets': 128, 'restored_feed_pad_nets': 16,
    'patch_representation_note': 'Native unassigned zones replaced by net-assigned filled copper rectangles matching EAGLE exactly; avoids corner rounding by KiCad zone minimum thickness.',
    'electrical_note': 'Original schematic contains connector ground wiring only; antenna feed and patch geometry exists in PCB. Do not run Update PCB from Schematic without reconciling RF nets.',
    'stackup_note': 'Four copper layers retained. Original In2.Cu is empty. The imported 1.6 mm board thickness is not a confirmed fabrication specification.',
    'source_mtIsolate': params['mtIsolate'], 'source_mtCopper': params['mtCopper'],
}
(OUT / 'verification/import_audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(report, indent=2, ensure_ascii=False))

"""Independent Gerber/Excellon readback, physical connectivity, and previews."""
from pathlib import Path
import collections
import dataclasses
import hashlib
import json
import sys
import warnings

OUT = Path(__file__).resolve().parent.parent
ROOT = OUT.parents[1].parent
sys.path.insert(0, str(ROOT / '5_Simulations/generated/antenna_4L_cam_tools'))
from gerbonara import GerberFile, ExcellonFile
from gerbonara.utils import MM
from shapely import make_valid
from shapely.geometry import Polygon, Point, GeometryCollection
from shapely.ops import unary_union
from PIL import Image, ImageDraw, ImageFont
import resvg_py

NAME = 'Phased_Array_Ant_70x70_4L'
CAM = OUT / 'cam'
specs = [('F_Cu', 'gtl', 'F_Cu', 'gtl'), ('In1_Cu', 'g1', 'In1_Cu', 'g1'),
         ('In2_Cu', 'g2', 'In4_Cu', 'g4'), ('B_Cu', 'gbl', 'B_Cu', 'gbl'),
         ('F_Mask', 'gts', 'F_Mask', 'gts'), ('B_Mask', 'gbs', 'B_Mask', 'gbs')]


def copper_geometry(g):
    geom = GeometryCollection()
    group, polarity = [], True
    for obj in g.objects:
        for primitive in obj.to_primitives(unit=MM):
            if primitive.polarity_dark != polarity:
                batch = unary_union(group)
                geom = geom.union(batch) if polarity else geom.difference(batch)
                group = []
                polarity = primitive.polarity_dark
            poly = primitive.to_arc_poly().approximate_arcs(max_error=0.0001)
            if len(poly.outline) >= 3:
                group.append(make_valid(Polygon(poly.outline)))
    batch = unary_union(group)
    return geom.union(batch) if polarity else geom.difference(batch)


def primitive_signature(g):
    return sorted(json.dumps(dataclasses.asdict(p), sort_keys=True)
                  for o in g.objects for p in o.to_primitives(unit=MM))


report = {'reader': 'gerbonara 1.6.3', 'units': 'mm', 'shape_comparison': {},
          'manufacturing_parameters': 'material, board thickness, copper weights, finish TBD'}
geoms, gerbers = {}, {}
for layer, ext, old_layer, old_ext in specs:
    new = GerberFile.open(CAM / f'{NAME}-{layer}.{ext}')
    old = GerberFile.open(OUT / f'verification/baseline_cam/original_6L-{old_layer}.{old_ext}')
    equal = primitive_signature(new) == primitive_signature(old)
    assert equal, f'Gerber primitives changed: {layer}'
    report['shape_comparison'][layer] = {'identical_primitives_to_six_layer_baseline': True,
                                         'gerber_objects': len(new.objects)}
    gerbers[layer] = new
    if layer.endswith('_Cu'):
        geoms[layer] = copper_geometry(new)
        print(layer, 'area', round(geoms[layer].area, 4), 'components',
              len(geoms[layer].geoms) if hasattr(geoms[layer], 'geoms') else 1, flush=True)

# Validate artwork connectivity independently of KiCad's footprint-graphic engine.
# 0.1 um arc approximation and 2 um component point tolerance; no trace geometry is edited.
components = {}
parent = {}
for layer, geom in geoms.items():
    parts = list(geom.geoms) if hasattr(geom, 'geoms') else [geom]
    components[layer] = [(i, p) for i, p in enumerate(parts) if p.area > 1e-9]
    for i, _ in components[layer]:
        parent[(layer, i)] = (layer, i)


def find(k):
    while parent[k] != k:
        parent[k] = parent[parent[k]]
        k = parent[k]
    return k


def union(a, b):
    parent[find(b)] = find(a)


def locate(layer, x, y):
    point = Point(x, y)
    hits = [(layer, i) for i, p in components[layer] if p.distance(point) < 0.002]
    assert len(hits) <= 1, (layer, x, y, hits)
    return hits[0] if hits else None


nodes = json.loads((OUT / 'verification/physical_net_nodes.json').read_text(encoding='utf8'))
terminals = []
for via in nodes['vias']:
    hits = [k for layer in geoms if (k := locate(layer, via['x'], via['y'])) is not None]
    assert len(hits) >= 2, via
    for k in hits[1:]:
        union(hits[0], k)
    terminals += [(via['net'], k) for k in hits]
for pad in nodes['pads']:
    hit = locate(pad['layer'], pad['x'], pad['y'])
    assert hit is not None, pad
    terminals.append((pad['net'], hit))
net_groups = collections.defaultdict(set)
component_nets = collections.defaultdict(set)
for net, k in terminals:
    net_groups[net].add(find(k))
    component_nets[find(k)].add(net)
assert all(len(v) == 1 for v in net_groups.values()), dict(net_groups)
assert all(len(v) == 1 for v in component_nets.values()), dict(component_nets)
assert len(net_groups) == 17
report['physical_connectivity'] = {'all_17_nets_connected': True, 'shorts_between_nets': 0,
                                   'tested_pads': len(nodes['pads']), 'tested_vias': len(nodes['vias']),
                                   'method': 'Gerber polygon union + plated-via graph; 0.1um arc approximation, 2um point tolerance'}
mask_audit = {}
for mask_name, copper_name in (('F_Mask', 'F_Cu'), ('B_Mask', 'B_Cu')):
    mask_geometry = copper_geometry(gerbers[mask_name])
    openings = list(mask_geometry.geoms) if hasattr(mask_geometry, 'geoms') else [mask_geometry]
    bridge_count = 0
    for opening in openings:
        exposed_nets = set()
        for index, copper in components[copper_name]:
            if opening.intersection(copper).area > 0.000001:
                exposed_nets.update(component_nets[find((copper_name,index))])
        if len(exposed_nets) > 1:
            bridge_count += 1
    assert bridge_count == 0, (mask_name, bridge_count)
    mask_audit[mask_name] = {'openings': len(openings), 'openings_exposing_multiple_nets': bridge_count}
report['physical_solder_mask_check'] = mask_audit

# Independent drill readback.
warnings.filterwarnings('ignore', category=SyntaxWarning)
drills = []
for kind in ('PTH', 'NPTH'):
    f = ExcellonFile.open(CAM / f'{NAME}-{kind}.drl')
    for o in f.objects:
        drills.append([kind, round(o.x, 6), round(o.y, 6), round(o.aperture.diameter, 6)])
counts = collections.Counter((row[0], row[3]) for row in drills)
assert counts == {('PTH', 0.2): 16, ('PTH', 0.3): 12, ('NPTH', 3.2): 4}, counts
expected_pth = sorted(['PTH', v['x'], v['y'], v['drill']] for v in nodes['vias'])
assert expected_pth == sorted(d for d in drills if d[0] == 'PTH')
assert sorted(d[1:3] for d in drills if d[0] == 'NPTH') == [[2,2], [2,68], [68,2], [68,68]]
report['drill_readback'] = {'total_holes': len(drills), 'PTH_0.2mm': 16, 'PTH_0.3mm': 12, 'NPTH_3.2mm': 4,
                          'all_positions_match_source': True}
outline = GerberFile.open(CAM / f'{NAME}-Edge_Cuts.gm1')
assert len(outline.objects) == 4
points = set((round(x,6), round(y,6)) for o in outline.objects for x,y in [(o.x1,o.y1),(o.x2,o.y2)])
assert points == {(0,0),(0,70),(70,0),(70,70)}
report['outline'] = {'closed': True, 'centerline_size_mm': [70,70]}

# Keep KiCad's unconfirmed defaults out of the fabrication job manifest.
job_file = CAM / f'{NAME}-job.gbrjob'
job = json.loads(job_file.read_text())
raw_job = OUT / 'verification/kicad_generated_job_before_removing_unconfirmed_defaults.json'
if not raw_job.exists():
    raw_job.write_text(json.dumps(job, indent=2), encoding='utf8')
job['GeneralSpecs'].pop('BoardThickness', None)
job['GeneralSpecs'].pop('Finish', None)
job['GeneralSpecs']['Size'] = {'X': 70.0, 'Y': 70.0}
job.pop('MaterialStackup', None)
job.pop('DesignRules', None)
job_file.write_text(json.dumps(job, indent=2), encoding='utf8')
report['job_manifest'] = 'Removed unconfirmed default material, thickness, finish and design-rule claims; outline size is centerline size.'

# DRC comparison is retained rather than suppressing inherited/conversion reports.
for suffix in ('4L', '6L'):
    drc = json.loads((OUT / f'verification/drc_{suffix}.json').read_text(encoding='utf8'))
    report[f'drc_{suffix}'] = {'violations_by_type': dict(collections.Counter(v['type'] for v in drc['violations'])),
                              'unconnected_reports': len(drc['unconnected_items'])}
assert report['drc_4L'] == report['drc_6L']
report['drc_interpretation'] = ('Identical reports before/after layer removal: 16 source 0.2mm drill holes below inherited 0.3mm rule; '
                              '60 mask-graphic reports and 24 connectivity reports from imported connector graphics. '
                              'Physical Gerber graph independently verifies all 17 nets connected with no net-to-net shorts. '
                              'Not a claim of clean native EAGLE DRC or RF performance validation.')

# Render actual Gerber files, not design screenshots.
panels = []
font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 25)
small = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 18)
for number, layer in enumerate(('F_Cu', 'In1_Cu', 'In2_Cu', 'B_Cu'), 1):
    svg = str(gerbers[layer].to_svg(force_bounds=((-2,-2),(72,72)), fg='#f4c66c', bg='#0b1722'))
    svg_path = OUT / f'preview/L{number}_{layer}.svg'
    svg_path.write_text(svg, encoding='utf8')
    png = resvg_py.svg_to_bytes(svg_string=svg, width=760, height=760, dpi=96, background='#0b1722')
    png_path = svg_path.with_suffix('.png')
    png_path.write_bytes(png)
    pic = Image.open(png_path).convert('RGB')
    panel = Image.new('RGB', (800,840), '#0b1722')
    ImageDraw.Draw(panel).text((24,15), f'L{number}  {layer.replace("_", ".")}'+('  /  GND' if layer.startswith('In') else ''), font=font, fill='#ffffff')
    panel.paste(pic, (20,65))
    panels.append(panel)
montage = Image.new('RGB',(1600,1790),'#0b1722')
d = ImageDraw.Draw(montage)
d.text((24,20),'70 x 70 mm antenna PCB | 4-layer Gerber artwork',font=font,fill='white')
d.text((24,58),'Top-view coordinates on every layer; drill holes are supplied separately.',font=small,fill='#c6d2dd')
for i,panel in enumerate(panels):
    montage.paste(panel,((i%2)*800,110+(i//2)*840))
montage.save(OUT / 'preview/four_layer_gerber_preview.png')
(OUT / 'verification/gerber_readback_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

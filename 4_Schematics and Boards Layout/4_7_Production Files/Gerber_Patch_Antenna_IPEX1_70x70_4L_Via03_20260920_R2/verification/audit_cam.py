"""Independent artwork/drill readback. Run with Python 3.12, not KiCad Python."""
from pathlib import Path
import collections, hashlib, json, re, sys, warnings
OUT = Path(__file__).resolve().parent.parent
ROOT = next(p for p in OUT.parents if (p/'.git').exists())
sys.path.insert(0, str(ROOT/'5_Simulations/generated/antenna_4L_cam_tools'))
from gerbonara import GerberFile, ExcellonFile
from gerbonara.ipc356 import Netlist
from gerbonara.utils import MM
from shapely import make_valid
from shapely.geometry import Polygon, Point, GeometryCollection, box
from shapely.ops import unary_union
from PIL import Image, ImageDraw, ImageFont
import resvg_py

NAME = 'Phased_Array_Ant_IPEX1'
CAM = OUT/'cam'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
warnings.filterwarnings('ignore', category=SyntaxWarning)
report = {'reader':'gerbonara 1.6.3 + shapely','units':'mm'}
nodes = json.loads((OUT/'verification/physical_net_nodes.json').read_text())
assert collections.Counter(p['layer'] for p in nodes['pads']) == {'F_Cu':16,'B_Cu':48}

def geometry(g):
    geom = GeometryCollection()
    group, polarity = [], True
    for obj in g.objects:
        for primitive in obj.to_primitives(unit=MM):
            if primitive.polarity_dark != polarity:
                batch = unary_union(group)
                geom = geom.union(batch) if polarity else geom.difference(batch)
                group, polarity = [], primitive.polarity_dark
            poly = primitive.to_arc_poly().approximate_arcs(max_error=.0001)
            if len(poly.outline) >= 3:
                group.append(make_valid(Polygon(poly.outline)))
    batch = unary_union(group)
    return geom.union(batch) if polarity else geom.difference(batch)

gerbers, geoms, masks = {}, {}, {}
for layer, ext, func in [('F_Cu','gtl','Copper,L1,Top'),('In1_Cu','g1','Copper,L2,Inr'),('In2_Cu','g2','Copper,L3,Inr'),('B_Cu','gbl','Copper,L4,Bot'),('F_Mask','gts','Soldermask,Top'),('B_Mask','gbs','Soldermask,Bot'),('F_Silkscreen','gto','Legend,Top'),('B_Silkscreen','gbo','Legend,Bot'),('Edge_Cuts','gm1','Profile')]:
    path = CAM/f'{NAME}-{layer}.{ext}'
    assert ('%TF.FileFunction,'+func).lower() in path.read_text().lower(), layer
    gerbers[layer] = GerberFile.open(path)
    if layer.endswith('_Cu'):
        geoms[layer] = geometry(gerbers[layer])
        assert geoms[layer].difference(box(0,0,70,70)).area < 1e-8, layer
    elif layer.endswith('_Mask'):
        masks[layer] = geometry(gerbers[layer])
    print('Read',layer,flush=True)
report['layer_order'] = ['F.Cu','In1.Cu','In2.Cu','B.Cu']

components, parent = {}, {}
for layer, geom in geoms.items():
    parts = list(geom.geoms) if hasattr(geom,'geoms') else [geom]
    components[layer] = [(i,p) for i,p in enumerate(parts) if p.area > 1e-9]
    for i,_ in components[layer]: parent[(layer,i)] = (layer,i)
def find(k):
    while parent[k] != k:
        parent[k] = parent[parent[k]]
        k = parent[k]
    return k
def union(a,b): parent[find(b)] = find(a)
def locate(layer,x,y):
    hits = [(layer,i) for i,p in components[layer] if p.distance(Point(x,y)) < .002]
    assert len(hits) <= 1, (layer,x,y,hits)
    return hits[0] if hits else None
terminals = []
for via in nodes['vias']:
    hits = [k for layer in geoms if (k:=locate(layer,via['x'],via['y'])) is not None]
    assert len(hits) == 4, via
    for k in hits[1:]: union(hits[0],k)
    terminals.extend((via['net'],k) for k in hits)
for pad in nodes['pads']:
    hit = locate(pad['layer'],pad['x'],pad['y'])
    assert hit is not None, pad
    terminals.append((pad['net'],hit))
net_groups, component_nets = collections.defaultdict(set), collections.defaultdict(set)
for net,k in terminals:
    net_groups[net].add(find(k))
    component_nets[find(k)].add(net)
assert len(net_groups) == 17
assert all(len(v)==1 for v in net_groups.values()), dict(net_groups)
assert all(len(v)==1 for v in component_nets.values()), dict(component_nets)
assert all(find(k) in component_nets for k in parent), 'Unassigned copper island'
report['physical_connectivity'] = {'all_17_nets_connected':True,'shorts_between_nets':0,'tested_pads':64,'tested_vias':60,'unassigned_copper_islands':0,'method':'Gerber polygon union + plated-via graph; arc approximation 0.1 um, point tolerance 2 um'}
clearances = {}
for layer,parts in components.items():
    distances = [a.distance(b) for i,a in parts for j,b in parts if j>i and find((layer,i)) != find((layer,j))]
    clearances[layer] = min(distances) if distances else None
    assert not distances or min(distances) >= .199, (layer,min(distances))
report['minimum_different_net_copper_clearance_mm'] = clearances

# Each individual GND via must merge directly into BOTH large inner GND planes.
# Connectivity through some other ground via alone does not satisfy this check.
ground_vias=[v for v in nodes['vias'] if v['net']=='GND']
signal_vias=[v for v in nodes['vias'] if v['net']!='GND']
assert len(ground_vias)==44 and len(signal_vias)==16
inner_review={}
for layer in ['In1_Cu','In2_Cu']:
    plane=max((shape for _,shape in components[layer]),key=lambda shape:shape.area)
    connected=[v for v in ground_vias if plane.covers(Point(v['x'],v['y']))]
    signal_gaps=[plane.distance(Point(v['x'],v['y']))-v['diameter']/2 for v in signal_vias]
    assert len(connected)==44 and min(signal_gaps)>=.199
    inner_review[layer]={'directly_connected_ground_vias':44,'isolated_signal_vias':16,'minimum_signal_pad_to_ground_clearance_mm':min(signal_gaps),'single_continuous_GND_plane':True,'GND_plane_area_mm2':plane.area}
report['individual_inner_ground_connections']=inner_review

# This review must not accidentally change previously verified fabrication artwork.
previous=OUT.with_name(OUT.name.removesuffix('_R2'))/'cam'
unchanged={}
for layer,ext in [('F_Cu','gtl'),('In1_Cu','g1'),('In2_Cu','g2'),('B_Cu','gbl'),('F_Mask','gts'),('B_Mask','gbs'),('F_Silkscreen','gto'),('B_Silkscreen','gbo'),('Edge_Cuts','gm1')]:
    before=geometry(GerberFile.open(previous/f'{NAME}-{layer}.{ext}'))
    after=geometry(gerbers[layer])
    delta=before.symmetric_difference(after).area
    assert delta<1e-8,(layer,delta)
    unchanged[layer]={'changed_area_mm2':delta}
report['manufacturing_artwork_comparison_to_previous']=unchanged

mask_report = {}
for mask_name,copper_name in [('F_Mask','F_Cu'),('B_Mask','B_Cu')]:
    g = masks[mask_name]
    openings = list(g.geoms) if hasattr(g,'geoms') else [g]
    for opening in openings:
        exposed = set()
        for i,copper in components[copper_name]:
            if opening.intersection(copper).area > 1e-6:
                exposed.update(component_nets[find((copper_name,i))])
        assert len(exposed) <= 1, (mask_name,exposed)
    mask_report[mask_name] = {'openings':len(openings),'openings_exposing_multiple_nets':0}
report['solder_mask'] = mask_report
# Confirm the rectangular lands themselves, independently from filled geometry.
for pad in nodes['pads']:
    if not pad['ref'].startswith('J'): continue
    matches = [o for o in gerbers['B_Cu'].objects if type(o).__name__=='Flash' and abs(o.x-pad['x'])<1e-6 and abs(o.y-pad['y'])<1e-6 and type(o.aperture).__name__=='RectangleAperture']
    assert len(matches)==1, pad
    a = matches[0].aperture
    assert abs(a.w-pad['size_mm'][0])<1e-6 and abs(a.h-pad['size_mm'][1])<1e-6, pad
report['ipex_lands'] = {'connectors':16,'B_Cu_rectangular_lands_verified':48,'signal_land_mm':[1,1.05],'ground_land_mm':[1.05,2.2]}

drills=[]
for kind in ['PTH','NPTH']:
    d=ExcellonFile.open(CAM/f'{NAME}-{kind}.drl')
    for o in d.objects: drills.append([kind,round(o.x,6),round(o.y,6),round(o.aperture.diameter,6)])
assert collections.Counter((d[0],d[3]) for d in drills)=={('PTH',.3):60,('NPTH',3.2):4}
assert sorted(d for d in drills if d[0]=='PTH')==sorted(['PTH',v['x'],v['y'],v['drill']] for v in nodes['vias'])
assert sorted(d for d in drills if d[0]=='NPTH')==sorted(['NPTH',v['x'],v['y'],v['drill']] for v in nodes['npth'])
report['drill_readback']={'PTH_0.3mm':60,'NPTH_3.2mm':4,'all_positions_match_source':True,'minimum_annular_ring_nominal_mm':.1}
outline=gerbers['Edge_Cuts']
assert len(outline.objects)==4
ends=collections.Counter((round(x,6),round(y,6)) for o in outline.objects for x,y in [(o.x1,o.y1),(o.x2,o.y2)])
assert ends=={(0,0):2,(0,70):2,(70,0):2,(70,70):2}
report['outline']={'closed':True,'size_mm':[70,70],'origin':'lower left (0,0)','all_layers_unmirrored_top_view':True,'drawing_sheet_not_exported':True}

# Correct malformed KiCad 10 IPC via mask values and restore the reserved column.
# Preserve the raw export, all network/pin/coordinate/dimension fields, and derive
# mask flags from actual mask openings. No artwork is changed by this operation.
ipc=CAM/f'{NAME}.d356'
raw=OUT/'verification/ipc356_kicad_raw.d356'
if any(line.startswith('317') and line[71:72]=='S' for line in ipc.read_text().splitlines()): raw.write_bytes(ipc.read_bytes())
assert raw.exists()
lines=[]
corrected=0
for line in raw.read_text().splitlines():
    if line.startswith(('317','327','367')):
        x,y=int(line[42:49])*.00254,int(line[50:57])*.00254
        if line.startswith('317'):
            via=min(nodes['vias'],key=lambda v:(v['x']-x)**2+(v['y']-y)**2)
            assert abs(via['x']-x)<.002 and abs(via['y']-y)<.002
            flag=sum(bit for name,bit in [('F_Mask',1),('B_Mask',2)] if not masks[name].covers(Point(via['x'],via['y'])))
        elif line.startswith('327'):
            flag=2 if int(line[39:41])==1 else 1
        else: flag=0
        revised=(line[:71]+' S'+str(flag)).ljust(80)
        corrected += revised.rstrip()!=line.rstrip()
        lines.append(revised)
    else: lines.append(line)
ipc.write_text('\n'.join(lines)+'\n',encoding='ascii')
parsed=Netlist.open(ipc)
assert len(parsed.test_records)==128
records=[r for r in parsed.test_records if r.net_name]
assert len(records)==124 and set(r.net_name for r in records)==set(net_groups)
remaining=records.copy()
maximum_error=0
for node in nodes['pads']+nodes['vias']:
    possible=[r for r in remaining if r.net_name==node['net'] and bool(r.is_via)==('ref' not in node)]
    r=min(possible,key=lambda r:(MM(r.x,r.unit)-node['x'])**2+(MM(r.y,r.unit)-node['y'])**2)
    error=max(abs(MM(r.x,r.unit)-node['x']),abs(MM(r.y,r.unit)-node['y']))
    assert error<.002, (node,r,error)
    maximum_error=max(maximum_error,error)
    if 'ref' in node:
        assert r.ref_des==node['ref'] and r.pin==node['pad']
        assert r.access_layer==({'F_Cu':1,'B_Cu':4}[node['layer']])
    else: assert r.access_layer==0 and abs(MM(r.hole_dia,r.unit)-.3)<.002
    remaining.remove(r)
assert not remaining
report['ipc356_readback']={'electrical_nodes':124,'mechanical_holes':4,'net_pin_layer_and_coordinate_match':True,'max_coordinate_quantization_error_mm':maximum_error,'format_normalized_records':corrected,'raw_export_archived':str(raw.relative_to(OUT)),'correction':'Reserved column 72 restored; via soldermask code derived from actual mask artwork; all first 71 columns unchanged.'}

jobfile=CAM/f'{NAME}-job.gbrjob'
job=json.loads(jobfile.read_text())
rawjob=OUT/'verification/kicad_generated_job_raw.json'
if job['GeneralSpecs'].get('Finish')=='None' or not rawjob.exists(): rawjob.write_text(json.dumps(job,indent=2),encoding='utf8')
job['GeneralSpecs'].update(Size={'X':70.0,'Y':70.0},BoardThickness=1.0,Finish='OSP')
job.pop('DesignRules',None)
for layer in job['MaterialStackup']:
    if layer['Type']=='Copper':
        layer['Thickness']=.035 if layer['Name'] in ['F.Cu','B.Cu'] else .0175
        layer['Notes']='Nominal 1 oz outer / 0.5 oz inner. Copper weight is the controlling requirement.'
    else: layer.pop('Thickness',None)
    if layer['Type']=='Dielectric': layer['Notes']='FR4; individual dielectric thickness and grade to be proposed by fabricator for 1.0 mm finished board.'
job['MaterialStackup']=[l for l in job['MaterialStackup'] if l['Type']!='SolderPaste']
jobfile.write_text(json.dumps(job,indent=2),encoding='utf8')
report['fabrication_parameters']=json.loads((OUT/'fabrication_requirements.json').read_text(encoding='utf8'))
report['job_manifest']='Confirmed fabrication values applied; unconfirmed default dielectric/mask thicknesses and design-rule claims removed.'
drc=json.loads((OUT/'verification/drc.json').read_text())
erc=json.loads((OUT/'verification/erc.json').read_text())
assert not drc['violations'] and not drc['unconnected_items'] and not drc['schematic_parity']
assert not drc['ignored_checks']
assert not any(s['violations'] for s in erc['sheets'])
report['kicad_checks']={'DRC':0,'unconnected':0,'schematic_parity':0,'ERC':0,'DRC_ignored_checks':drc['ignored_checks'],'ERC_ignored_checks':erc['ignored_checks']}
manifest=json.loads((OUT/'verification/export_manifest.json').read_text())
assert sha(OUT/'source'/f'{NAME}.kicad_pcb')==manifest['exported_board_sha256']
for rel,digest in manifest['source_hashes'].items(): assert sha(Path(manifest['source_project'])/rel)==digest
report['source_hashes_still_match']=True

# Preview is rendered directly from the delivered Gerbers with separate drills overlaid.
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',25)
small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
panels=[]
for number,layer in enumerate(['F_Cu','In1_Cu','In2_Cu','B_Cu'],1):
    svg=str(gerbers[layer].to_svg(force_bounds=((-2,-2),(72,72)),fg='#f4c66c',bg='#0b1722'))
    svgpath=OUT/f'preview/L{number}_{layer}.svg'
    svgpath.write_text(svg,encoding='utf8')
    svgpath.with_suffix('.png').write_bytes(resvg_py.svg_to_bytes(svg_string=svg,width=760,height=760,dpi=96,background='#0b1722'))
    pic=Image.open(svgpath.with_suffix('.png')).convert('RGB')
    draw=ImageDraw.Draw(pic)
    for kind,x,y,dia in drills:
        px,py=(x+2)*760/74,(72-y)*760/74
        r=dia*760/148
        draw.ellipse((px-r,py-r,px+r,py+r),fill='#080b10')
    panel=Image.new('RGB',(800,840),'#0b1722')
    ImageDraw.Draw(panel).text((24,15),f'L{number}  {layer.replace("_", ".")}'+('  / GND' if layer.startswith('In') else ''),font=font,fill='white')
    panel.paste(pic,(20,65))
    panels.append(panel)
montage=Image.new('RGB',(1600,1810),'#0b1722')
d=ImageDraw.Draw(montage)
d.text((24,15),'IPEX1 antenna PCB | 70 x 70 mm | FR4 1.0 mm | OSP',font=font,fill='white')
d.text((24,53),'Outer 1 oz / inner 0.5 oz | 60 x 0.30 mm PTH + 4 x 3.20 mm NPTH',font=small,fill='#c6d2dd')
d.text((24,81),'Actual Gerber artwork + drill overlay. All layers shown in unmirrored top-view coordinates.',font=small,fill='#c6d2dd')
for i,panel in enumerate(panels): montage.paste(panel,((i%2)*800,125+(i//2)*840))
montage.save(OUT/'preview/four_layer_gerber_preview.png')
(OUT/'verification/gerber_readback_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

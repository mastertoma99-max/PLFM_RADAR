"""Read back actual CAM artwork, verify connectivity and render copper previews."""
from pathlib import Path
import collections, hashlib, json, re, shutil, sys, warnings
OUT = Path(__file__).resolve().parents[1]
ROOT = next(p for p in OUT.parents if (p/'.git').exists())
sys.path.insert(0,str(ROOT/'5_Simulations/generated/antenna_4L_cam_tools'))
from gerbonara import GerberFile, ExcellonFile
from gerbonara.ipc356 import Netlist
from gerbonara.utils import MM
from shapely import make_valid
from shapely.geometry import Polygon, Point, GeometryCollection, box
from shapely.ops import unary_union
from PIL import Image, ImageDraw, ImageFont
import resvg_py

NAME = 'Patch_Anetnna_16_8_IPEX1'
CAM = OUT/'cam'
sha = lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
warnings.filterwarnings('ignore',category=SyntaxWarning)
nodes = json.loads((OUT/'verification/physical_net_nodes.json').read_text())
report = {'reader':'Gerbonara 1.6.3 + Shapely 2.1.2','units':'mm'}

def geometry(g):
    geom = GeometryCollection()
    group,polarity=[],True
    for obj in g.objects:
        for primitive in obj.to_primitives(unit=MM):
            if primitive.polarity_dark!=polarity:
                batch=unary_union(group)
                geom=geom.union(batch) if polarity else geom.difference(batch)
                group,polarity=[],primitive.polarity_dark
            poly=primitive.to_arc_poly().approximate_arcs(max_error=.0001)
            if len(poly.outline)>=3: group.append(make_valid(Polygon(poly.outline)))
    batch=unary_union(group)
    return geom.union(batch) if polarity else geom.difference(batch)

specs=[('F_Cu','gtl','Copper,L1,Top'),('In1_Cu','g1','Copper,L2,Inr'),('In2_Cu','g2','Copper,L3,Inr'),('B_Cu','gbl','Copper,L4,Bot'),('F_Mask','gts','Soldermask,Top'),('B_Mask','gbs','Soldermask,Bot'),('F_Silkscreen','gto','Legend,Top'),('B_Silkscreen','gbo','Legend,Bot'),('Edge_Cuts','gm1','Profile')]
gerbers,geoms,masks={}, {}, {}
for layer,ext,func in specs:
    f=CAM/f'{NAME}-{layer}.{ext}'
    assert ('%TF.FileFunction,'+func).lower() in f.read_text().lower()
    gerbers[layer]=GerberFile.open(f)
    if layer.endswith('_Cu'):
        geoms[layer]=geometry(gerbers[layer])
        assert geoms[layer].difference(box(0,0,245,155)).area<1e-7
    elif layer.endswith('_Mask'): masks[layer]=geometry(gerbers[layer])
    print('Read',layer,len(gerbers[layer].objects),'objects',flush=True)
report['layer_order']=['F.Cu','In1.Cu','In2.Cu','B.Cu']

components,parent={},{}
for layer,geom in geoms.items():
    parts=list(geom.geoms) if hasattr(geom,'geoms') else [geom]
    components[layer]=[(i,g) for i,g in enumerate(parts) if g.area>1e-9]
    for i,_ in components[layer]:parent[(layer,i)]=(layer,i)
def find(k):
    while parent[k]!=k:
        parent[k]=parent[parent[k]]
        k=parent[k]
    return k
def union(a,b):parent[find(b)]=find(a)
def locate(layer,x,y):
    hits=[(layer,i) for i,g in components[layer] if g.distance(Point(x,y))<.002]
    assert len(hits)<=1,(layer,x,y,hits)
    return hits[0] if hits else None
terminals=[]
for v in nodes['vias']:
    hits=[k for layer in geoms if (k:=locate(layer,v['x'],v['y'])) is not None]
    assert len(hits)>=2,v
    for k in hits[1:]:union(hits[0],k)
    terminals.extend((v['net'],k) for k in hits)
for q in nodes['pads']:
    k=locate(q['layer'],q['x'],q['y'])
    assert k is not None,q
    terminals.append((q['net'],k))
for q in nodes['patches']:
    x1,y1,x2,y2=q['bounds']
    assert abs(x2-x1-7.86)<1e-6 and abs(y2-y1-7.36)<1e-6
    target=box(*q['bounds'])
    assert target.difference(geoms['F_Cu']).area<1e-7,q
    k=locate('F_Cu',(x1+x2)/2,(y1+y2)/2)
    assert k is not None,q
    terminals.append((q['net'],k))
net_groups,component_nets=collections.defaultdict(set),collections.defaultdict(set)
for net,k in terminals:
    net_groups[net].add(find(k)); component_nets[find(k)].add(net)
assert len(net_groups)==17
assert all(len(v)==1 for v in net_groups.values()),dict(net_groups)
assert all(len(v)==1 for v in component_nets.values()),dict(component_nets)
assert all(find(k) in component_nets for k in parent),'Unassigned copper island'
report['physical_connectivity']={'all_17_nets_connected':True,'shorts_between_nets':0,'tested_connector_pads':48,'tested_via_objects':127,'tested_antenna_patches':128,'unassigned_copper_islands':0,'method':'Gerber polygon union plus plated-via graph, 0.1 um arc approximation and 2 um point tolerance'}
report['minimum_different_net_copper_clearance_mm']={}
for layer,parts in components.items():
    ds=[a.distance(b) for i,a in parts for j,b in parts if j>i and find((layer,i))!=find((layer,j))]
    report['minimum_different_net_copper_clearance_mm'][layer]=min(ds) if ds else None
    assert not ds or min(ds)>=.199,(layer,min(ds))
plane=max((g for _,g in components['In1_Cu']),key=lambda g:g.area)
assert all(plane.covers(Point(v['x'],v['y'])) for v in nodes['vias'])
report['ground_plane']={'In1_Cu_continuous_plane_area_mm2':plane.area,'ground_via_objects_directly_touching_In1':127,'In2_and_B_Cu_have_no_plane':True,'layer_copper_areas_mm2':{k:g.area for k,g in geoms.items()}}

# Verify all 48 connector rectangles, including physical dimensions.
for q in nodes['pads']:
    hits=[o for o in gerbers['F_Cu'].objects if type(o).__name__=='Flash' and abs(o.x-q['x'])<1e-6 and abs(o.y-q['y'])<1e-6 and type(o.aperture).__name__=='RectangleAperture']
    assert len(hits)==1,q
    a=hits[0].aperture
    assert abs(a.w-q['size_mm'][0])<1e-6 and abs(a.h-q['size_mm'][1])<1e-6
report['ipex_lands']={'mounting_side':'top','connectors':16,'rectangular_pads_verified':48}

# Source intentionally has a full top-mask opening; record it without treating it as a short.
mask_report={}
for m,c in [('F_Mask','F_Cu'),('B_Mask','B_Cu')]:
    mask=masks[m]
    openings=list(mask.geoms) if hasattr(mask,'geoms') else [mask]
    multi=0
    for opening in openings:
        exposed=set()
        for i,copper in components[c]:
            if opening.intersection(copper).area>1e-6:exposed.update(component_nets[find((c,i))])
        multi+=len(exposed)>1
    mask_report[m]={'opening_count':len([g for g in openings if g.area>1e-9]),'opening_area_mm2':mask.area,'openings_exposing_multiple_nets':multi}
assert box(0,0,245,155).difference(masks['F_Mask']).area<.1
report['solder_mask']={**mask_report,'top_nearly_entire_board_open_inherited_from_source':True,'comment':'Full-board mask opening with small rounded corners, spanning different nets by original design; no solder-mask dams between top nets. Copper connectivity was checked separately.'}
report['silkscreen']={}
for side in ['F','B']:
    silk=geometry(gerbers[side+'_Silkscreen'])
    assert silk.intersection(masks[side+'_Mask']).area<1e-7
    report['silkscreen'][side]={'plotted_primitives':len(gerbers[side+'_Silkscreen'].objects),'effective_printed_area_mm2':silk.area,'overlap_with_mask_openings_mm2':0}

# Remove only exact duplicate drill commands, leaving coordinates and tool tables unchanged.
pth=CAM/f'{NAME}-PTH.drl'
rawpth=OUT/'verification/PTH_KiCad_raw_127_hits.drl'
if not rawpth.exists():shutil.copy2(pth,rawpth)
tool=None; seen=set(); lines=[]; duplicates=[]
for line in rawpth.read_text().splitlines():
    if re.fullmatch(r'T\d+',line):tool=line
    if line.startswith('X'):
        assert re.fullmatch(r'X[-+\d.]+Y[-+\d.]+',line),line
        key=(tool,line)
        if key in seen:duplicates.append({'tool':tool,'command':line});continue
        seen.add(key)
    lines.append(line)
assert len(duplicates)==3
pth.write_text('\n'.join(lines)+'\n',encoding='ascii')
drills=[]
for kind in ['PTH','NPTH']:
    f=ExcellonFile.open(CAM/f'{NAME}-{kind}.drl')
    for o in f.objects:drills.append([kind,round(o.x,6),round(o.y,6),round(o.aperture.diameter,6)])
assert collections.Counter((d[0],d[3]) for d in drills)=={('PTH',.4):32,('PTH',.6):92,('NPTH',3.2):4}
expected={('PTH',v['x'],v['y'],v['drill']) for v in nodes['vias']}|{('NPTH',v['x'],v['y'],v['drill']) for v in nodes['npth']}
remaining=set(map(tuple,drills));drill_error=0
assert len(expected)==len(remaining)==len(drills)
for kind,x,y,dia in expected:
    matches=[d for d in remaining if d[0]==kind and d[3]==dia]
    d=min(matches,key=lambda d:(d[1]-x)**2+(d[2]-y)**2)
    error=max(abs(d[1]-x),abs(d[2]-y))
    assert error<=.000501,(kind,x,y,dia,d)
    drill_error=max(drill_error,error);remaining.remove(d)
assert not remaining
report['drill_readback']={'PTH_0.4mm':32,'PTH_0.6mm':92,'NPTH_3.2mm':4,'total_unique_PTH':124,'all_positions_and_diameters_match_source_within_0.0005mm':True,'max_coordinate_quantization_error_mm':drill_error,'duplicate_commands_removed':duplicates,'source_via_objects_preserved':127,'minimum_nominal_annular_ring_mm':min((v['diameter']-v['drill'])/2 for v in nodes['vias'])}
outline=gerbers['Edge_Cuts']
assert len(outline.objects)==4
ends=collections.Counter((round(x,6),round(y,6)) for o in outline.objects for x,y in [(o.x1,o.y1),(o.x2,o.y2)])
assert ends=={(0,0):2,(0,155):2,(245,0):2,(245,155):2},ends
report['outline']={'closed':True,'centerline_size_mm':[245,155],'origin':'lower left (0,0)','all_layers_unmirrored_top_view':True,'drawing_sheet_not_exported':True}

# Normalize the known KiCad 10 IPC reserved-column/mask-field defect, preserving first 71 columns.
ipc=CAM/f'{NAME}.d356'; rawipc=OUT/'verification/ipc356_KiCad_raw.d356'
if not rawipc.exists():shutil.copy2(ipc,rawipc)
lines=[]; seen=set(); corrected=0; ipc_duplicates=0
for line in rawipc.read_text().splitlines():
    if line.startswith(('317','327','367')):
        x,y=int(line[42:49])*.00254,int(line[50:57])*.00254
        if line.startswith('317'):
            v=min(nodes['vias'],key=lambda q:(q['x']-x)**2+(q['y']-y)**2)
            assert abs(v['x']-x)<.002 and abs(v['y']-y)<.002
            flag=sum(bit for name,bit in [('F_Mask',1),('B_Mask',2)] if not masks[name].covers(Point(v['x'],v['y'])))
        elif line.startswith('327'):flag=2 if int(line[39:41])==1 else 1
        else:flag=0
        revised=(line[:71]+' S'+str(flag)).ljust(80)
        corrected+=revised.rstrip()!=line.rstrip()
        if revised in seen:ipc_duplicates+=1;continue
        seen.add(revised);lines.append(revised)
    else:lines.append(line)
ipc.write_text('\n'.join(lines)+'\n',encoding='ascii')
parsed=Netlist.open(ipc)
records=[r for r in parsed.test_records if r.net_name]
unique_vias=list({(v['x'],v['y'],v['drill']):v for v in nodes['vias']}.values())
assert len(parsed.test_records)==176 and len(records)==172 and ipc_duplicates==3
assert set(r.net_name for r in records)==set(net_groups)
remaining=records.copy();maximum_error=0
for q in nodes['pads']+unique_vias:
    possible=[r for r in remaining if r.net_name==q['net'] and bool(r.is_via)==('ref' not in q)]
    r=min(possible,key=lambda r:(MM(r.x,r.unit)-q['x'])**2+(MM(r.y,r.unit)-q['y'])**2)
    error=max(abs(MM(r.x,r.unit)-q['x']),abs(MM(r.y,r.unit)-q['y']))
    assert error<.002,(q,r,error)
    maximum_error=max(maximum_error,error)
    if 'ref' in q:assert r.ref_des==q['ref'] and r.pin==q['pad'] and r.access_layer==1
    else:assert r.access_layer==0 and abs(MM(r.hole_dia,r.unit)-q['drill'])<.002
    remaining.remove(r)
assert not remaining
report['ipc356_readback']={'electrical_nodes':172,'mechanical_holes':4,'net_pin_layer_and_coordinate_match':True,'max_coordinate_quantization_error_mm':maximum_error,'format_normalized_records':corrected,'duplicate_via_records_removed':ipc_duplicates,'raw_export_archived':True,'normalization':'Reserved column 72 restored and mask code derived from actual artwork; first 71 columns unchanged.'}

jobpath=CAM/f'{NAME}-job.gbrjob'
rawjob=OUT/'verification/kicad_generated_job_raw.json'
if not rawjob.exists():shutil.copy2(jobpath,rawjob)
job=json.loads(rawjob.read_text())
job['GeneralSpecs']['Size']={'X':245.0,'Y':155.0}
job['GeneralSpecs'].pop('BoardThickness',None);job['GeneralSpecs'].pop('Finish',None)
job.pop('MaterialStackup',None);job.pop('DesignRules',None)
jobpath.write_text(json.dumps(job,indent=2),encoding='utf8')
report['job_manifest']='Unconfirmed material, thickness, copper weight, finish and stackup defaults removed; layer count and order retained.'
drc=json.loads((OUT/'verification/drc.json').read_text())
erc=json.loads((OUT/'verification/erc.json').read_text())
assert not [v for v in drc['violations'] if v['severity']=='error']
assert not drc['unconnected_items'] and not drc['schematic_parity'] and not drc['ignored_checks']
ercv=[v for s in erc['sheets'] for v in s['violations']]
assert not [v for v in ercv if v['severity']=='error']
report['kicad_checks']={'DRC_errors':0,'unconnected':0,'schematic_parity':0,'DRC_warning_counts':dict(collections.Counter(v['type'] for v in drc['violations'])),'DRC_ignored_checks':drc['ignored_checks'],'ERC_errors':0,'ERC_warning_counts':dict(collections.Counter(v['type'] for v in ercv)),'ERC_ignored_checks':erc['ignored_checks']}
manifest=json.loads((OUT/'verification/export_manifest.json').read_text())
assert sha(OUT/'source'/f'{NAME}.kicad_pcb')==manifest['exported_board_sha256']
for rel,digest in manifest['source_hashes'].items():assert sha(Path(manifest['source_project'])/rel)==digest
report['source_hashes_still_match']=True

# Render the actual four Gerbers, with actual drill positions overlaid.
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',25)
small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
panels=[]
for n,layer in enumerate(['F_Cu','In1_Cu','In2_Cu','B_Cu'],1):
    svg=str(gerbers[layer].to_svg(force_bounds=((-3,-3),(248,158)),fg='#f4c66c',bg='#0b1722'))
    svgpath=OUT/f'preview/L{n}_{layer}.svg';svgpath.write_text(svg,encoding='utf8')
    svgpath.with_suffix('.png').write_bytes(resvg_py.svg_to_bytes(svg_string=svg,width=1004,height=644,dpi=96,background='#0b1722'))
    pic=Image.open(svgpath.with_suffix('.png')).convert('RGB');draw=ImageDraw.Draw(pic)
    for kind,x,y,dia in drills:
        px,py=(x+3)*4,(158-y)*4;r=dia*2
        draw.ellipse((px-r,py-r,px+r,py+r),fill='#05090d')
    draw.rectangle((12,12,992,632),outline='#8394a3',width=1)
    panel=Image.new('RGB',(1044,715),'#0b1722')
    title=f'L{n}  {layer.replace("_", ".")}'
    title += '  / GND plane' if n==2 else ('  / via pads only' if n in [3,4] else '  / 128 patches + 16 IPEX')
    ImageDraw.Draw(panel).text((20,12),title,font=font,fill='white');panel.paste(pic,(20,58));panels.append(panel)
montage=Image.new('RGB',(2088,1550),'#0b1722');d=ImageDraw.Draw(montage)
d.text((24,16),'8 x 16 IPEX antenna | 245 x 155 mm | 4 copper layers',font=font,fill='white')
d.text((24,51),'Actual Gerber artwork + drill overlay. All layers in unmirrored top-view coordinates.',font=small,fill='#c6d2dd')
d.text((24,80),'PTH: 92 x 0.60 mm + 32 x 0.40 mm | NPTH: 4 x 3.20 mm | Material / thickness / finish: TBD',font=small,fill='#c6d2dd')
for i,panel in enumerate(panels):montage.paste(panel,((i%2)*1044,120+(i//2)*715))
montage.save(OUT/'preview/four_layer_gerber_preview.png')
(OUT/'verification/gerber_readback_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

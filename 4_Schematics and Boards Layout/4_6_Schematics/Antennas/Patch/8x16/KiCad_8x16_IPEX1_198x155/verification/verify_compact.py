"""Read back candidate copper and compare ideal array factors, not full-wave RF."""
from pathlib import Path
import collections, hashlib, json, math, sys, xml.etree.ElementTree as ET
OUT=Path(__file__).resolve().parents[1]
ROOT=next(p for p in OUT.parents if (p/'.git').exists())
sys.path.insert(0,str(ROOT/'5_Simulations/generated/antenna_4L_cam_tools'))
from gerbonara import GerberFile
from gerbonara.utils import MM
from shapely import make_valid
from shapely.geometry import Polygon,Point,GeometryCollection,box
from shapely.ops import unary_union
from PIL import Image,ImageDraw,ImageFont
import resvg_py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
NAME='Patch_Anetnna_16_8_IPEX1_198x155'
CAM=OUT/'verification/cam_readback'
nodes=json.loads((OUT/'verification/physical_net_nodes.json').read_text())
def geometry(g):
    geom=GeometryCollection();group=[];polarity=True
    for o in g.objects:
        for primitive in o.to_primitives(unit=MM):
            if primitive.polarity_dark!=polarity:
                batch=unary_union(group);geom=geom.union(batch) if polarity else geom.difference(batch)
                group=[];polarity=primitive.polarity_dark
            q=primitive.to_arc_poly().approximate_arcs(max_error=.0001)
            if len(q.outline)>=3:group.append(make_valid(Polygon(q.outline)))
    batch=unary_union(group)
    return geom.union(batch) if polarity else geom.difference(batch)
gerbers={k:GerberFile.open(CAM/f'{NAME}-{k}.{e}') for k,e in [('F_Cu','gtl'),('In1_Cu','g1'),('In2_Cu','g2'),('B_Cu','gbl'),('Edge_Cuts','gm1')]}
geoms={k:geometry(g) for k,g in gerbers.items() if k.endswith('_Cu')}
for k,g in geoms.items():assert g.difference(box(0,0,198,155)).area<1e-7,k
outline=gerbers['Edge_Cuts']
ends=collections.Counter((round(x,6),round(y,6)) for o in outline.objects for x,y in [(o.x1,o.y1),(o.x2,o.y2)])
assert len(outline.objects)==4 and ends=={(0,0):2,(198,0):2,(0,155):2,(198,155):2}
components,parent={},{}
for k,g in geoms.items():
    parts=list(g.geoms) if hasattr(g,'geoms') else [g]
    components[k]=[(i,p) for i,p in enumerate(parts) if p.area>1e-9]
    for i,_ in components[k]:parent[(k,i)]=(k,i)
def find(k):
    while parent[k]!=k:parent[k]=parent[parent[k]];k=parent[k]
    return k
def union(a,b):parent[find(b)]=find(a)
def locate(layer,x,y):
    hits=[(layer,i) for i,g in components[layer] if g.distance(Point(x,y))<.002]
    assert len(hits)<=1
    return hits[0] if hits else None
terminals=[]
for v in nodes['vias']:
    hits=[k for layer in geoms if (k:=locate(layer,v['x'],v['y'])) is not None]
    assert len(hits)==4
    for k in hits[1:]:union(hits[0],k)
    terminals.extend((v['net'],k) for k in hits)
for q in nodes['pads']:
    k=locate('F_Cu',q['x'],q['y']);assert k is not None;terminals.append((q['net'],k))
for q in nodes['patches']:
    x1,y1,x2,y2=q['bounds'];target=box(x1,y1,x2,y2)
    assert target.difference(geoms['F_Cu']).area<1e-7
    k=locate('F_Cu',(x1+x2)/2,(y1+y2)/2);assert k is not None;terminals.append((q['net'],k))
netgroups,componentnets=collections.defaultdict(set),collections.defaultdict(set)
for net,k in terminals:netgroups[net].add(find(k));componentnets[find(k)].add(net)
assert len(netgroups)==17 and all(len(v)==1 for v in netgroups.values()) and all(len(v)==1 for v in componentnets.values())
assert all(find(k) in componentnets for k in parent)
plane=max((g for _,g in components['In1_Cu']),key=lambda g:g.area)
assert all(plane.covers(Point(v['x'],v['y'])) for v in nodes['vias'])
clearances={}
for layer,parts in components.items():
    ds=[a.distance(b) for i,a in parts for j,b in parts if j>i and find((layer,i))!=find((layer,j))]
    clearances[layer]=min(ds) if ds else None
    assert not ds or min(ds)>=.249
drc=json.loads((OUT/'verification/drc.json').read_text())
assert not [v for v in drc['violations'] if v['severity']=='error']
assert not drc['unconnected_items'] and not drc['schematic_parity'] and not drc['ignored_checks']
erc=json.loads((OUT/'verification/erc.json').read_text())
assert not [v for s in erc['sheets'] for v in s['violations'] if v['severity']=='error']
netxml=ET.parse(OUT/'verification/schematic_netlist.xml')
sch={n.attrib['name']:sorted((i.attrib['ref'],i.attrib['pin']) for i in n.findall('node')) for n in netxml.findall('./nets/net')}
pcb=collections.defaultdict(list)
for q in nodes['pads']:pcb[q['net']].append((q['ref'],q['pad']))
assert sch=={k:sorted(v) for k,v in pcb.items()}

wave=299792458/10.5e9*1000
def array_power(angle,d):
    psi=math.pi*d*math.sin(math.radians(angle))/wave
    return 1 if abs(psi)<1e-12 else (math.sin(16*psi)/(16*math.sin(psi)))**2
def hpbw(d):
    lo,hi=0,math.degrees(math.asin(wave/(16*d)))
    for i in range(80):
        mid=(lo+hi)/2
        if array_power(mid,d)>.5:lo=mid
        else:hi=mid
    return lo+hi
ideal={'frequency_GHz':10.5,'columns':16,'old_pitch_mm':14.34,'new_pitch_mm':12,'old_horizontal_HPBW_deg':hpbw(14.34),'new_horizontal_HPBW_deg':hpbw(12),'beamwidth_increase_percent':(hpbw(12)/hpbw(14.34)-1)*100,'assumptions':'Uniform amplitude, in-phase broadside excitation, uncoupled identical column elements; excludes element pattern, dielectric/ground-edge effects, losses, matching and mutual coupling. Not full-wave RF validation.'}
report={'board_size_mm':[198,155],'layer_count':4,'patches':128,'connector_pads':48,'nets':17,'all_nets_connected':True,'shorts_between_nets':0,'unassigned_copper_islands':0,'all_ground_vias_touch_In1_plane':True,'min_different_net_clearance_mm':clearances,'DRC_errors':0,'unconnected':0,'schematic_parity':0,'DRC_warning_counts':dict(collections.Counter(v['type'] for v in drc['violations'])),'ERC_errors':0,'schematic_pcb_17_nets_48_pad_nodes_match':True,'ideal_array_factor':ideal}
manifest=json.loads((OUT/'verification/compact_layout_audit.json').read_text())
for rel,digest in manifest['source_hashes'].items():assert hashlib.sha256((Path(manifest['source_project'])/rel).read_bytes()).hexdigest()==digest
report['source_hashes_still_match']=True
(OUT/'verification/final_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')

# Same-scale comparison rendered from actual Gerbers, then an explicitly ideal plot.
oldbase=ROOT/'4_Schematics and Boards Layout/4_7_Production Files/Gerber_Patch_Antenna_8x16_IPEX1_245x155_4L_20260920'
old=GerberFile.open(oldbase/'cam/Patch_Anetnna_16_8_IPEX1-F_Cu.gtl')
fontpath='C:/Windows/Fonts/msyh.ttc';font=ImageFont.truetype(fontpath,26);small=ImageFont.truetype(fontpath,19)
pic=Image.new('RGB',(1600,1130),'#0b1722');draw=ImageDraw.Draw(pic)
draw.text((24,15),'保留 16 路、8×16 贴片：245 mm → 198 mm',font=font,fill='white')
draw.text((24,55),'同一比例显示实际顶层铜图形；只压缩列间距，单个贴片与纵向馈线尺寸保持。',font=small,fill='#c6d2dd')
for j,(g,w,title) in enumerate([(old,245,'原版：245×155 mm / 列距 14.34 mm'),(gerbers['F_Cu'],198,'候选：198×155 mm / 列距 12.00 mm')]):
    svg=str(g.to_svg(force_bounds=((-4,-4),(249,159)),fg='#f4c66c',bg='#0b1722'))
    png=resvg_py.svg_to_bytes(svg_string=svg,width=759,height=489,dpi=96,background='#0b1722')
    import io
    layerpic=Image.open(io.BytesIO(png)).convert('RGB');d=ImageDraw.Draw(layerpic)
    d.rectangle((12,12,(w+4)*3,477),outline='#8ba2b3',width=2)
    pic.paste(layerpic,(20+j*800,145));draw.text((24+j*800,107),title,font=small,fill='white')
draw.text((24,651),'以下为 10.5 GHz、16 列等幅同相的理想阵列因子；不是全波仿真或实测。',font=small,fill='#c6d2dd')
plt.rcParams['font.family']='DejaVu Sans'
fig,ax=plt.subplots(figsize=(15.4,3.8),dpi=100);fig.patch.set_facecolor('#0b1722');ax.set_facecolor('#0b1722')
angles=[-25+i*.025 for i in range(2001)]
for d,color,label in [(14.34,'#f4c66c',f'Original: HPBW {hpbw(14.34):.2f} deg'),(12,'#62d6e4',f'Compact: HPBW {hpbw(12):.2f} deg')]:
    ax.plot(angles,[10*math.log10(max(array_power(a,d),1e-6)) for a in angles],color=color,label=label,linewidth=2)
ax.set_xlim(-25,25);ax.set_ylim(-40,1);ax.set_xlabel('Angle from broadside (deg)',color='white');ax.set_ylabel('Normalized array power (dB)',color='white');ax.tick_params(colors='white');ax.grid(alpha=.2)
for s in ax.spines.values():s.set_color('#8ba2b3')
legend=ax.legend(facecolor='#182936',edgecolor='#8ba2b3')
for t in legend.get_texts():t.set_color('white')
fig.tight_layout();buf=io.BytesIO();fig.savefig(buf,format='png',facecolor=fig.get_facecolor());plt.close(fig);buf.seek(0)
pic.paste(Image.open(buf).convert('RGB'),(30,704))
draw.text((24,1090),'主瓣预计加宽约 19.5%；互耦、输入匹配、实际增益和扫描标定需另行验证。',font=small,fill='#c6d2dd')
pic.save(OUT/'preview/width_comparison.png')
print(json.dumps(report,ensure_ascii=False,indent=2))

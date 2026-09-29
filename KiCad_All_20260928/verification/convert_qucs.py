"""Reconstruct editable KiCad diagrams from the eight QucsStudio 5.8 sources.
No Qucs or ngspice simulation equivalence is claimed. Every source parameter is retained.
"""
from pathlib import Path
import collections, hashlib, json, math, re, shutil, subprocess, uuid
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parent
CLI=r'D:\3_Software\KiCAD\bin\kicad-cli.exe'
S=0.254
def q(x): return json.dumps(str(x),ensure_ascii=False)
def uid(): return str(uuid.uuid4())
def num(x): return f'{x:.5f}'.rstrip('0').rstrip('.') if x else '0'
def effects(size=1.27,hide=False):return f'(effects (font (size {size} {size}))'+(' (hide yes)' if hide else '')+')'
def section(text,key):return text.split('<'+key+'>')[1].split('</'+key+'>')[0].strip().splitlines()
def components(text):
    result=[]
    for line in section(text,'Components'):
        head=line.split('"',1)[0].split()
        typ,ref=head[:2]
        a,x,y,dx,dy,orient=map(int,head[2:8])
        params=[{'value':v,'visible':bool(int(show))} for v,show in re.findall(r'"([^\"]*)"([01])',line)]
        result.append(dict(type=typ,ref=ref,active=bool(a),x=x,y=y,dx=dx,dy=dy,orientation=orient,parameters=params,source_line=line))
    return result
def pin_positions(c):
    typ=c['type'];o=c['orientation']
    if typ in ('R','L','C','MLIN'):
        assert o in (0,1)
        return [(-30,0),(30,0)] if o==0 else [(0,-30),(0,30)]
    if typ in ('Pac','Vfile'): assert o==0;return [(0,-30),(0,30)]
    if typ=='MTEE': assert o==2;return [(-30,0),(30,0),(0,-30)]
    if typ=='Tr': assert o==0;return [(-30,-30),(-30,30),(30,-30),(30,30)]
    if typ=='SPfile':
        n=int(c['parameters'][1]['value']);assert n in (2,3)
        return [(-30,0),(30,0),(0,30)] if n==2 else [(-30,-30),(30,-30),(-30,30),(0,60)]
    raise ValueError(typ)

def symbol_def(c,name):
    typ=c['type'];pins=pin_positions(c)
    def poly(points):return '(polyline (pts '+' '.join(f'(xy {num(x*S)} {num(-y*S)})' for x,y in points)+') (stroke (width 0.254) (type default)) (fill (type none)))'
    def orient(points):return [(-y,x) for x,y in points] if c['orientation']==1 else points
    def circle(x,y,r):return f'(circle (center {num(x*S)} {num(-y*S)}) (radius {num(r*S)}) (stroke (width 0.254) (type default)) (fill (type none)))'
    graphics=[]
    if typ=='R':graphics=[poly(orient([(-20,-7),(20,-7),(20,7),(-20,7),(-20,-7)]))]
    elif typ=='C':graphics=[poly(orient([(-4,-13),(-4,13)])),poly(orient([(4,-13),(4,13)]))]
    elif typ=='L':
        pts=[(-20,0)]
        for i in range(4):
            pts += [(-20+i*10+j, -8*math.sin(math.pi*j/10)) for j in range(11)]
        graphics=[poly(orient(pts))]
    elif typ in ('Pac','Vfile'):
        graphics=[circle(0,0,16),poly([(-5,-7),(5,-7)]),poly([(0,-12),(0,-2)]),poly([(-5,7),(5,7)])]
    elif typ=='MLIN':graphics=[poly(orient([(-20,-8),(20,-8),(20,8),(-20,8),(-20,-8)]))]
    elif typ=='MTEE':graphics=[poly([(-20,0),(20,0)]),poly([(0,0),(0,-20)])]
    elif typ=='Tr':graphics=[poly([(-12,-25),(-12,25)]),poly([(12,-25),(12,25)]),poly([(-3,-25),(-3,25)]),poly([(3,-25),(3,25)])]
    else:
        three=len(pins)==4
        graphics=[poly([(-20,-45 if three else -16),(20,-45 if three else -16),(20,45 if three else 16),(-20,45 if three else 16),(-20,-45 if three else -16)])]
    pintext=[]
    for i,(x,y) in enumerate(pins,1):
        angle=0 if x<0 else 180 if x>0 else 270 if y<0 else 90
        length=26 if typ=='C' else 14 if typ in ('Pac','Vfile') else 10
        if typ=='Tr':length=18
        if typ=='SPfile' and i==len(pins):length=14 if len(pins)==3 else 15
        pname=('GND' if i==len(pins) else 'RF'+str(i)) if typ=='SPfile' else str(i)
        pintext.append(f'(pin passive line (at {num(x*S)} {num(-y*S)} {angle}) (length {num(length*S)}) (name {q(pname)} {effects(0.9)}) (number {q(i)} {effects(0.9)}))')
    showpins=typ in ('SPfile','MTEE','Tr')
    return f'''(symbol {q(name)} (pin_names (offset 0.508){'' if showpins else ' hide'}) {'' if showpins else '(pin_numbers hide)'} (in_bom yes) (on_board no)
      (property "Reference" "X" (at 0 10 0) {effects()})
      (property "Value" {q(typ)} (at 0 -10 0) {effects()})
      (symbol {q(name.split(':')[-1]+'_0_1')} {' '.join(graphics)})
      (symbol {q(name.split(':')[-1]+'_1_1')} {' '.join(pintext)}))'''

def convert(path):
    text=path.read_text(encoding='utf-8-sig');cs=components(text)
    wires=[];labels=[]
    for line in section(text,'Wires'):
        toks=line.split();x1,y1,x2,y2=map(int,toks[:4])
        if (x1,y1)!=(x2,y2):wires.append(((x1,y1),(x2,y2)))
        label=re.search(r'"([^\"]+)"',line)
        if label:labels.append(((x1,y1),label[1]))
    circuits=[c for c in cs if c['type'] not in ('GND','.SP','.TR','SUBST')]
    configs=[c for c in cs if c['type'] in ('.SP','.TR','SUBST')]
    grounds=[c for c in cs if c['type']=='GND']
    name=path.stem;d=OUT/'Simulations'/name;d.mkdir(parents=True,exist_ok=True)
    original=d/'original';original.mkdir(exist_ok=True);shutil.copy2(path,original/path.name)
    dep=[]
    for c in circuits:
        if c['type'] not in ('SPfile','Vfile'):continue
        old=c['parameters'][0]['value'];file=path.parent/old
        if not file.is_file():
            matches=list((ROOT/'7_Components Datasheets and Application notes').rglob(Path(old).name))
            file=matches[0] if len(matches)==1 else None
        if file and file.is_file():
            dest=d/'models'/file.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(file,dest)
            c['local_model']='models/'+file.name
            dep.append({'ref':c['ref'],'original':old,'local':c['local_model'],'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
        else:dep.append({'ref':c['ref'],'original':old,'missing':True})
    minx=min(c['x'] for c in cs)-60;miny=min(c['y'] for c in cs)-60
    maxx=max(c['x'] for c in cs)+100;maxy=max(c['y'] for c in cs)+100
    width=max(297,(maxx-minx)*S+70);height=max(210,(maxy-miny)*S+120+len(configs)*25)
    def xy(pt):return num((pt[0]-minx)*S+20.32),num((pt[1]-miny)*S+30.48)
    root=uid();defs={};body=[];expected_pin_positions={}
    def txt(value,x,y,size=1.27):return f'(text {q(value)} (at {num(x)} {num(y)} 0) (effects (font (size {size} {size})) (justify left top)) (uuid "{uid()}"))'
    body.append(txt(name+' / QucsStudio circuit',20,12,2.0))
    body.append(txt('Editable diagram and parameters only. Simulation models are NOT configured. Crossed components were inactive in Qucs.',20,20,1.15))
    for c in circuits:
        variant=c['type']+'_'+str(c['orientation'])+('_'+c['parameters'][1]['value'] if c['type']=='SPfile' else '')
        lib='Qucs_Imported:'+variant
        if lib not in defs:defs[lib]=symbol_def(c,lib)
        x,y=xy((c['x'],c['y']));x=float(x);y=float(y)
        values=[v['value'] for v in c['parameters']]
        value=values[0] if c['type'] in ('R','L','C','Tr') else ('Z='+values[1] if c['type']=='Pac' else ('W='+values[1]+' L='+values[2] if c['type']=='MLIN' else 'S'+values[1]+'P' if c['type']=='SPfile' else c['type']))
        # Keep the source field placement. KiCad fields remain horizontal for legibility.
        fx=x+c['dx']*S;fy=y+c['dy']*S
        props=[f'(property "Reference" {q(c["ref"])} (at {num(fx)} {num(fy)} 0) (effects (font (size 1.15 1.15)) (justify left)))',f'(property "Value" {q(value)} (at {num(fx)} {num(fy+3)} 0) (effects (font (size 1.0 1.0)) (justify left)))']
        for k,v in [('Qucs_Type',c['type']),('Qucs_Active',str(int(c['active']))),('Qucs_SourceLine',c['source_line'])]+[(f'Qucs_Param_{i:02}',v) for i,v in enumerate(values,1)]+([('Local_Model',c['local_model'])] if 'local_model' in c else []):
            props.append(f'(property {q(k)} {q(v)} (at {num(x)} {num(y)} 0) {effects(1.0,True)})')
        body.append(f'(symbol (lib_id {q(lib)}) (at {num(x)} {num(y)} 0) (unit 1) (exclude_from_sim yes) (in_bom yes) (on_board no) (dnp {"no" if c["active"] else "yes"}) (uuid "{uid()}") '+ ' '.join(props)+f' (instances (project {q(name)} (path "/{root}" (reference {q(c["ref"])}) (unit 1)))))')
        for i,(px,py) in enumerate(pin_positions(c),1):expected_pin_positions[(c['ref'],str(i))]=(c['x']+px,c['y']+py)
    allpoints=set(expected_pin_positions.values())|{p for wire in wires for p in wire}|{(c['x'],c['y']) for c in grounds}|{p for p,_ in labels}
    def on_segment(p,a,b):return (p[0]-a[0])*(b[1]-a[1])==(p[1]-a[1])*(b[0]-a[0]) and min(a[0],b[0])<=p[0]<=max(a[0],b[0]) and min(a[1],b[1])<=p[1]<=max(a[1],b[1])
    parents={p:p for p in allpoints}
    def find(p):
        while parents[p]!=p:parents[p]=parents[parents[p]];p=parents[p]
        return p
    def union(a,b):parents[find(a)]=find(b)
    edges=set()
    for a,b in wires:
        pts=sorted((p for p in allpoints if on_segment(p,a,b)),key=lambda p:(p[0]-a[0])**2+(p[1]-a[1])**2)
        for p1,p2 in zip(pts,pts[1:]):
            union(p1,p2);edge=tuple(sorted([p1,p2]));edges.add(edge)
    deg=collections.Counter()
    for a,b in edges:
        ax,ay=xy(a);bx,by=xy(b)
        body.append(f'(wire (pts (xy {ax} {ay}) (xy {bx} {by})) (stroke (width 0) (type default)) (uuid "{uid()}"))');deg[a]+=1;deg[b]+=1
    for p,count in deg.items():
        if count>2 or (count>1 and p in expected_pin_positions.values()):
            x,y=xy(p);body.append(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid "{uid()}"))')
    for c in grounds:
        p=(c['x'],c['y']);x,y=map(float,xy(p));direction=-1 if c['orientation']==4 else 1
        body.append(f'(label "GND" (at {num(x)} {num(y)} 0) {effects(0.9)} (uuid "{uid()}"))')
        for half,off in [(7,5),(4,8),(1,11)]:
            body.append(f'(polyline (pts (xy {num(x-half*S)} {num(y+direction*off*S)}) (xy {num(x+half*S)} {num(y+direction*off*S)})) (stroke (width 0.254) (type default)) (fill (type none)) (uuid "{uid()}"))')
        body.append(f'(polyline (pts (xy {num(x)} {num(y)}) (xy {num(x)} {num(y+direction*5*S)})) (stroke (width 0.254) (type default)) (fill (type none)) (uuid "{uid()}"))')
    groups=collections.defaultdict(list)
    for p,label in labels+[((c['x'],c['y']),'GND') for c in grounds]:groups[label].append(p)
    for pts in groups.values():
        for p in pts[1:]:union(pts[0],p)
    for p,label in labels:
        x,y=xy(p);body.append(f'(label {q(label)} (at {x} {y} 0) {effects(1.15)} (uuid "{uid()}"))')
    for line in section(text,'Paintings'):
        if line.startswith('Text '):
            a=line.split(' ',6);x,y=map(float,xy((int(a[1]),int(a[2]))));body.append(txt(a[6].replace('\\n','\n').replace('\\\\Omega','Ω'),x,y,1.4))
        else: raise ValueError('Unsupported painting '+line)
    notes_y=(maxy-miny)*S+35
    body.append(txt('Original simulation settings / all ordered parameters are also stored in source_parameters.json',20,notes_y,1.4))
    for i,c in enumerate(configs):
        description=f'{c["type"]} {c["ref"]} | active={int(c["active"])}\n'+'; '.join(f'{j}: {p["value"]}' for j,p in enumerate(c['parameters'],1))
        body.append(txt(description,20,notes_y+10+i*25,1.15))
    sch=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid "{root}") (paper "User" {num(width)} {num(height)}) (lib_symbols '+ '\n'.join(defs.values())+')\n'+'\n'.join(body)+'\n(sheet_instances (path "/" (page "1"))))\n'
    schpath=d/(name+'.kicad_sch');schpath.write_text(sch,encoding='utf-8')
    (d/(name+'.kicad_pro')).write_text(json.dumps({'meta':{'filename':name+'.kicad_pro','version':3},'schematic':{'top_level_sheets':[{'filename':name+'.kicad_sch','name':'','uuid':root}]}},indent=2),encoding='utf-8')
    (d/'Qucs_Imported.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+'\n'.join(v.replace(q(k),q(k.split(':')[-1]),1) for k,v in defs.items())+')\n',encoding='utf-8')
    (d/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "Qucs_Imported") (type "KiCad") (uri "${KIPRJMOD}/Qucs_Imported.kicad_sym") (options "") (descr "Qucs diagrams only; simulation models not configured")))\n',encoding='utf-8')
    (d/'source_parameters.json').write_text(json.dumps({'source':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'components':cs,'wires':section(text,'Wires'),'paintings':section(text,'Paintings'),'properties':section(text,'Properties'),'dependencies':dep},ensure_ascii=False,indent=2),encoding='utf-8')
    xml=OUT/'verification'/(name+'_qucs.xml')
    run=subprocess.run([CLI,'sch','export','netlist','--format','kicadxml','-o',str(xml),str(schpath)],capture_output=True,encoding='utf-8',errors='replace')
    assert run.returncode==0,run.stdout+run.stderr
    tree=ET.parse(xml);actual={}
    for n in tree.findall('nets/net'):
        for pin in n.findall('node'):actual[(pin.attrib['ref'],pin.attrib['pin'])]=n.attrib['name']
    expected=collections.defaultdict(set)
    for pin,pos in expected_pin_positions.items():expected[find(pos)].add(pin)
    splits=[sorted(v) for v in expected.values() if len({actual.get(p,'MISSING') for p in v})>1]
    rev={p:k for k,v in expected.items() for p in v}
    actual_groups=collections.defaultdict(set)
    for pin,net in actual.items():actual_groups[net].add(pin)
    merges=[sorted(v) for v in actual_groups.values() if len({rev[p] for p in v if p in rev})>1]
    result={'project':name,'source_components_including_ground_and_settings':len(cs),'circuit_components':len(circuits),'kicad_components':len(tree.findall('components/comp')),'inactive_circuit_components':sum(not c['active'] for c in circuits),'ground_markers':len(grounds),'configuration_blocks':len(configs),'wires_source':len(wires),'wires_after_splitting':len(edges),'missing_pins':sorted(set(expected_pin_positions)-set(actual)),'split_nets':splits,'merged_nets':merges,'dependencies':dep,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'validation_scope':'Coordinate and terminal connectivity reconstruction; simulation behavior not validated'}
    assert not result['missing_pins'] and not splits and not merges,result
    assert result['circuit_components']==result['kicad_components'],result
    return result

if __name__=='__main__':
    results=[]
    for row in json.loads((OUT/'source_inventory.json').read_text(encoding='utf-8')):
        if row['kind']=='qucsstudio':
            result=convert(ROOT/row['path']);results.append(result);print({k:v for k,v in result.items() if k not in ('dependencies','validation_scope')},flush=True)
    (OUT/'verification/qucs_conversion_audit.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')

"""Build a self-contained KiCad replacement project using the installed KiCad Python."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET
import pcbnew as pcb
import wx

APP = wx.App(False)
PLUGIN = pcb.PCB_IO_MGR.FindPlugin(pcb.PCB_IO_MGR.KICAD_SEXP)

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.git').exists() and (p/'4_Schematics and Boards Layout').exists())
BASE = ROOT / '4_Schematics and Boards Layout/4_6_Schematics/Antennas/Patch/4x4'
OUT = BASE / 'Phased_Array_Ant_IPEX1'
NAME = 'Phased_Array_Ant_IPEX1'
LIB = 'PLFM_RF'
FP = 'ECT_818000368_IPEX1_1.25mm'
SOURCE = ROOT / '4_Schematics and Boards Layout/4_7_Production Files/Gerber_Patch_Antenna_70x70_4L_Via03_20260918/source/Phased_Array_Ant_70x70_4L_Via03.kicad_pcb'
PDF = Path(r'D:\2_Works\4_Procedures\4_CIS_DataBase_Management\outputs\library_sync_v0_2_0_20260915\client\Data\CIS_Lib\YC.DZ.SS-连接器\YC.DZ.SS00008--818000368(USS RF插座,I代,H1.25mm,三焊脚,外壳镀金,白色)SPEC_E.pdf')
for d in [OUT, OUT/'PLFM_RF.pretty', OUT/'datasheets', OUT/'verification', OUT/'preview']:
    d.mkdir(parents=True, exist_ok=True)
shutil.copy2(PDF, OUT/'datasheets/ECT_818000368_SPEC_E.pdf')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
uid = lambda s: str(uuid.uuid5(uuid.NAMESPACE_URL, 'PLFM-RADAR/IPEX1/' + s))
q = lambda s: json.dumps(str(s), ensure_ascii=False)
mm = pcb.FromMM
vec = lambda x, y: pcb.VECTOR2I(mm(x), mm(y))
xy = lambda v: [round(pcb.ToMM(v.x),6), round(pcb.ToMM(v.y),6)]

# Pad numbering is our library convention, not the mechanical BOM callouts.
footprint = f'''(footprint "{FP}" (version 20241229) (generator "pcbnew")
 (layer "F.Cu")
 (descr "ECT 818000368, USS RF I generation, H=1.25mm; SPEC E page 7; project pins 1=SIG, 2/3=GND")
 (tags "ECT 818000368 IPEX I-PEX I generation U.FL 3pad")
 (attr smd)
 (fp_text reference "REF**" (at 0 -2.5) (layer "F.SilkS") (effects (font (size 0.7 0.7) (thickness 0.12))))
 (fp_text value "818000368" (at 0 3.0) (layer "F.Fab") (effects (font (size 0.7 0.7) (thickness 0.1))))
 (fp_rect (start -1.3 -1.3) (end 1.3 1.3) (stroke (width 0.1) (type solid)) (fill none) (layer "F.Fab"))
 (fp_circle (center 0 0) (end 1 0) (stroke (width 0.1) (type solid)) (fill none) (layer "F.Fab"))
 (fp_line (start 0 1.3) (end 0 1.95) (stroke (width 0.1) (type solid)) (layer "F.Fab"))
 (fp_rect (start -2.25 -1.55) (end 2.25 2.30) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))
 (fp_line (start -0.75 -1.45) (end 0.75 -1.45) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
 (fp_line (start -0.75 1.45) (end -0.75 2.15) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
 (fp_line (start 0.75 1.45) (end 0.75 2.15) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
 (pad "1" smd rect (at 0 1.525) (size 1 1.05) (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin 0.05))
 (pad "2" smd rect (at -1.475 0) (size 1.05 2.2) (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin 0.05))
 (pad "3" smd rect (at 1.475 0) (size 1.05 2.2) (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin 0.05))
 (zone (net 0) (net_name "") (layer "F.Cu") (uuid "{uid('keepout')}")
   (name "No copper under connector insulator") (hatch edge 0.25)
   (connect_pads (clearance 0)) (min_thickness 0.1)
   (keepout (tracks not_allowed) (vias not_allowed) (pads not_allowed) (copperpour not_allowed) (footprints allowed))
   (fill (thermal_gap 0.2) (thermal_bridge_width 0.2))
   (polygon (pts (xy -0.94 -1.1) (xy 0.94 -1.1) (xy 0.94 0.99) (xy -0.94 0.99))))
)'''
(OUT/'PLFM_RF.pretty'/f'{FP}.kicad_mod').write_text(footprint, encoding='utf-8')

def prop(k,v,x=0,y=0,hide=True):
    return f'(property {q(k)} {q(v)} (at {x:g} {y:g} 0) (effects (font (size 1.27 1.27)){" hide" if hide else ""}))'

def pin(n,name,x,y,a,length=2.54):
    return f'''(pin passive line (at {x:g} {y:g} {a}) (length {length:g})
    (name {q(name)} (effects (font (size 0.9 0.9))))
    (number {q(n)} (effects (font (size 0.9 0.9)))))'''

def symbol(name,embedded=False):
    connector = name == 'ECT_818000368'
    prefix = 'J' if connector else 'U'
    value = '818000368' if connector else '10.5GHZ_ANT'
    footprint = FP if connector else 'Patch_10p5GHz_9.538x7.636mm'
    body = f'(symbol {q((LIB+":" if embedded else "")+name)} (pin_names (offset 0.4)) (in_bom yes) (on_board yes)\n'
    body += prop('Reference',prefix,0,5.08,False)+prop('Value',value,0,-11.43 if connector else -7.62,False)
    body += prop('Footprint',f'{LIB}:{footprint}')
    body += prop('Datasheet','${KIPRJMOD}/datasheets/ECT_818000368_SPEC_E.pdf' if connector else '')
    body += prop('Description', 'ECT USS RF I generation, 3 solder pads, 1.25mm high, 50 ohm, DC-6GHz' if connector else 'Original 10.5GHz printed antenna element, copper dimensions unchanged')
    if connector:
        body += prop('Manufacturer','ECT')+prop('MPN','818000368')+prop('MaterialCode','YC.DZ.SS00008')
        body += f'''(symbol "{name}_0_1"
          (circle (center 0 0) (radius 2.54) (stroke (width 0.254) (type default)) (fill (type none)))
          (circle (center 0 0) (radius 0.635) (stroke (width 0.254) (type default)) (fill (type none)))
          (polyline (pts (xy 0.635 0) (xy 2.54 0)) (stroke (width 0.254) (type default)) (fill (type none)))
          (polyline (pts (xy -1.27 -2.2) (xy -1.27 -5.08)) (stroke (width 0.254) (type default)) (fill (type none)))
          (polyline (pts (xy 1.27 -2.2) (xy 1.27 -5.08)) (stroke (width 0.254) (type default)) (fill (type none))))
          (symbol "{name}_1_1"
          {pin('1','SIG',7.62,0,180,5.08)}
          {pin('2','GND',-1.27,-7.62,90)}
          {pin('3','GND',1.27,-7.62,90)})'''
    else:
        body += f'''(symbol "{name}_0_1"
          (rectangle (start -5.08 3.81) (end 5.08 -3.81) (stroke (width 0.254) (type default)) (fill (type background))))
          (symbol "{name}_1_1" {pin('P$1','FEED',-10.16,0,0,5.08)})'''
    return body+')'

(OUT/f'{LIB}.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor")\n'+symbol('ECT_818000368')+'\n'+symbol('Patch_10p5GHz')+'\n)',encoding='utf-8')
(OUT/'sym-lib-table').write_text(f'(sym_lib_table (version 7) (lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIB}.kicad_sym") (options "") (descr "Project RF symbols")))\n',encoding='utf-8')
(OUT/'fp-lib-table').write_text(f'(fp_lib_table (version 7) (lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIB}.pretty") (options "") (descr "Project RF footprints")))\n',encoding='utf-8')

source_sch = ET.parse(BASE/'Phased_Array_Ant.sch')
parts = {p.attrib['name']:p.attrib for p in source_sch.findall('.//parts/part')}
rootid = uid('sheet')
uuids = {}
sch = [f'''(kicad_sch (version 20250114) (generator "eeschema")
 (uuid "{rootid}") (paper "A3")
 (title_block (title "4 x 4 Phased Array - IPEX I Generation") (date "2026-09-20") (rev "IPEX1-A2")
 (comment 1 "ECT 818000368 / SPEC E / YC.DZ.SS00008")
 (comment 2 "4L Via03 / Connector rated DC-6GHz / RF validation required"))
 (lib_symbols {symbol('ECT_818000368',True)} {symbol('Patch_10p5GHz',True)})''']
def wire(x1,y1,x2,y2,key):
    sch.append(f'(wire (pts (xy {x1:g} {y1:g}) (xy {x2:g} {y2:g})) (stroke (width 0) (type default)) (uuid "{uid(key)}"))')
def label(text,x,y,key):
    sch.append(f'(global_label {q(text)} (shape input) (at {x:g} {y:g} 0) (effects (font (size 1 1)) (justify left)) (uuid "{uid(key)}"))')
def place(ref,lib,x,y,value,fp):
    uuid_ = uid(ref)
    uuids[ref]=uuid_
    props=prop('Reference',ref,x,y-6.35,False)+prop('Value',value,x,y+17.78,False)+prop('Footprint',f'{LIB}:{fp}')
    props+=prop('Datasheet','${KIPRJMOD}/datasheets/ECT_818000368_SPEC_E.pdf' if ref.startswith('J') else '')
    if ref.startswith('J'):
        props+=prop('ArrayPosition',parts[ref]['value'])+prop('Manufacturer','ECT')+prop('MPN','818000368')+prop('MaterialCode','YC.DZ.SS00008')
    sch.append(f'''(symbol (lib_id "{LIB}:{lib}") (at {x:g} {y:g} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no)
      (uuid "{uuid_}") {props}
      (instances (project "{NAME}" (path "/{rootid}" (reference "{ref}") (unit 1)))))''')
for i in range(1,17):
    # Physical array coordinates: row 1 at the top, J1..J4 at the bottom.
    r,c = map(int, parts[f'J{i}']['value'].split('_'))
    x,y = 31.75+(c-1)*93.98, 40.64+(r-1)*55.88
    place(f'J{i}','ECT_818000368',x,y,'818000368',FP)
    place(f'U${i}','Patch_10p5GHz',x+48.26,y,'10.5GHZ_ANT','Patch_10p5GHz_9.538x7.636mm')
    wire(x+7.62,y,x+38.1,y,f'sig{i}')
    wire(x+20.32,y,x+20.32,y-3.81,f'sigbranch{i}')
    sch.append(f'(junction (at {x+20.32:g} {y:g}) (diameter 0) (color 0 0 0 0) (uuid "{uid(f"sigjunction{i}")}"))')
    label(f'N${i}',x+20.32,y-3.81,f'netlabel{i}')
    wire(x-1.27,y+7.62,x-1.27,y+11.43,f'gnda{i}')
    wire(x+1.27,y+7.62,x+1.27,y+11.43,f'gndb{i}')
    wire(x-1.27,y+11.43,x+1.27,y+11.43,f'gndc{i}')
    label('GND',x+1.27,y+11.43,f'gndlabel{i}')
    sch.append(f'(text "Array {r}_{c}" (at {x:g} {y-13.97:g} 0) (effects (font (size 1.5 1.5)) (justify left)) (uuid "{uid(f"array{i}")}"))')
sch.append(f'''(text "Pin convention: 1 = SIG, 2 / 3 = GND (both shell terminals).\\nConnector: ECT 818000368, I generation, H 1.25 mm, rated DC - 6 GHz.\\nOriginal patch copper and N$1 - N$16 connectivity retained. 10.5 GHz RF performance requires validation."
 (at 25.4 254 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{uid('notes')}"))
 (sheet_instances (path "/" (page "1"))) )''')
(OUT/f'{NAME}.kicad_sch').write_text('\n'.join(sch),encoding='utf-8')
if '--schematic-only' in sys.argv:
    if Path(__file__).resolve() != (OUT/'verification/build_ipex.py').resolve():
        shutil.copy2(__file__,OUT/'verification/build_ipex.py')
    sys.exit(0)

# Preserve all antenna copper, signal vias, inner planes, outline, and mount holes.
b = pcb.LoadBoard(str(SOURCE))
def track_snapshot(board):
    return sorted([[t.GetNetname(),type(t).__name__,xy(t.GetStart()),xy(t.GetEnd()),t.GetLayer(),
                    mm(0)+t.GetWidth(pcb.F_Cu) if isinstance(t,pcb.PCB_VIA) else t.GetWidth(),
                    t.GetDrillValue() if isinstance(t,pcb.PCB_VIA) else 0]
                   for t in board.GetTracks()])
before = track_snapshot(b)
def setpath(fp,ref):
    path=pcb.KIID_PATH()
    path.push_back(pcb.KIID(rootid)); path.push_back(pcb.KIID(uuids[ref]))
    fp.SetPath(path)
def setid(fp,name):
    fp.SetFPID(pcb.LIB_ID(LIB,name))
def size_text(t,s=0.8):
    t.SetTextSize(vec(s,s)); t.SetTextThickness(mm(.12))

source_fp = list(b.GetFootprints())
antenna = next(f for f in source_fp if f.GetReference()=='U$1')
antlib = pcb.FOOTPRINT(antenna)
antlib.SetPosition(vec(0,0)); antlib.SetReference('REF**'); antlib.SetValue('10.5GHZ_ANT')
antlib.SetPath(pcb.KIID_PATH()); setid(antlib,'Patch_10p5GHz_9.538x7.636mm')
for p in antlib.Pads(): p.SetNetCode(0)
PLUGIN.FootprintSave(str(OUT/'PLFM_RF.pretty'),antlib)

gnd = b.FindNet('GND')
removed_ground = 0
for t in list(b.GetTracks()):
    if not isinstance(t,pcb.PCB_VIA) and t.GetNetname()=='GND' and t.GetLayer()==pcb.B_Cu:
        b.RemoveNative(t); removed_ground+=1
changes=[]
def track(a,z,net,width=.3):
    t=pcb.PCB_TRACK(b); t.SetStart(a); t.SetEnd(z); t.SetLayer(pcb.B_Cu); t.SetWidth(mm(width)); t.SetNet(net); b.Add(t)
for old in source_fp:
    ref=old.GetReference()
    if ref.startswith('U$'):
        setpath(old,ref); setid(old,'Patch_10p5GHz_9.538x7.636mm')
        continue
    if not ref.startswith('J'):
        old.SetBoardOnly(True)
        continue
    center=old.GetPosition()
    sig=next(p for p in old.Pads() if p.GetNumber()=='1')
    sigpos=vec(*xy(sig.GetPosition())); net=sig.GetNet()
    new=PLUGIN.FootprintLoad(str(OUT/'PLFM_RF.pretty'),FP)
    b.Add(new)
    new.SetReference(ref); new.SetValue('818000368'); setid(new,FP); setpath(new,ref)
    for key,value in {'ArrayPosition':old.GetValue(),'Manufacturer':'ECT','MPN':'818000368','MaterialCode':'YC.DZ.SS00008','Datasheet':'${KIPRJMOD}/datasheets/ECT_818000368_SPEC_E.pdf'}.items():
        new.SetField(key,value); new.GetField(key).SetVisible(False)
    new.SetPosition(center)
    new.Flip(center,pcb.FLIP_DIRECTION_TOP_BOTTOM)
    new.Reference().SetPosition(center+vec(0,2.5)); size_text(new.Reference())
    new.Value().SetVisible(False)
    for p in new.Pads(): p.SetNet(net if p.GetNumber()=='1' else gnd)
    new_sig=next(p for p in new.Pads() if p.GetNumber()=='1')
    count=0
    for t in b.GetTracks():
        if isinstance(t,pcb.PCB_VIA) or t.GetLayer()!=pcb.B_Cu or t.GetNetname()!=net.GetNetname(): continue
        if t.GetStart()==sigpos: t.SetStart(new_sig.GetPosition()); count+=1
        if t.GetEnd()==sigpos: t.SetEnd(new_sig.GetPosition()); count+=1
    assert count==1,(ref,count)
    assert abs(xy(new_sig.GetPosition())[1]-(xy(center)[1]-1.525))<1e-6
    for p in new.Pads():
        if p.GetNumber()=='1':continue
        sgn=-1 if p.GetPosition().x<center.x else 1
        vp=center+vec(sgn*2.5,-1.0)
        v=pcb.PCB_VIA(b);v.SetPosition(vp);v.SetWidth(mm(.6));v.SetDrill(mm(.3));v.SetLayerPair(pcb.F_Cu,pcb.B_Cu);v.SetNet(gnd);b.Add(v)
        track(p.GetPosition(),vp,gnd)
    changes.append({'ref':ref,'array_position':old.GetValue(),'center_mm':xy(center),'signal_net':net.GetNetname(),'old_signal_mm':xy(sigpos),'new_signal_mm':xy(new_sig.GetPosition()),'side':'B.Cu','new_ground_vias':2})
    b.RemoveNative(old)
b.BuildConnectivity()
assert b.GetCopperLayerCount()==4
assert len(changes)==16
assert sum(1 for t in b.GetTracks() if isinstance(t,pcb.PCB_VIA))==60
# Place the complete imported design inside the A4 page.
page_offset=vec(113.5,135)
for items in [list(b.GetFootprints()),list(b.GetTracks()),list(b.Zones()),list(b.GetDrawings())]:
    for item in items:item.Move(page_offset)
ds=b.GetDesignSettings()
ds.SetAuxOrigin(ds.GetAuxOrigin()+page_offset)
ds.SetGridOrigin(ds.GetGridOrigin()+page_offset)
b.GetDesignSettings().SetBoardThickness(mm(1.0))
assert pcb.SaveBoard(str(OUT/f'{NAME}.kicad_pcb'),b)
proj=json.loads(SOURCE.with_suffix('.kicad_pro').read_text(encoding='utf-8'))
proj['meta']['filename']=NAME+'.kicad_pro'
(OUT/f'{NAME}.kicad_pro').write_text(json.dumps(proj,indent=2),encoding='utf-8')
audit={'tool':pcb.GetBuildVersion(),'source_board':str(SOURCE),'source_board_sha256':sha(SOURCE),
       'source_schematic':str(BASE/'Phased_Array_Ant.sch'),'source_schematic_sha256':sha(BASE/'Phased_Array_Ant.sch'),
       'datasheet':str(PDF),'datasheet_sha256':sha(PDF),'basis':'4L Via03',
       'pin_convention':{'1':'SIG','2':'GND','3':'GND'},'removed_old_ground_tracks':removed_ground,
       'added_ground_vias':32,'added_ground_tracks':32,'modified_bottom_signal_tracks':16,
       'source_tracks_and_vias':before,'changes':sorted(changes,key=lambda x:int(x['ref'][1:])),
       'source_files_unchanged':True,'root_uuid':rootid,'symbol_uuids':uuids,
       'board_offset_mm':[113.5,135],
       'changes_coordinate_frame':'original Eagle-derived coordinates; add board_offset_mm for current PCB coordinates'}
(OUT/'verification/build_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
if Path(__file__).resolve() != (OUT/'verification/build_ipex.py').resolve():
    shutil.copy2(__file__,OUT/'verification/build_ipex.py')
from review_fixes import apply as apply_review_fixes
apply_review_fixes(OUT)
print(json.dumps({'output':str(OUT),'connectors':len(changes),'removed_ground_tracks':removed_ground,'new_ground_vias':32,'pads':len(list(b.GetPads())),'tracks_and_vias':len(list(b.GetTracks()))},indent=2))

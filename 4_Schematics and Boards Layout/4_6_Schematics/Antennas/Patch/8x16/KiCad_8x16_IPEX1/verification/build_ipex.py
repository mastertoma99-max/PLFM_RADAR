"""Build the 8x16 IPEX variant from the preserved KiCad import, using KiCad Python.
Rebuilding overwrites this output only; close its editors and back up edits first.
"""
from pathlib import Path
import hashlib
import json
import math
import re
import shutil
import uuid
import pcbnew as pcb
import wx

APP = wx.App(False)
OUT = Path(__file__).resolve().parents[1]
BASE = OUT.parent / 'KiCad_8x16'
SOURCE_NAME = 'Patch_Anetnna_16_8'
NAME = SOURCE_NAME + '_IPEX1'
EXISTING = OUT.parent.parent / '4x4/Phased_Array_Ant_IPEX1'
LIB = 'PLFM_RF'
FP = 'ECT_818000368_IPEX1_1.25mm'
SOURCE = BASE / (SOURCE_NAME + '.kicad_pcb')
PLUGIN = pcb.PCB_IO_MGR.FindPlugin(pcb.PCB_IO_MGR.KICAD_SEXP)
uid = lambda key: str(uuid.uuid5(uuid.NAMESPACE_URL, 'PLFM_RADAR/8x16/IPEX1/' + key))
q = lambda s: json.dumps(str(s), ensure_ascii=False)
mm = pcb.FromMM
vec = lambda x, y: pcb.VECTOR2I(mm(x), mm(y))
xy = lambda v: [round(pcb.ToMM(v.x), 6), round(pcb.ToMM(v.y), 6)]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
for name in ['verification', 'preview', 'datasheets', 'PLFM_RF.pretty']:
    (OUT / name).mkdir(exist_ok=True)
shutil.copy2(EXISTING / 'PLFM_RF.pretty' / (FP + '.kicad_mod'), OUT / 'PLFM_RF.pretty' / (FP + '.kicad_mod'))
shutil.copy2(EXISTING / 'PLFM_RF.kicad_sym', OUT / 'PLFM_RF.kicad_sym')
shutil.copy2(EXISTING / 'datasheets/ECT_818000368_SPEC_E.pdf', OUT / 'datasheets/ECT_818000368_SPEC_E.pdf')
(OUT / 'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "PLFM_RF")(type "KiCad")(uri "${KIPRJMOD}/PLFM_RF.kicad_sym")(options "")(descr "Local RF symbols")))\n', encoding='utf-8')
(OUT / 'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "PLFM_RF")(type "KiCad")(uri "${KIPRJMOD}/PLFM_RF.pretty")(options "")(descr "Local RF footprints")))\n', encoding='utf-8')

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
            stack[-1].append(token)
    assert len(stack) == 1
    return stack[0][0]

def emit(node):
    return '(' + ' '.join(emit(v) if isinstance(v, list) else v for v in node) + ')'

lib = parse((OUT / 'PLFM_RF.kicad_sym').read_text(encoding='utf-8'))
symbol = next(s for s in lib if isinstance(s, list) and s[:2] == ['symbol', '"ECT_818000368"'])
symbol[1] = '"PLFM_RF:ECT_818000368"'
rootid = uid('sheet')
board = pcb.LoadBoard(str(SOURCE))
connectors = sorted((f for f in board.GetFootprints() if f.GetReference().startswith('J')), key=lambda f: f.GetPosition().x)
assert len(connectors) == 16
gnd = board.FindNet('GND')
changes = []
existing_holes = [(v.GetPosition(), v.GetDrillValue()) for v in board.GetTracks() if isinstance(v, pcb.PCB_VIA)]
existing_holes += [(p.GetPosition(), p.GetDrillSize().x) for f in board.GetFootprints() if not f.GetReference().startswith('J') for p in f.Pads() if p.GetDrillSize().x]

def track(start, end, net, width, key):
    t = pcb.PCB_TRACK(board)
    t.SetStart(start)
    t.SetEnd(end)
    t.SetLayer(pcb.F_Cu)
    t.SetWidth(mm(width))
    t.SetNet(net)
    board.Add(t)
    return t

def safe_via_position(center, side):
    # Keep each added 0.4 mm drill at least 0.30 mm from all existing drills.
    for ox in (2.8, 3.3, 3.8):
        for oy in (0, 0.6, -0.6, 1.2, -1.2):
            pos = center + vec(side * ox, oy)
            if all(math.hypot(pos.x - p.x, pos.y - p.y) >= (d + mm(0.4)) / 2 + mm(0.30) for p, d in existing_holes):
                existing_holes.append((pos, mm(0.4)))
                return pos
    raise AssertionError('No clear local GND via position')

for column, old in enumerate(connectors, 1):
    ref = old.GetReference()
    center = old.GetPosition()
    sig = next(p for p in old.Pads() if p.GetNumber() == '1')
    net = sig.GetNet()
    assert old.GetLayer() == pcb.F_Cu and net.GetNetname()
    new = PLUGIN.FootprintLoad(str(OUT / 'PLFM_RF.pretty'), FP)
    board.Add(new)
    new.SetReference(ref)
    new.SetValue('818000368')
    new.SetPosition(center)
    new.SetOrientationDegrees(180)
    new.SetFPID(pcb.LIB_ID(LIB, FP))
    new.SetPath(pcb.KIID_PATH('/' + rootid + '/' + uid('symbol-' + ref)))
    fields = {'Manufacturer': 'ECT', 'MPN': '818000368', 'MaterialCode': 'YC.DZ.SS00008', 'ArrayColumn': str(column), 'Datasheet': '${KIPRJMOD}/datasheets/ECT_818000368_SPEC_E.pdf'}
    for key, value in fields.items():
        new.SetField(key, value)
        new.GetField(key).SetVisible(False)
    new.Reference().SetPosition(center + vec(0, 3.0))
    new.Reference().SetTextAngle(pcb.EDA_ANGLE(0, pcb.DEGREES_T))
    new.Reference().SetTextSize(vec(0.8, 0.8))
    new.Reference().SetTextThickness(mm(0.12))
    new.Value().SetVisible(False)
    for pad in new.Pads():
        pad.SetNet(net if pad.GetNumber() == '1' else gnd)
    new_sig = next(p for p in new.Pads() if p.GetNumber() == '1')
    assert xy(new_sig.GetPosition() - center) == [0, -1.525]
    feeds = [t for t in board.GetTracks() if not isinstance(t, pcb.PCB_VIA) and t.GetNetname() == net.GetNetname() and t.GetLayer() == pcb.F_Cu and abs(t.GetStart().y - center.y) < mm(0.2)]
    assert len(feeds) == 1, (ref, len(feeds))
    feed = feeds[0]
    old_start = xy(feed.GetStart())
    join = pcb.VECTOR2I(feed.GetStart().x, center.y - mm(3.0))
    feed.SetStart(join)
    track(join, new_sig.GetPosition(), net, 1.0, ref + '-feed-adapter')
    added_vias = []
    for pad in new.Pads():
        if pad.GetNumber() == '1':
            continue
        side = -1 if pad.GetPosition().x < center.x else 1
        via_pos = safe_via_position(center, side)
        via = pcb.PCB_VIA(board)
        via.SetPosition(via_pos)
        via.SetWidth(mm(0.8))
        via.SetDrill(mm(0.4))
        via.SetLayerPair(pcb.F_Cu, pcb.B_Cu)
        via.SetNet(gnd)
        board.Add(via)
        track(pad.GetPosition(), via_pos, gnd, 0.4, ref + '-gnd-track-' + pad.GetNumber())
        added_vias.append({'pad': pad.GetNumber(), 'xy_mm': xy(via_pos), 'uuid': via.m_Uuid.AsString()})
    changes.append({'ref': ref, 'column': column, 'center_mm': xy(center), 'signal_net': net.GetNetname(), 'old_feed_start_mm': old_start, 'new_feed_start_mm': xy(join), 'signal_pad_mm': xy(new_sig.GetPosition()), 'ground_vias': added_vias})
    board.RemoveNative(old)

for fp in board.GetFootprints():
    if not fp.GetReference().startswith('J'):
        fp.SetBoardOnly(True)
board.BuildConnectivity()
title = board.GetTitleBlock()
title.SetTitle('8 x 16 Patch Antenna - IPEX1')
title.SetRevision('IPEX1-A1')
title.SetDate('2026-09-20')
assert pcb.SaveBoard(str(OUT / (NAME + '.kicad_pcb')), board)

def prop(key, value, x=0, y=0, hide=True):
    return f'(property {q(key)} {q(value)} (at {x:g} {y:g} 0) (effects (font (size 1.1 1.1)){" hide" if hide else ""}))'

sch = [f'(kicad_sch (version 20250114) (generator "eeschema") (uuid "{rootid}") (paper "A3") (title_block (title "8 x 16 Patch Antenna - IPEX1") (date "2026-09-20") (rev "IPEX1-A1") (comment 1 "ECT 818000368 / YC.DZ.SS00008 / 16 channels, 8 patches per channel")) (lib_symbols {emit(symbol)})']
def wire(x1, y1, x2, y2, key):
    sch.append(f'(wire (pts (xy {x1:g} {y1:g}) (xy {x2:g} {y2:g})) (stroke (width 0) (type default)) (uuid "{uid(key)}"))')
def label(net, x, y, key):
    sch.append(f'(global_label {q(net)} (shape bidirectional) (at {x:g} {y:g} 0) (effects (font (size 1.1 1.1)) (justify left)) (uuid "{uid(key)}"))')
for c in changes:
    i = c['column'] - 1
    x, y = 38.1 + (i % 4) * 93.98, 45.72 + (i // 4) * 53.34
    ref = c['ref']
    properties = prop('Reference', ref, x, y - 6.35, False) + prop('Value', '818000368', x, y + 17.78, False)
    properties += prop('Footprint', LIB + ':' + FP) + prop('Datasheet', '${KIPRJMOD}/datasheets/ECT_818000368_SPEC_E.pdf')
    properties += prop('Manufacturer', 'ECT') + prop('MPN', '818000368') + prop('MaterialCode', 'YC.DZ.SS00008') + prop('ArrayColumn', c['column'])
    sch.append(f'(symbol (lib_id "PLFM_RF:ECT_818000368") (at {x:g} {y:g} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid("symbol-" + ref)}") {properties} (instances (project "{NAME}" (path "/{rootid}" (reference "{ref}") (unit 1)))))')
    wire(x + 7.62, y, x + 27.94, y, ref + '-signal')
    label(c['signal_net'], x + 27.94, y, ref + '-signal-label')
    wire(x - 1.27, y + 7.62, x - 1.27, y + 11.43, ref + '-gnd2')
    wire(x + 1.27, y + 7.62, x + 1.27, y + 11.43, ref + '-gnd3')
    wire(x - 1.27, y + 11.43, x + 1.27, y + 11.43, ref + '-gnd-link')
    label('GND', x + 1.27, y + 11.43, ref + '-gnd-label')
    sch.append(f'(text "Column {c["column"]:02d} / 8 patches" (at {x - 10:g} {y - 15.24:g} 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{uid(ref + "-caption")}"))')
sch.append(f'''(text "SIG labels refer to the 16 existing PCB feed networks; each feeds 8 printed patches.\\nAll 128 patch copper rectangles, array spacing and the 4-layer board are retained.\\nConnector specification: DC-6 GHz. Operation of the 10.5 GHz antenna with this interface is unverified."
 (at 25.4 258 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{uid("notes")}")) (sheet_instances (path "/" (page "1"))))''')
(OUT / (NAME + '.kicad_sch')).write_text('\n'.join(sch), encoding='utf-8')
project = json.loads((BASE / (SOURCE_NAME + '.kicad_pro')).read_text(encoding='utf-8'))
project['meta']['filename'] = NAME + '.kicad_pro'
project['schematic']['top_level_sheets'] = [{'filename': NAME + '.kicad_sch', 'name': '', 'uuid': rootid}]
project['schematic']['page_layout_descr_file'] = ''
project['sheets'] = [[rootid, '']]
project['text_variables'] = {'CONNECTOR_MPN': '818000368', 'MATERIAL_CODE': 'YC.DZ.SS00008', 'FAB_STACKUP': 'TBD - inherited importer thickness is not a fabrication specification'}
(OUT / (NAME + '.kicad_pro')).write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / (NAME + '.kicad_dru')).write_text('(version 1)\n', encoding='utf-8')
audit = {'source_board': str(SOURCE), 'source_schematic': str(BASE / (SOURCE_NAME + '.kicad_sch')), 'source_board_sha256': sha(SOURCE), 'source_schematic_sha256': sha(BASE / (SOURCE_NAME + '.kicad_sch')), 'footprint_source': str(EXISTING / 'PLFM_RF.pretty' / (FP + '.kicad_mod')), 'footprint_sha256': sha(OUT / 'PLFM_RF.pretty' / (FP + '.kicad_mod')), 'datasheet_sha256': sha(OUT / 'datasheets/ECT_818000368_SPEC_E.pdf'), 'root_uuid': rootid, 'symbol_uuids': {c['ref']: uid('symbol-' + c['ref']) for c in changes}, 'changes': changes, 'new_ground_vias': {'count': 32, 'drill_mm': 0.4, 'diameter_mm': 0.8}, 'source_vias_retained': 95, 'connector_mounting': 'F.Cu, rotated 180 degrees, signal toward patch array', 'tool': pcb.GetBuildVersion(), 'rf_validation': 'Not performed; reused ECT 818000368 is specified to 6 GHz'}
(OUT / 'verification/build_audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'connectors': len(changes), 'original_vias': 95, 'new_vias': 32, 'output': str(OUT)}, indent=2))

from pathlib import Path
import collections, json, re, xml.etree.ElementTree as ET
import pcbnew as p
import wx
from sexpr import blocks, parse, children

app = wx.App(False)

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parent
plugin = p.PCB_IO_MGR.FindPlugin(p.PCB_IO_MGR.KICAD_SEXP)
results = []
for row in json.loads((OUT/'source_inventory.json').read_text(encoding='utf-8')):
    if row['kind'] != 'eagle': continue
    source = ROOT/row['path']
    name = source.stem
    d = OUT/'Hardware'/name
    boardpath = d/(name+'.kicad_pcb')
    board = p.PCB_IO_MGR.Load(p.PCB_IO_MGR.KICAD_SEXP, str(boardpath), p.BOARD())
    srcboard = ET.parse(source.with_suffix('.brd'))
    elems = {e.attrib['name']: e.attrib for e in srcboard.findall('./drawing/board/elements/element')}
    # Distinguish identically named packages from different EAGLE libraries.
    packages = collections.defaultdict(set)
    for e in elems.values(): packages[e['package']].add(e['library'])
    norm = lambda r: ('UNK22V0' if r=='22V' and name=='RF_PA' else (r+'0' if name=='RADAR_Main_Board' and re.fullmatch(r'ADAR[1-4]_',r) else r))
    libdir = d/(name+'.pretty'); libdir.mkdir(exist_ok=True)
    ref_fp, exported = {}, set()
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        e = elems.get(ref)
        # The reused antenna board already has matching references.
        package = str(fp.GetFPID().GetLibItemName())
        if e:
            package = e['package'] + ('__'+e['library'] if len(packages[e['package']])>1 else '')
        package = re.sub(r'[<>:"/\\|?*]', '_', package)
        fp.SetReference(norm(ref))
        fp.SetFPID(p.LIB_ID(name, package))
        ref_fp[norm(ref)] = name+':'+package
        if package not in exported:
            plugin.FootprintSave(str(libdir), fp)
            exported.add(package)
    p.SaveBoard(str(boardpath), board)
    (d/'fp-lib-table').write_text(f'(fp_lib_table (version 7) (lib (name "{name}") (type "KiCad") (uri "${{KIPRJMOD}}/{name}.pretty") (options "") (descr "Local footprints retained from source board")))\n',encoding='utf-8')
    for sch in d.glob('*.kicad_sch'):
        text = sch.read_text(encoding='utf-8')
        for a,b,block in reversed(blocks(text,'symbol')):
            props = {x[1]:x[2] for x in children(parse(block),'property')}
            ref=props.get('Reference')
            if ref in ref_fp:
                updated=re.sub(r'(\(property "Footprint"\s+)"(?:\\.|[^"\\])*"', lambda m:m[1]+json.dumps(ref_fp[ref]),block)
                text=text[:a]+updated+text[b:]
        sch.write_text(text,encoding='utf-8')
    results.append({'project':name,'local_footprints':len(exported),'board_footprints':len(list(board.GetFootprints())),'normalized_references':{r:norm(r) for r in elems if norm(r)!=r}})
    print(results[-1],flush=True)
(OUT/'verification/local_footprint_audit.json').write_text(json.dumps(results,indent=2),encoding='utf-8')

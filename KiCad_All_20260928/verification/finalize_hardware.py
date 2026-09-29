from pathlib import Path
import json
import re
import shutil
import uuid
from sexpr import blocks, parse, child

OUT = Path(__file__).resolve().parents[1]

def backup(d):
    dest = OUT / 'verification/native_import' / d.name
    dest.mkdir(parents=True, exist_ok=True)
    for p in d.iterdir():
        if p.is_file() and p.suffix in ['.kicad_sch', '.kicad_pro'] and not (dest / p.name).exists():
            shutil.copy2(p, dest / p.name)

def flatten_single(name):
    d = OUT / 'Hardware' / name
    s = d / (name + '_1.kicad_sch')
    if not s.exists(): return
    backup(d)
    p = json.loads((d / (name + '.kicad_pro')).read_text(encoding='utf-8'))
    text = s.read_text(encoding='utf-8')
    uid = child(parse(text), 'uuid')[1]
    old = next(x['uuid'] for x in p['schematic']['top_level_sheets'] if x['filename'] == s.name)
    (d / (name + '.kicad_sch')).write_text(text.replace('/' + old, '/' + uid), encoding='utf-8')
    p['schematic']['top_level_sheets'] = [{'filename': name + '.kicad_sch', 'name': '', 'uuid': uid}]
    (d / (name + '.kicad_pro')).write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding='utf-8')
    s.unlink()

def main_hierarchy():
    name = 'RADAR_Main_Board'
    d = OUT / 'Hardware' / name
    backup(d)
    source = OUT / 'verification/native_import' / name
    p = json.loads((source / (name + '.kicad_pro')).read_text(encoding='utf-8'))
    sheets = p['schematic']['top_level_sheets']
    root_uuid = sheets[0]['uuid']
    text = f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
    (uuid "{root_uuid}") (paper "A4")
    (title_block (title "RADAR Main Board - Sheet Index") (comment 1 "Converted from EAGLE; four source sheets retained"))
    (lib_symbols)
    (text "RADAR Main Board / Four source sheets" (at 35 28 0) (effects (font (size 2.54 2.54)) (justify left)) (uuid "{uuid.uuid4()}"))
    (text "Double-click a sheet below to open its circuit." (at 35 38 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{uuid.uuid4()}"))
    '''
    for i, s in enumerate(sheets[1:]):
        x, y = 35 + (i % 2) * 120, 60 + (i // 2) * 55
        uid = s['uuid']
        page = (source / s['filename']).read_text(encoding='utf-8')
        page = page.replace('/' + uid, '/' + root_uuid + '/' + uid)
        (d / s['filename']).write_text(page, encoding='utf-8')
        text += f'''\n(sheet (at {x} {y}) (size 105 35) (fields_autoplaced yes)
          (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid "{uid}")
          (property "Sheetname" {json.dumps(s['name'])} (at {x} {y-1.27} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
          (property "Sheetfile" "{s['filename']}" (at {x} {y+36.27} 0) (effects (font (size 1.0 1.0)) (justify left top)))
          (instances (project "{name}" (path "/{root_uuid}" (page "{i+2}")))))\n'''
    text += '(sheet_instances (path "/" (page "1"))) (embedded_fonts no))\n'
    (d / (name + '.kicad_sch')).write_text(text, encoding='utf-8')
    p['schematic']['top_level_sheets'] = [sheets[0]]
    (d / (name + '.kicad_pro')).write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding='utf-8')

def fix_clock_branch():
    p = OUT / 'Hardware/Clocks_Freq_Synth_board/Clocks_Freq_Synth_board.kicad_sch'
    text = p.read_text(encoding='utf-8')
    target = '(xy 530.98 228.18) (xy 541.14 228.18)'
    for start, end, block in blocks(text, 'wire'):
        tree = parse(block)
        pts = child(tree, 'pts')[1:]
        if pts == [['xy', '530.98', '228.18'], ['xy', '541.14', '228.18']]:
            first = block.replace('(xy 541.14 228.18)', '(xy 541.02 228.18)')
            second = f'(wire (pts (xy 541.02 228.18) (xy 541.14 228.18)) (stroke (width 0) (type default)) (uuid "{uuid.uuid4()}"))'
            dot = f'(junction (at 541.02 228.18) (diameter 0) (color 0 0 0 0) (uuid "{uuid.uuid4()}"))'
            text = text[:start] + first + '\n\t' + second + '\n\t' + dot + text[end:]
            p.write_text(text, encoding='utf-8')
            return

if __name__ == '__main__':
    for name in ['PowerBoard', 'RF_PA', 'Clocks_Freq_Synth_board', 'Phased_Array_Ant']:
        flatten_single(name)
    main_hierarchy()
    fix_clock_branch()

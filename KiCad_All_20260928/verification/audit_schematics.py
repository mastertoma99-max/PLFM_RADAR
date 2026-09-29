"""Compare native KiCad netlists against EAGLE pin-to-pad connectivity."""
from pathlib import Path
import collections
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parent
CLI = r'D:\3_Software\KiCAD\bin\kicad-cli.exe'


def audit(row):
    source = ROOT / row['path']
    name = source.stem
    sch = ET.parse(source).find('./drawing/schematic')
    libs = {lib.attrib['name']: lib for lib in sch.findall('libraries/library')}
    parts = {p.attrib['name']: p for p in sch.findall('parts/part')}
    padmap, packaged = {}, set()
    for ref, part in parts.items():
        a = part.attrib
        lib = libs[a['library']]
        ds = next(d for d in lib.findall('devicesets/deviceset') if d.attrib['name'] == a['deviceset'])
        dev = next(d for d in ds.findall('devices/device') if d.attrib.get('name', '') == a.get('device', ''))
        if dev.attrib.get('package'):
            packaged.add(ref)
        for c in dev.findall('connects/connect'):
            padmap[(ref, c.attrib['gate'], c.attrib['pin'])] = c.attrib['pad'].split()
    expected = collections.defaultdict(set)
    for net in sch.findall('sheets/sheet/nets/net'):
        for pr in net.findall('segment/pinref'):
            a = pr.attrib
            for pad in padmap.get((a['part'], a['gate'], a['pin']), []):
                expected[net.attrib['name']].add((a['part'], pad))
    d = OUT / 'Hardware' / name
    xml = OUT / 'verification' / (name + '.xml')
    result = subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(xml), str(d / (name + '.kicad_sch'))], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        return {'project': name, 'load_failed': result.stdout + result.stderr}
    tree = ET.parse(xml)
    refmap = {'UNK22V0': '22V'} if name == 'RF_PA' else ({f'ADAR{i}_0': f'ADAR{i}_' for i in range(1,5)} if name == 'RADAR_Main_Board' else {})
    norm = lambda r: refmap.get(r, r)
    actual = {n.attrib['name']: {(norm(x.attrib['ref']), x.attrib['pin']) for x in n.findall('node') if norm(x.attrib['ref']) in packaged} for n in tree.findall('./nets/net')}
    expected = {k: v for k, v in expected.items() if v}
    actual = {k: v for k, v in actual.items() if v}
    ep = {pin: n for n, pins in expected.items() for pin in pins}
    ap = {pin: n for n, pins in actual.items() for pin in pins}
    splits = []
    for n, pins in expected.items():
        mapped = {ap[p] for p in pins if p in ap}
        if len(mapped) > 1:
            splits.append({'source_net': n, 'destination_nets': sorted(mapped), 'pins': sorted(pins)})
    merges = []
    for n, pins in actual.items():
        mapped = {ep[p] for p in pins if p in ep}
        if len(mapped) > 1:
            merges.append({'destination_net': n, 'source_nets': sorted(mapped), 'pins': sorted(pins)})
    actual_refs = {norm(x.attrib['ref']) for x in tree.findall('./components/comp')}
    extra_pins = set(ap) - set(ep)
    extra_joined = [{'net': net, 'pins': sorted(pins & extra_pins)} for net,pins in actual.items() if len(pins)>1 and pins & extra_pins]
    return {
        'project': name, 'source_sha256_unchanged': hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256'],
        'kicad_to_source_reference_mapping': refmap,
        'source_sheets': len(sch.findall('sheets/sheet')),
        'source_parts_including_power_symbols': len(parts),
        'source_packaged_components': len(packaged),
        'kicad_components': len(actual_refs),
        'missing_packaged_components': sorted(packaged - actual_refs),
        'source_nets_with_package_pins': len(expected), 'kicad_nets_with_package_pins': len(actual),
        'missing_connected_pins': sorted(set(ep) - set(ap)),
        'extra_connected_pins': sorted(set(ap) - set(ep)),
        'originally_unconnected_pins_joined_to_other_pins': extra_joined,
        'split_nets': splits, 'merged_nets': merges,
    }


if __name__ == '__main__':
    rows = json.loads((OUT / 'source_inventory.json').read_text(encoding='utf-8'))
    results = []
    for row in rows:
        if row['kind'] != 'eagle':
            continue
        d = OUT / 'Hardware' / Path(row['path']).stem
        if not (d / (d.name + '.kicad_sch')).exists():
            continue
        result = audit(row)
        results.append(result)
        print({k: (len(v) if isinstance(v, list) else v) for k, v in result.items()}, flush=True)
    (OUT / 'verification' / 'schematic_connectivity_audit.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    assert len(results)==6
    assert all(not r.get('load_failed') and not r['missing_packaged_components'] and not r['missing_connected_pins'] and not r['split_nets'] and not r['merged_nets'] and not r['originally_unconnected_pins_joined_to_other_pins'] for r in results)

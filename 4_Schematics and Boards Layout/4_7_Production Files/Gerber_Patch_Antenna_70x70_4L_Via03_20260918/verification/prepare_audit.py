"""Reuse the already exercised Gerber readback checks, adapted to an intentional via edit."""
from pathlib import Path

out = Path(__file__).resolve().parent.parent
base = out.parent / 'Gerber_Patch_Antenna_70x70_4L_20260918'
s = (base/'verification/audit_gerbers.py').read_text(encoding='utf8')
s = s.replace("NAME = 'Phased_Array_Ant_70x70_4L'", "NAME = 'Phased_Array_Ant_70x70_4L_Via03'\nBASE = OUT.parent / 'Gerber_Patch_Antenna_70x70_4L_20260918'\nOLDNAME = 'Phased_Array_Ant_70x70_4L'")
s = s.replace("('In2_Cu', 'g2', 'In4_Cu', 'g4')", "('In2_Cu', 'g2', 'In2_Cu', 'g2')")
start = s.index('for layer, ext, old_layer, old_ext in specs:')
end = s.index('# Validate artwork connectivity',start)
s = s[:start]+'''changes = json.loads((OUT/'verification/via_change_audit.json').read_text())['modified_vias']
allowed_change_area = unary_union([Point(v['x'],v['y']).buffer(0.65,quad_segs=128) for v in changes])
for layer, ext, old_layer, old_ext in specs:
    new = GerberFile.open(CAM / f'{NAME}-{layer}.{ext}')
    old = GerberFile.open(BASE / f'cam/{OLDNAME}-{old_layer}.{old_ext}')
    gerbers[layer] = new
    if layer.endswith('_Cu'):
        geoms[layer] = copper_geometry(new)
        difference = geoms[layer].symmetric_difference(copper_geometry(old))
        outside = difference.difference(allowed_change_area).area
        assert outside < 0.000001, (layer,outside)
        report['shape_comparison'][layer] = {
            'all_changes_within_0.65mm_of_16_modified_vias': True,
            'changed_copper_area_mm2': difference.area,
            'unexplained_change_area_mm2': outside}
    else:
        assert primitive_signature(new) == primitive_signature(old), layer
        report['shape_comparison'][layer] = {'unchanged_from_Via02':True}
    print(layer,report['shape_comparison'][layer],flush=True)
for layer,ext in [('F_Silkscreen','gto'),('B_Silkscreen','gbo'),('Edge_Cuts','gm1')]:
    assert primitive_signature(GerberFile.open(CAM/f'{NAME}-{layer}.{ext}')) == primitive_signature(GerberFile.open(BASE/f'cam/{OLDNAME}-{layer}.{ext}'))
    report['shape_comparison'][layer] = {'unchanged_from_Via02':True}

''' + s[end:]
start=s.index('mask_audit = {}')
s=s[:start]+'''via_clearances = []
for via in changes:
    disk = Point(via['x'],via['y']).buffer(0.3,quad_segs=256)
    layer_clearances = {}
    for layer in geoms:
        own = find(locate(layer,via['x'],via['y']))
        others = [p for i,p in components[layer] if find((layer,i)) != own]
        distance = min((disk.distance(p) for p in others), default=999)
        assert distance >= 0.099, (via,layer,distance)
        layer_clearances[layer] = distance
    via_clearances.append({'net':via['net'],'minimum_copper_clearance_mm':min(layer_clearances.values()),'by_layer':layer_clearances})
report['enlarged_via_clearance'] = {'required_mm':0.1,'minimum_measured_mm':min(v['minimum_copper_clearance_mm'] for v in via_clearances),'all_16_vias':via_clearances}

''' + s[start:]
s=s.replace("{('PTH', 0.2): 16, ('PTH', 0.3): 12, ('NPTH', 3.2): 4}","{('PTH', 0.3): 28, ('NPTH', 3.2): 4}")
s=s.replace("'PTH_0.2mm': 16, 'PTH_0.3mm': 12", "'PTH_0.2mm': 0, 'PTH_0.3mm': 28")
start=s.index("for suffix in ('4L', '6L'):")
end=s.index('# Render actual Gerber files',start)
s=s[:start]+'''for suffix in ('Via03','Via02_reference'):
    drc = json.loads((OUT / f'verification/drc_{suffix}.json').read_text(encoding='utf8'))
    report[f'drc_{suffix}'] = {'violations_by_type': dict(collections.Counter(v['type'] for v in drc['violations'])),
                              'unconnected_reports': len(drc['unconnected_items'])}
assert set(report['drc_Via03']['violations_by_type']) <= {'solder_mask_bridge'}
assert report['drc_Via03']['unconnected_reports'] == report['drc_Via02_reference']['unconnected_reports']
report['drc_interpretation'] = ('The 16 drill-size violations are eliminated. No copper short, copper clearance, or annular-ring violations. '
    'Imported connector mask/ground-graphic reports remain; physical Gerber connectivity and mask checks above independently verified. '
    'No RF-performance equivalence is asserted.')

''' + s[end:]
s=s.replace('70 x 70 mm antenna PCB | 4-layer Gerber artwork', '70 x 70 mm antenna PCB | 4 layers | 0.3 mm via holes')
(out/'verification/audit_gerbers.py').write_text(s,encoding='utf8')
print('Prepared via-revision Gerber readback audit')

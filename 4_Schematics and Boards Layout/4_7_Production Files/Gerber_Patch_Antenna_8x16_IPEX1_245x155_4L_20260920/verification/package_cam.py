"""Package flat fabrication files, re-extract, and independently parse delivered data."""
from pathlib import Path
import collections, hashlib, json, shutil, sys, zipfile
OUT=Path(__file__).resolve().parents[1]
ROOT=next(p for p in OUT.parents if (p/'.git').exists())
sys.path.insert(0,str(ROOT/'5_Simulations/generated/antenna_4L_cam_tools'))
from gerbonara import GerberFile, ExcellonFile
from gerbonara.ipc356 import Netlist
NAME='Patch_Anetnna_16_8_IPEX1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
audit=json.loads((OUT/'verification/gerber_readback_audit.json').read_text())
manifest=json.loads((OUT/'verification/export_manifest.json').read_text())
assert audit['physical_connectivity']['all_17_nets_connected'] and audit['physical_connectivity']['shorts_between_nets']==0
assert audit['kicad_checks']['DRC_errors']==0 and not audit['kicad_checks']['DRC_ignored_checks']
assert audit['source_hashes_still_match']
for rel,digest in manifest['source_hashes'].items():assert sha(Path(manifest['source_project'])/rel)==digest
assert sha(OUT/'source'/f'{NAME}.kicad_pcb')==manifest['exported_board_sha256']
requirements={
    'revision':'IPEX1-A1-CAM-20260920','status':'CAM geometry exported and checked; manufacturing parameters pending confirmation before fabrication',
    'board_size_mm':[245,155],'copper_layers':4,'layer_order':['F.Cu','In1.Cu','In2.Cu','B.Cu'],
    'layer_use':{'F.Cu':'128 antenna patches, feeds, 16 top-side IPEX connectors','In1.Cu':'GND plane','In2.Cu':'plated-via annuli only; no plane','B.Cu':'plated-via annuli only; no plane'},
    'material':None,'material_grade':None,'finished_board_thickness_mm':None,'outer_copper_oz':None,'inner_copper_oz':None,'surface_finish':None,
    'dielectric_thicknesses_mm':None,'dielectric_properties':None,'soldermask_color':None,'impedance_requirement':None,'fabrication_tolerances':None,
    'null_means':'TBD; never infer from CAD defaults or the separate 70x70 mm antenna project',
    'origin':'board lower-left (0,0); unmirrored top-view coordinates for every layer',
    'pth':[{'drill_mm':.4,'count':32},{'drill_mm':.6,'count':92}],
    'npth':[{'drill_mm':3.2,'count':4,'centers_mm':[[4,4],[4,151],[241,4],[241,151]]}],
    'exact_duplicate_drill_commands_removed':3,'source_via_objects':127,'unique_plated_holes':124,
    'minimum_nominal_annular_ring_mm':.15,'minimum_track_width_mm':.4,'measured_minimum_different_net_copper_clearance_mm':.45,
    'mask':'Original near-full-board top opening retained; bottom via annuli tented according to Gerbers',
    'silkscreen':'Both sides have zero effective printed area after soldermask subtraction',
    'ipc356':{'electrical_nodes':172,'nets':17,'mechanical_hole_records':4},
    'scope':'Bare PCB only; assembly BOM, paste stencil and pick/place data not included',
    'RF_validation':'Not performed. Connector specification DC-6GHz does not qualify operation at 10.5GHz.'
}
reqpath=OUT/'fabrication_requirements.json'
reqpath.write_text(json.dumps(requirements,ensure_ascii=False,indent=2),encoding='utf8')
shutil.copy2(reqpath,OUT/'source/fabrication_requirements.json')
(OUT/'verification/drill_report_final.txt').write_text('Final delivered drill files\nPTH T1: 0.400 mm x 32\nPTH T2: 0.600 mm x 92\nTotal unique PTH: 124\nNPTH: 3.200 mm x 4\nTotal unique drilled holes: 128\nThree identical duplicate PTH commands removed. See gerber_readback_audit.json.\nOriginal KiCad drill_report.txt describes the unnormalized 127-PTH-object export.\n',encoding='utf8')
job=json.loads((OUT/'cam'/f'{NAME}-job.gbrjob').read_text())
assert job['GeneralSpecs']['LayerNumber']==4 and job['GeneralSpecs']['Size']=={'X':245.0,'Y':155.0}
assert 'BoardThickness' not in job['GeneralSpecs'] and 'Finish' not in job['GeneralSpecs'] and 'MaterialStackup' not in job
files=sorted((OUT/'cam').iterdir())+[OUT/'README_制造说明.txt',reqpath]
assert len(files)==15 and all(f.is_file() for f in files),[f.name for f in files]
checks=OUT/'SHA256SUMS.txt';checks.write_text(''.join(sha(f)+'  '+f.name+'\n' for f in files),encoding='utf8');files.append(checks)
archive=OUT/'Patch_Antenna_8x16_IPEX1_245x155_4L_Gerber_20260920.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in files:z.write(f,f.name)
extracted=OUT/'verification/zip_readback';extracted.mkdir(exist_ok=True)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and len(z.namelist())==16
    assert set(z.namelist())=={f.name for f in files}
    for f in files:
        data=z.read(f.name);assert hashlib.sha256(data).hexdigest()==sha(f)
        (extracted/f.name).write_bytes(data)
for f in files:assert sha(extracted/f.name)==sha(f)
for f in extracted.iterdir():
    if f.suffix in ['.gtl','.g1','.g2','.gbl','.gts','.gbs','.gto','.gbo','.gm1']:GerberFile.open(f)
drill_counts=collections.Counter()
for kind in ['PTH','NPTH']:
    d=ExcellonFile.open(extracted/f'{NAME}-{kind}.drl')
    drill_counts.update((kind,round(o.aperture.diameter,6)) for o in d.objects)
assert drill_counts=={('PTH',.4):32,('PTH',.6):92,('NPTH',3.2):4}
assert len(Netlist.open(extracted/f'{NAME}.d356').test_records)==176
report={'archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),'files':{f.name:sha(f) for f in files},
    'zip_crc_and_all_file_hashes_verified':True,'extracted_gerber_drill_and_ipc_files_parse_successfully':True,
    'source_board_sha256':manifest['source_hashes'][NAME+'.kicad_pcb'],'exported_board_sha256':manifest['exported_board_sha256'],
    'physical_geometry_unchanged':manifest['physical_geometry_unchanged'],'manufacturing_parameters_pending':True}
(OUT/'verification/package_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False,indent=2))

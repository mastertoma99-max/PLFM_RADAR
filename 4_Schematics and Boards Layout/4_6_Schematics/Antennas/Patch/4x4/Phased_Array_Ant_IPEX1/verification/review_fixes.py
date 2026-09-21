"""Apply review fixes without changing copper, routes, drills or component positions.

Use KiCad Python. Called by build_ipex.py as the final post-processing step.
"""
from pathlib import Path
import collections, hashlib, json, shutil
import pcbnew as p

NAME='Phased_Array_Ant_IPEX1'
ANT='Patch_10p5GHz_9.538x7.636mm'
HOLE='MountingHole_NPTH_3.2mm'
mm=p.FromMM
vec=lambda x,y:p.VECTOR2I(mm(x),mm(y))
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
FAB_VARS={'FAB_MATERIAL':'FR4','FAB_FINISHED_THICKNESS_MM':'1.0','FAB_OUTER_COPPER_OZ':'1','FAB_INNER_COPPER_OZ':'0.5','FAB_FINISH':'OSP','FAB_LAYER_ORDER':'F.Cu / In1.Cu GND / In2.Cu GND / B.Cu','FAB_DIELECTRIC_THICKNESS':'TBD - fabricator to propose'}

def rect(fp,x,y):
    if any(g.GetLayer()==p.F_CrtYd for g in fp.GraphicalItems()): return
    g=p.PCB_SHAPE(fp)
    g.SetShape(p.SHAPE_T_RECT); g.SetLayer(p.F_CrtYd); g.SetWidth(mm(.05)); g.SetFilled(False)
    center=fp.GetPosition(); g.SetStart(center+vec(-x,-y)); g.SetEnd(center+vec(x,y)); fp.Add(g)

def circle(fp,r,layer):
    if any(g.GetLayer()==layer for g in fp.GraphicalItems()): return
    g=p.PCB_SHAPE(fp)
    g.SetShape(p.SHAPE_T_CIRCLE); g.SetLayer(layer); g.SetWidth(mm(.05)); g.SetFilled(False)
    center=fp.GetPosition(); g.SetStart(center); g.SetEnd(center+vec(r,0)); fp.Add(g)

def update_antenna(fp):
    for pad in fp.Pads():
        layers=pad.GetLayerSet(); layers.RemoveLayer(p.F_Paste); layers.RemoveLayer(p.B_Paste); pad.SetLayerSet(layers)
    # CAD overlap boundary, not an RF keepout or a guaranteed electromagnetic clearance.
    rect(fp,5.019,4.068)

def apply(out):
    out=Path(out); pcb=out/f'{NAME}.kicad_pcb'; pro=out/f'{NAME}.kicad_pro'
    backup=out/'verification/full_review_20260920/before_fixes'
    backup.mkdir(parents=True,exist_ok=True)
    originals=[pcb,pro,out/'PLFM_RF.pretty'/f'{ANT}.kicad_mod']
    for f in originals:
        dest=backup/f.relative_to(out)
        if not dest.exists(): dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(f,dest)
    b=p.LoadBoard(str(pcb))
    antennas=[f for f in b.GetFootprints() if f.GetReference().startswith('U$')]
    holes=[f for f in b.GetFootprints() if f.GetReference().startswith('UNK_HOLE')]
    assert len(antennas)==16 and len(holes)==4 and b.GetCopperLayerCount()==4
    for f in antennas: update_antenna(f)
    for f in holes:
        assert len(list(f.Pads()))==1
        assert p.ToMM(next(iter(f.Pads())).GetDrillSize().x)==3.2
        circle(f,1.85,p.F_CrtYd); circle(f,1.85,p.B_CrtYd)
        f.SetFPID(p.LIB_ID('PLFM_RF',HOLE))
    zones=list(b.Zones()); assert len(zones)==2
    for z in zones:
        assert z.GetNetname()=='GND' and z.GetLayer() in [p.In1_Cu,p.In2_Cu]
        z.SetZoneName('L2_GND' if z.GetLayer()==p.In1_Cu else 'L3_GND')
        z.SetPadConnection(p.ZONE_CONNECTION_FULL)
    plot=b.GetPlotOptions()
    layers=p.LSET()
    for l in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu,p.F_Mask,p.B_Mask,p.F_SilkS,p.B_SilkS,p.Edge_Cuts]: layers.AddLayer(l)
    plot.SetLayerSelection(layers); plot.SetFormat(p.PLOT_FORMAT_GERBER)
    plot.SetUseAuxOrigin(True); plot.SetUseGerberProtelExtensions(True)
    plot.SetUseGerberAttributes(True); plot.SetUseGerberX2format(True)
    plot.SetIncludeGerberNetlistInfo(True); plot.SetCreateGerberJobFile(True)
    plot.SetSubtractMaskFromSilk(True); plot.SetMirror(False); plot.SetNegative(False)
    plot.SetPlotFrameRef(False); plot.SetScale(1.0); plot.SetDrillMarksType(p.DRILL_MARKS_NO_DRILL_SHAPE)
    b.SetPlotOptions(plot)
    title=b.GetTitleBlock()
    title.SetTitle('4 x 4 Phased Array - IPEX1'); title.SetRevision('IPEX1-A2'); title.SetDate('2026-09-20')
    title.SetComment(0,'4L: F.Cu / In1.Cu GND / In2.Cu GND / B.Cu')
    title.SetComment(1,'FR4 1.0 mm; outer 1 oz; inner 0.5 oz; OSP')
    title.SetComment(2,'60 PTH 0.30 mm; 4 NPTH 3.20 mm; 70 x 70 mm')
    title.SetComment(3,'Dielectric thickness / FR4 grade: fabricator proposal required')
    b.SetTitleBlock(title)
    b.GetDesignSettings().SetBoardThickness(mm(1))
    assert p.SaveBoard(str(pcb),b)
    plugin=p.PCB_IO_MGR.FindPlugin(p.PCB_IO_MGR.KICAD_SEXP)
    ant=p.FootprintLoad(str(out/'PLFM_RF.pretty'),ANT)
    update_antenna(ant); plugin.FootprintSave(str(out/'PLFM_RF.pretty'),ant)
    hole=p.FOOTPRINT(holes[0]); hole.SetPosition(vec(0,0)); hole.SetReference('REF**'); hole.SetPath(p.KIID_PATH())
    plugin.FootprintSave(str(out/'PLFM_RF.pretty'),hole)
    data=json.loads(pro.read_text(encoding='utf8'))
    data.setdefault('text_variables',{}).update(FAB_VARS)
    severities=data['board']['design_settings']['rule_severities']
    previously_ignored=[k for k,v in severities.items() if v=='ignore']
    for k in previously_ignored: severities[k]='warning'
    pro.write_text(json.dumps(data,indent=2),encoding='utf8')
    result={'revision':'IPEX1-A2','changes':['Removed paste from 16 printed antenna pads and their library footprint','Added CAD courtyard bounds for 16 antenna features and 4 NPTH features','Added reusable local NPTH footprint','Named both GND zones and explicitly selected solid connection','Persisted production plot layers, auxiliary origin, X2, no mirror/frame/drill marks and mask subtraction','Recorded confirmed fabrication requirements in project text variables and board title block','Enabled all previously ignored PCB DRC rules'],'newly_enabled_DRC_rules':previously_ignored,'courtyard_note':'Antenna: copper extent + 0.25 mm. Hole: radius 1.85 mm = hole radius + 0.25 mm, both sides. These are CAD overlap bounds, not RF spacing or screw-head clearance specifications.','before_file_hashes':{str(f.relative_to(out)):sha(backup/f.relative_to(out)) for f in originals},'after_file_hashes':{str(f.relative_to(out)):sha(f) for f in originals}}
    (out/'verification/full_review_20260920/applied_fixes.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result

if __name__=='__main__': print(json.dumps(apply(Path(__file__).resolve().parent.parent),indent=2))

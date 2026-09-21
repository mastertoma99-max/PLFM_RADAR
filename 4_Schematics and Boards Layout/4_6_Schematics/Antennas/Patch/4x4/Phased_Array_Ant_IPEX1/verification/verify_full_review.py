"""Read-only verification of A2 source geometry, library/paste, grounding and export setup."""
from pathlib import Path
import collections, hashlib, json
import pcbnew as p
OUT=Path(__file__).resolve().parent.parent
NAME='Phased_Array_Ant_IPEX1'
ROOT=next(x for x in OUT.parents if (x/'.git').exists())
CAM=ROOT/'4_Schematics and Boards Layout/4_7_Production Files/Gerber_Patch_Antenna_IPEX1_70x70_4L_Via03_20260920_R2'
reportdir=OUT/'verification/full_review_20260920'
b=p.LoadBoard(str(OUT/f'{NAME}.kicad_pcb'))
before=p.LoadBoard(str(reportdir/'before_fixes'/f'{NAME}.kicad_pcb'))
xy=lambda v:[v.x,v.y]
def tracks(board):
    return sorted((t.m_Uuid.AsString(),t.GetNetname(),t.GetLayer(),xy(t.GetStart()),xy(t.GetEnd()),t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,p.PCB_VIA) else 0) for t in board.GetTracks())
def pad_data(board):
    rows=[]
    for f in board.GetFootprints():
        for pad in f.Pads():
            layers=pad.GetLayerSet()
            if f.GetReference().startswith('U$'): layers.RemoveLayer(p.F_Paste)
            rows.append((f.GetReference(),pad.GetNumber(),pad.GetNetname(),xy(pad.GetPosition()),xy(pad.GetSize()),xy(pad.GetDrillSize()),pad.GetShape(),pad.GetOrientationDegrees(),layers.FmtBin(),pad.GetLocalSolderMaskMargin()))
    return sorted(rows)
def centers(board):
    return sorted((f.GetReference(),xy(f.GetPosition()),f.GetOrientationDegrees(),f.GetLayer()) for f in board.GetFootprints())
assert tracks(before)==tracks(b) and pad_data(before)==pad_data(b) and centers(before)==centers(b)
assert b.GetCopperLayerCount()==4 and p.ToMM(b.GetDesignSettings().GetBoardThickness())==1
assert [b.GetLayerName(l) for l in b.GetEnabledLayers().CuStack()]==['F.Cu','In1.Cu','In2.Cu','B.Cu']
zones=list(b.Zones()); assert len(zones)==2
assert {(z.GetZoneName(),z.GetLayer(),z.GetNetname(),z.GetPadConnection()) for z in zones}=={('L2_GND',p.In1_Cu,'GND',p.ZONE_CONNECTION_FULL),('L3_GND',p.In2_Cu,'GND',p.ZONE_CONNECTION_FULL)}
vias=[t for t in b.GetTracks() if isinstance(t,p.PCB_VIA)]
assert len(vias)==60 and all(v.TopLayer()==p.F_Cu and v.BottomLayer()==p.B_Cu and p.ToMM(v.GetDrillValue())==.3 for v in vias)
ground=[v for v in vias if v.GetNetname()=='GND']; assert len(ground)==44
for f in b.GetFootprints():
    if f.GetReference().startswith('J'):
        for x in [-2.5,2.5]:
            expected=f.GetPosition()+p.VECTOR2I(p.FromMM(x),p.FromMM(-1))
            assert sum(v.GetPosition()==expected for v in ground)==1
    if f.GetReference().startswith('U$'):
        assert all(not pad.GetLayerSet().Contains(p.F_Paste) for pad in f.Pads())
    assert any(g.GetLayer() in [p.F_CrtYd,p.B_CrtYd] for g in f.GraphicalItems()),f.GetReference()
lib=p.FootprintLoad(str(OUT/'PLFM_RF.pretty'),'Patch_10p5GHz_9.538x7.636mm')
assert all(not pad.GetLayerSet().Contains(p.F_Paste) for pad in lib.Pads())
plot=b.GetPlotOptions()
assert set(plot.GetLayerSelection().Seq())=={p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu,p.F_Mask,p.B_Mask,p.F_SilkS,p.B_SilkS,p.Edge_Cuts}
assert plot.GetUseAuxOrigin() and plot.GetUseGerberProtelExtensions() and plot.GetSubtractMaskFromSilk()
assert not plot.GetMirror() and not plot.GetPlotFrameRef() and plot.GetDrillMarksType()==p.DRILL_MARKS_NO_DRILL_SHAPE
pro=json.loads((OUT/f'{NAME}.kicad_pro').read_text(encoding='utf8'))
assert all(s!='ignore' for s in pro['board']['design_settings']['rule_severities'].values())
assert not pro['board']['design_settings']['drc_exclusions']
params=pro['text_variables']
assert params['FAB_MATERIAL']=='FR4' and params['FAB_FINISHED_THICKNESS_MM']=='1.0' and params['FAB_OUTER_COPPER_OZ']=='1' and params['FAB_INNER_COPPER_OZ']=='0.5' and params['FAB_FINISH']=='OSP'
cam=json.loads((CAM/'verification/gerber_readback_audit.json').read_text(encoding='utf8'))
assert all(v['directly_connected_ground_vias']==44 and v['isolated_signal_vias']==16 for v in cam['individual_inner_ground_connections'].values())
assert not cam['kicad_checks']['DRC_ignored_checks']
result={'revision':'IPEX1-A2','copper_layers':4,'positions_orientations_and_sides_unchanged':True,'all_copper_pad_geometry_nets_mask_margin_and_holes_unchanged':True,'all_tracks_and_vias_unchanged':True,'antenna_paste_removed_in_board_and_library':True,'all_36_footprints_have_courtyards':True,'44_ground_vias_connect_both_inner_planes':True,'each_IPEX_has_two_nearby_ground_vias':True,'all_16_signal_vias_isolated_from_inner_ground_planes':True,'saved_plot_options_match_production_flow':True,'confirmed_fabrication_parameters_saved':True,'all_PCB_DRC_rules_enabled':True,'PCB_DRC_exclusions':0,'production_review':str(CAM/'verification/gerber_readback_audit.json'),'not_verified':['RF performance at 10.5 GHz','Final individual dielectric thickness / FR4 grade','Screw-head and enclosure mechanical clearance']}
(reportdir/'full_review_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))

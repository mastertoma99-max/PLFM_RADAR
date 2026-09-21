"""Translate the complete board onto its A4 page, with a reversible backup."""
from pathlib import Path
import datetime, hashlib, json, shutil
import pcbnew as p

OUT=Path(__file__).resolve().parent.parent
FILE=OUT/'Phased_Array_Ant_IPEX1.kicad_pcb'
DX,DY=113.5,135.0
delta=p.VECTOR2I(p.FromMM(DX),p.FromMM(DY))
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
xy=lambda v:[v.x,v.y]

def snapshot(b,offset=(0,0)):
    def pt(v):return [v.x-offset[0],v.y-offset[1]]
    def poly(ps):
        return [[pt(ps.COutline(i).CPoint(j)) for j in range(ps.COutline(i).PointCount())]
                for i in range(ps.OutlineCount())]
    rows={}
    for fp in b.GetFootprints():
        rows[fp.m_Uuid.AsString()]=['footprint',fp.GetReference(),fp.GetValue(),pt(fp.GetPosition()),fp.GetOrientationDegrees(),fp.GetLayer()]
        for pad in fp.Pads():
            rows[pad.m_Uuid.AsString()]=['pad',pad.GetNumber(),pad.GetNetname(),pt(pad.GetPosition()),xy(pad.GetSize()),xy(pad.GetDrillSize()),pad.GetOrientationDegrees(),pad.GetLayerSet().FmtBin()]
        for z in fp.Zones():
            rows[z.m_Uuid.AsString()]=['footprint_zone',z.GetLayer(),z.GetIsRuleArea(),poly(z.Outline())]
        for g in fp.GraphicalItems():
            if isinstance(g,p.PCB_SHAPE):
                rows[g.m_Uuid.AsString()]=['fp_shape',g.GetLayer(),pt(g.GetStart()),pt(g.GetEnd()),g.GetWidth()]
        for f in fp.GetFields():
            rows[f.m_Uuid.AsString()]=['field',f.GetName(),f.GetText(),pt(f.GetPosition()),f.GetLayer()]
    for t in b.GetTracks():
        via=isinstance(t,p.PCB_VIA)
        rows[t.m_Uuid.AsString()]=[type(t).__name__,t.GetNetname(),pt(t.GetStart()),pt(t.GetEnd()),t.GetLayer(),t.GetWidth(p.F_Cu) if via else t.GetWidth(),t.GetDrillValue() if via else 0]
    for g in b.GetDrawings():
        assert isinstance(g,p.PCB_SHAPE)
        rows[g.m_Uuid.AsString()]=['drawing',g.GetLayer(),pt(g.GetStart()),pt(g.GetEnd()),g.GetWidth()]
    for z in b.Zones():
        rows[z.m_Uuid.AsString()]=['zone',z.GetNetname(),z.GetLayer(),poly(z.Outline())]
    return rows

b=p.LoadBoard(str(FILE))
bb=b.GetBoardEdgesBoundingBox()
assert abs(p.ToMM(bb.GetX())+.025)<1e-6 and abs(p.ToMM(bb.GetY())+70.025)<1e-6, 'Unexpected board bounds; no changes made'
assert len(list(b.Groups()))==0
before=snapshot(b)
BACKUP=OUT/'verification'/'before_page_centering'
BACKUP.mkdir(exist_ok=False)
shutil.copy2(FILE,BACKUP/FILE.name)
for group in [list(b.GetFootprints()),list(b.GetTracks()),list(b.Zones()),list(b.GetDrawings())]:
    for item in group:item.Move(delta)
settings=b.GetDesignSettings()
settings.SetAuxOrigin(settings.GetAuxOrigin()+delta)
settings.SetGridOrigin(settings.GetGridOrigin()+delta)
assert snapshot(b,(delta.x,delta.y))==before, 'Translation changed relative geometry'
assert p.SaveBoard(str(FILE),b)
again=p.LoadBoard(str(FILE))
assert snapshot(again,(delta.x,delta.y))==before,'Saved board differs'
report={'offset_mm':[DX,DY],'board_outline_centerline_before_mm':[0,-70,70,0],
        'board_outline_centerline_after_mm':[113.5,65,183.5,135],
        'page_mm':[297,210],'uniform_translation_all_items_verified':True,
        'relative_geometry_nets_pad_sizes_layers_and_uuids_unchanged':True,
        'verified_objects':len(before),'backup':str(BACKUP/FILE.name),
        'before_sha256':sha(BACKUP/FILE.name),'after_sha256':sha(FILE),
        'auxiliary_and_grid_origins_shifted_by_same_offset':True}
(OUT/'verification/page_centering.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
auditfile=OUT/'verification/build_audit.json'
audit=json.loads(auditfile.read_text(encoding='utf-8'))
audit['board_offset_mm']=[DX,DY]
audit['changes_coordinate_frame']='original Eagle-derived coordinates; add board_offset_mm for current PCB coordinates'
auditfile.write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))

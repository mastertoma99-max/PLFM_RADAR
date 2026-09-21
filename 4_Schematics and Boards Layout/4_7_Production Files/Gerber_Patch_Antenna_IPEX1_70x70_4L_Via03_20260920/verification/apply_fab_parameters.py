from pathlib import Path
import hashlib,json,re,shutil
OUT=Path(__file__).resolve().parent.parent
ROOT=next(x for x in OUT.parents if (x/'.git').exists())
SRC=ROOT/'4_Schematics and Boards Layout/4_6_Schematics/Antennas/Patch/4x4/Phased_Array_Ant_IPEX1'
PCB=SRC/'Phased_Array_Ant_IPEX1.kicad_pcb'
original=PCB.read_text(encoding='utf-8')
before=hashlib.sha256(PCB.read_bytes()).hexdigest()
backup=OUT/'verification/source_before_1mm_metadata.kicad_pcb'
if not backup.exists():shutil.copy2(PCB,backup)
modified,n=re.subn(r'(\(general\s*\(thickness )1\.6(\))',r'\g<1>1.0\2',original)
assert n==1 or re.search(r'\(general\s*\(thickness 1(?:\.0)?\)',original)
if n:PCB.write_text(modified,encoding='utf-8',newline='\n')
params={'material':'FR4','finished_board_thickness_mm':1.0,'outer_copper_oz':1.0,'inner_copper_oz':0.5,'finish':'OSP','copper_order':['F.Cu','In1.Cu','In2.Cu','B.Cu'],'individual_dielectric_thickness_mm':None,'manufacturer_stackup_confirmation_required':True,'user_specification':'FR4 1mm板厚 外层铜厚1盎司，内层0.5盎司，表面osp，叠层按照文件叠层顺序'}
for base in [SRC,OUT]:
 (base/'fabrication_requirements.json').write_text(json.dumps(params,ensure_ascii=False,indent=2),encoding='utf-8')
readme=SRC/'README_修改说明.md'
s=readme.read_text(encoding='utf-8')
s=s.replace('板材、介质厚度及阻抗参数沿用基础版的数据状态，本次未确定新的射频叠层或生成制造光绘。用于该频段前，应进行连接器与线缆的频率适配核对，以及馈电过渡仿真/实测。','用户已指定打样参数：FR4、成品板厚 1.0 mm、外层铜厚 1 oz、内层铜厚 0.5 oz、OSP；层序 F.Cu → In1.Cu → In2.Cu → B.Cu。PCB 总板厚显示值已由原默认 1.6 mm 更新为 1.0 mm，仅修改厚度元数据。各介质层厚度、FR4 具体牌号及阻抗参数尚未指定；不要把 KiCad 自动生成的各介质层默认厚度当成已确认的射频叠层。生产光绘另存于 `4_7_Production Files/Gerber_Patch_Antenna_IPEX1_70x70_4L_Via03_20260920`。用于该频段前，应核对连接器与线缆频率适配，并进行馈电过渡仿真/实测。')
readme.write_text(s,encoding='utf-8')
builder=SRC/'verification/build_ipex.py'
s=builder.read_text(encoding='utf-8').replace('assert pcb.SaveBoard(str(OUT/', 'b.GetDesignSettings().SetBoardThickness(mm(1.0))\nassert pcb.SaveBoard(str(OUT/',1)
builder.write_text(s,encoding='utf-8')
report={'before_sha256':before,'after_sha256':hashlib.sha256(PCB.read_bytes()).hexdigest(),'pcb_change':'Only general board thickness 1.6 -> 1.0 mm; copper geometry unchanged','user_parameters':params}
(OUT/'verification/manufacturing_parameter_update.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
checks=SRC/'verification/SHA256SUMS.txt'
names=[s.split('  ',1)[1] for s in checks.read_text(encoding='utf-8-sig').splitlines() if s]
checks.write_text('\n'.join(hashlib.sha256((SRC/n).read_bytes()).hexdigest().upper()+'  '+n for n in names)+'\n',encoding='utf-8')
print('Applied user fabrication parameters; copper geometry unchanged.')

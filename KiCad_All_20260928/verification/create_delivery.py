from pathlib import Path
import hashlib, json, shutil, zipfile

OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parent
inventory=json.loads((OUT/'source_inventory.json').read_text(encoding='utf-8'))
hardware=json.loads((OUT/'verification/schematic_connectivity_audit.json').read_text(encoding='utf-8'))
simulation=json.loads((OUT/'verification/qucs_conversion_audit.json').read_text(encoding='utf-8'))
checks=json.loads((OUT/'verification/final_validation.json').read_text(encoding='utf-8'))
for f in (OUT/'verification/import_side_effects').glob('*.kicad_dru'):
    target=OUT/'Hardware'/f.stem/f.name
    if not target.exists():shutil.copy2(f,target)
names={'Clocks_Freq_Synth_board':'频率合成板','RADAR_Main_Board':'雷达主板','RF_PA':'射频功率放大板','PowerBoard':'电源板','Phased_Array_Ant':'4×4天线（原始连接器版）','Patch_Anetnna_16_8':'8×16天线（原始连接器版）'}
lines=['# PLFM_RADAR 全部原理图 KiCad 工程','',
'转换日期：2026-09-28。验证环境：Windows，KiCad 10.0.0。','',
'## 文件统计与打开方法','',
'转换前递归扫描得到 **26个原理图文件**：6个 EAGLE `.sch`、8个 QucsStudio `.sch`、12个已有 `.kicad_sch`。压缩包内部备份不重复计数。',
'本次将14份非 KiCad 源图整理为 **14个独立 KiCad 工程**。硬件源图共9页；主板额外增加1页目录，因此交付18个正式 `.kicad_sch` 文件。`verification` 下的中间备份不属于正式工程页。',
'已有12个 KiCad 文件含天线改版、生产包副本、校验备份和一个 Gerber 空工程，保留原处，不覆盖、不重复转换。完整路径见末尾清单。','',
'使用 KiCad 10.0 或更新版本，打开下面的 `.kicad_pro`。原理图、PCB和本地库应连同所在文件夹一起复制。主板进入目录页后双击对应子页；也可使用左侧层级导航。','',
'## 硬件工程','',
'6套均附带对应PCB、本地符号库、封装库和库表。','',
'| 工程 | 源图页数 | 封装元件数 | 打开工程 |',
'|---|---:|---:|---|']
for a in hardware:
    n=a['project'];lines.append(f'| {names[n]} | {a["source_sheets"]} | {a["source_packaged_components"]} | [{n}](Hardware/{n}/{n}.kicad_pro) |')
lines+=['','## 仿真图工程','',
'按用户要求保留可编辑电路、参数、导线、源图注释与启用状态，未适配 KiCad/ngspice 仿真模型。',
'每个元件属性包含 `Qucs_Type`、`Qucs_Active`、按源顺序保存的 `Qucs_Param_XX` 和完整 `Qucs_SourceLine`。工程中的 `source_parameters.json` 保留全部参数及其原显示状态；`original/` 保留原图副本。',
'原图未启用的33个电路元件以 KiCad DNP 交叉标记保留。地符号用接地图形和同名GND网络标签表达；`.SP`、`.TR`、`SUBST`参数作为图面文字与JSON保存。仿真命令块的位置为便于阅读移到图纸下方。',
'S参数及波形依赖均已找到并复制到对应 `models/`；原绝对路径仍保留在源参数中，本地相对路径在 `Local_Model` 属性中。它们尚未绑定到仿真器。','',
'| 工程 | 电路元件数（不含地及仿真设置） | 打开工程 |','|---|---:|---|']
for a in simulation:
    n=a['project'];lines.append(f'| {n} | {a["circuit_components"]} | [{n}](Simulations/{n}/{n}.kicad_pro) |')
lines+=['','## 验证结果和转换修复','',
'- 14/14顶层原理图成功由 KiCad CLI 读取、导出XML网表和SVG预览；主板目录及4页电路均已导出。',
'- 6/6 PCB成功由 KiCad CLI 加载并导出顶层铜与板框预览。',
'- 6套硬件共1358个封装元件数量一致；依据源图的 gate/pin 到 package/pad 映射逐网对比：缺失元件0、缺失已连接引脚0、断网0、误并网0，原本悬空引脚没有被误接到其他引脚。KiCad会把悬空引脚列为单点网，因此总网数与EAGLE可能不同。',
'- 8套仿真图共115个电路元件；根据源坐标、端子和导线重建网络，导出网表未发现缺失引脚、断网或误并网。该检查验证图形/端子转换，不验证模型端口的物理意义或仿真数值。',
'- 原有26个原理图文件及6个配套 EAGLE PCB的SHA-256全部保持不变。',
'- 主板4页整理为一个KiCad层级工程，跨页连接使用原生导入的全局网络标签。',
'- 频率合成板的 `+3V3_LO_2` 支路、主板 `N$80` 的R78引脚连接及U16地总线在原生导入后缺少有效端点，已按源连接切分导线并补连接点。',
'- 源图把ADTR1107的9/10脚和EP4RKU+的17个NC类型引脚接到GND。KiCad原生导入将这些脚标为 `no_connect`，会使网表丢失连接。本次仅在转换副本中改为passive，以保留源图49个接地引脚的连接。源NC标记与实际用法仍需设计人员复核。',
'- 为符合KiCad位号格式：`22V → UNK22V0`；`ADAR1_…ADAR4_ → ADAR1_0…ADAR4_0`。PCB位号同步调整。',
'- PCB原生导入的少量未定义非铜注释层图元已转入 `User.Comments`（文件层名 `Cmts.User`），几何和文字保留，明细见 `pcb_layer_recovery.json`。',
'- 8×16天线复用了此前原始连接器版本的导入结果，并核对当前SCH/BRD源哈希一致；没有使用IPEX1改版替换原设计。','',
'## 已知限制','',
'硬件ERC仍有源设计/跨软件解释产生的提示，未为了得到零错误而屏蔽或批量改动电路。以下计数是本次KiCad运行结果，并非错误成因的逐条判定。8套仿真图ERC为0，但它们使用简化被动端子符号，ERC为0不代表可直接仿真。','',
'| 硬件工程 | ERC错误 | ERC警告 |','|---|---:|---:|']
for a in checks['projects']:
    if 'pcb_svg' in a:lines.append(f'| {a["project"]} | {a["erc_counts_by_severity"].get("error",0)} | {a["erc_counts_by_severity"].get("warning",0)} |')
lines+=['',
'本次交付目的是KiCad可打开、可编辑和源图连接保留。未进行完整PCB DRC、全板SCH/PCB一致性验证或RF/阻抗等效验证；源图和板文件本身可能不完全对应，尤其天线射频铜图形没有完整表达在原理图中。更新PCB前应先检查变更列表。',
'PCB导入所得默认板厚、材料、层叠数值不能作为制造确认；板材、成品板厚和介质层参数按原项目要求待确认。当前PCB文件不是重新批准的生产资料。','',
'## 命令行使用','',
'在原仓库中运行（脚本依赖 `source_inventory.json` 记录的相对源路径；单独拷走工程仍可打开，但重新转换/对比需要源仓库）：','',
'```powershell',
f'& "{OUT / "Run-Conversion.ps1"}"',
'```','',
'默认重新生成8套Qucs工程，并核对6套硬件网表、导出全部预览和ERC报告。重新生成会覆盖本次输出的Qucs副本；开始自行编辑后请先备份，或只运行验证：','',
'```powershell',
f'& "{OUT / "Run-Conversion.ps1"}" -VerifyOnly',
'```','',
r'脚本使用PATH中的Python 3，KiCad CLI路径为 `D:\3_Software\KiCAD\bin\kicad-cli.exe`。环境不同请调整三个Python脚本中的 `CLI` 常量。','',
'**EAGLE首次原理图导入的边界：** 本机KiCad 10.0 CLI没有直接EAGLE原理图导入命令，6份首次导入使用KiCad管理器原生导入入口；8×16使用已验证的历史原生导入。其后层级整理、网表比较、修复、库导出、仿真图重建和最终校验均使用脚本/CLI。`Run-Conversion.ps1`不会伪装成能从任意修改后的EAGLE文件重新生成6套硬件原理图；源图修改后需要重新原生导入。',
'`verification/finalize_hardware.py` 是本轮中间处理代码，不要单独对已编辑工程运行，否则会恢复导入基线。日常入口为上面的PowerShell脚本。','',
'## 报告与预览','',
'- [源文件清单和哈希](source_inventory.json)',
'- [最终加载与源哈希验证](verification/final_validation.json)',
'- [硬件逐网对比](verification/schematic_connectivity_audit.json)',
'- [仿真图转换对比](verification/qucs_conversion_audit.json)',
'- [本地封装库统计](verification/local_footprint_audit.json)',
'- [PCB注释层恢复记录](verification/pcb_layer_recovery.json)',
'- `verification/ERC/`：14个工程的完整ERC报告。',
'- `verification/previews/`：18页原理图SVG预览。',
'- `verification/pcb_previews/`：6块PCB预览。','',
'## 原有12个KiCad文件（保持原处）','']
for r in inventory:
    if r['kind']=='existing_kicad':lines.append('- `'+r['path']+'`')
lines+=['','正式工程包 `PLFM_RADAR_KiCad_14projects_20260928.zip` 包含14套工程、库、模型、源参数与主要校验报告/命令脚本；排除了UI临时状态、自动备份和本轮导入探测文件。','']
(OUT/'README_转换说明.md').write_text('\n'.join(lines),encoding='utf-8')

files=[]
for parent in ('Hardware','Simulations'):
    for f in (OUT/parent).rglob('*'):
        if not f.is_file():continue
        rel=f.relative_to(OUT)
        if any(p.startswith('.') or p.endswith('-backups') or p=='__pycache__' for p in rel.parts):continue
        if f.suffix in ('.kicad_prl','.lck'):continue
        files.append(f)
for f in (OUT/'verification').rglob('*'):
    if not f.is_file():continue
    rel=f.relative_to(OUT/'verification')
    if rel.parts[0] in ('ERC','previews','pcb_previews') or (len(rel.parts)==1 and f.suffix in ('.json','.py','.xml') and not f.name.startswith('test')):files.append(f)
files += [OUT/'README_转换说明.md',OUT/'source_inventory.json',OUT/'Run-Conversion.ps1']
manifest='\n'.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.relative_to(OUT).as_posix() for f in sorted(set(files)))+'\n'
(OUT/'SHA256SUMS.txt').write_text(manifest,encoding='utf-8');files.append(OUT/'SHA256SUMS.txt')
archive=ROOT/'PLFM_RADAR_KiCad_14projects_20260928.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for f in sorted(set(files)):z.write(f,OUT.name+'/'+f.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len([n for n in z.namelist() if n.endswith('.kicad_pro')])==14
    assert len([n for n in z.namelist() if n.endswith('.kicad_pcb')])==6
    assert len([n for n in z.namelist() if n.endswith('.kicad_sch')])==18
print('archive',archive,'bytes',archive.stat().st_size,'files',len(files),'sha256',hashlib.sha256(archive.read_bytes()).hexdigest())

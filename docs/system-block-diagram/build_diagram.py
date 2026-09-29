"""Build the offline AERIS-10 diagrams from reviewed local design sources."""
from pathlib import Path
import json, html, hashlib, re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE.parent / 'system-block-diagram.html'
COLORS = {'data':'#245dcc','rf':'#087f8c','ctrl':'#7254b3','clock':'#aa710c','power':'#bc414d','neutral':'#384858'}
SOURCES = [
 ('main','主板原理图','4_Schematics and Boards Layout/4_6_Schematics/MainBoard/RADAR_Main_Board.sch','器件型号、数量、USB 与主板网络'),
 ('clock','频率合成板原理图','4_Schematics and Boards Layout/4_6_Schematics/FrequencySynthesizerBoard/Clocks_Freq_Synth_board.sch','AD9523、两路 ADF4382A 与时钟连接'),
 ('power','电源板原理图','4_Schematics and Boards Layout/4_6_Schematics/PowerBoard/PowerBoard.sch','DC/DC、LDO、负电源及电源网络'),
 ('pa','扩展功放原理图','4_Schematics and Boards Layout/4_6_Schematics/PowerAmplifierBoard/RF_PA.sch','QPA2962、栅压与电流采样接口'),
 ('ref','原始系统框图','2_Functional Diagram & Interconnection Matrices/RADAR_V6_V2.png','白底工程风格、共用射频通道和扩展功放收发路径'),
 ('readme','项目说明','README.md','系统目标、天线选型及模块功能'),
 ('top','FPGA 顶层 RTL','9_Firmware/9_2_FPGA/radar_system_top.v','USB_MODE=1 默认值、DC notch、CFAR 和数据上传'),
 ('rx','FPGA 接收 RTL','9_Firmware/9_2_FPGA/radar_receiver_final.v','AGC、脉压、距离单元、MTI、Doppler 连接顺序'),
 ('ddc','数字下变频 RTL','9_Firmware/9_2_FPGA/ddc_400m.v','400 MHz 采样域、120 MHz NCO 默认值、CIC / CDC / FIR'),
 ('tx','FPGA 发射 RTL','9_Firmware/9_2_FPGA/radar_transmitter.v','Chirp 与 DAC 接口'),
 ('targets','FPGA 目标与接口说明','9_Firmware/9_2_FPGA/constraints/README.md','50T / 200T 型号与 USB 接口分工'),
 ('build200','200T 构建脚本','9_Firmware/9_2_FPGA/scripts/200t/build_200t.tcl','显式设置 USB_MODE=0'),
 ('mcu','STM32 主程序','9_Firmware/9_1_Microcontroller/9_1_3_C_Cpp_Code/main.cpp','UM982、USB CDC、PA 偏置与系统管理'),
 ('settings','MCU 默认设置','9_Firmware/9_1_Microcontroller/9_1_1_C_Cpp_Libraries/RadarSettings.cpp','默认频率与项目概述存在差异，待整机配置确认'),
]
SOURCED = {x[0]: dict(id=x[0],title=x[1],path=x[2],use=x[3],sha256=hashlib.sha256((ROOT/x[2]).read_bytes()).hexdigest()) for x in SOURCES}
graphs=[]
def graph(id,title,caption,w,h):
 g=dict(id=id,title=title,caption=caption,w=w,h=h,nodes=[],edges=[],labels=[],dots=[]);graphs.append(g);return g
def node(g,id,x,y,w,h,title,sub,meta,kind,detail,sources):
 g['nodes'].append(dict(id=id,x=x,y=y,w=w,h=h,title=title,sub=sub,meta=meta,kind=kind,detail=detail,sources=sources))
def edge(g,points,kind='data',label='',lx=0,ly=0,both=False,arrow=True,dash=False):
 g['edges'].append(dict(points=points,kind=kind,label=label,lx=lx,ly=ly,both=both,arrow=arrow,dash=dash))
def label(g,x,y,text,size=20,color='#59697b'):
 g['labels'].append(dict(x=x,y=y,text=text,size=size,color=color))

g=graph('overview','整机框图','从主机、数字处理、模拟收发到阵列天线；下方展开系统控制、时钟与供电。',1800,890)
label(g,40,60,'AERIS-10 / PLFM_RADAR 系统总览',29,'#152e46')
label(g,40,104,'10.5 GHz 项目目标 · 脉冲线性调频 · 16 路模拟波束赋形',19)
node(g,'host',40,230,240,170,'上位机','Python 雷达 GUI','显示 · 参数设置 · 数据记录','data','接收距离像、多普勒数据与检测结果；下发处理参数。FPGA 数据口与 STM32 USB CDC 管理口是两条独立连接。GUI_V65_Tk 与 GUI_V7_PyQt 是 README 指出的活动版本。',['readme','top','mcu'])
node(g,'digital',410,230,270,170,'数字处理与 USB','{fpgaShort}','{usbShort}','data','FPGA 生成 Chirp、接收 ADC 数据并执行脉压、MTI、Doppler 与 CFAR。50T 主板 U42=XC7A50T-2FTG256I，U6=FT2232HQ；200T 开发目标为 XC7A200T-2FBG484I，使用 FT601。切换本页选项仅改变图的展示。',['main','top','targets','build200'])
node(g,'analog',800,230,270,170,'模拟收发链路','AD9708 / AD9484','LTC5552 ×2 · 滤波 / 驱动','rf','发射：8 位 DAC → 重建低通 → 上变频 → RF 带通。接收：RF 带通 → 下变频 → IF 滤波 / AD8352 驱动 → 8 位 ADC。两条链路经 RF 开关接入公共阵列端口。',['main','ref','rx'])
node(g,'beam',1190,230,240,170,'阵列射频前端','ADAR1000 ×4','ADTR1107 ×16','rf','四片四通道 ADAR1000 实现 16 路相位与增益控制；每路连接一片 ADTR1107 收发前端。EP4RKU+ 在公共端口与四片 ADAR1000 之间完成分配 / 合成。属于模拟波束赋形，不是 16 组独立 ADC。',['main','readme'])
node(g,'antenna',1550,230,210,170,'阵列天线','{antenna}','{frontEnd}','rf','项目描述提供 8×16 贴片阵列与 32×16 波导阵列两类方案。16 路射频通道对应馈电子阵；不要将 16 路等同于 16 个贴片。增强方案在发射路径加入 16 路 QPA2962；接收信号绕过外置功放。',['readme','ref','pa'])
node(g,'sensors',40,620,240,150,'定位与姿态','UM982 · GY-85','BMP180 气压计','ctrl','当前 MCU 主程序使用 UM982，旧框图中的 NEO-6M 已作为历史信息处理。GPS、IMU 与气压信息供位置标记、姿态修正与监控使用。',['mcu','readme','ref'])
node(g,'mcu',410,620,270,150,'系统管理 MCU','STM32F746ZGT7','配置 · 扫描 · 监测 · 时序','ctrl','配置 AD9523 / ADF4382A 与 ADAR1000，协调 FPGA 扫描时序，管理 PA 偏置与电源顺序，读取传感器、温度和电流，控制电机 / 散热。通过自身 USB FS CDC 与上位机通信。',['main','mcu','readme'])
node(g,'clocks',800,620,270,150,'时钟与本振板','AD9523 + ADF4382A ×2','ADC / DAC / FPGA 时钟 · TX/RX LO','clock','参考振荡器经 AD9523 分配时钟，两片 ADF4382A 分别产生发射和接收本振。ADC 采样设计为 400 MHz，DAC 侧逻辑使用 120 MHz，FPGA 主处理域为 100 MHz。频率数值是文件中的设计 / 配置值，不代表上板测量。',['clock','top','ddc','ref'])
node(g,'power',1190,620,240,150,'电源管理板','DC/DC · LDO · 负电源','MCU 控制上 / 下电顺序','power','原理图包含 TPS562208、TPS7A8300、LM2662。供电覆盖数字逻辑、射频、模拟和时钟等模块；总览仅画部分供电连接，完整关系见时钟与控制视图。外置 QPA2962 的漏极供电与继电器属于增强方案。',['power','mcu','readme'])
edge(g,[[280,315],[410,315]],'data','USB',345,300,True)
edge(g,[[680,315],[800,315]],'data','ADC / DAC',740,300,True)
edge(g,[[1070,315],[1190,315]],'rf','公共 RF',1130,300,True)
edge(g,[[1430,315],[1550,315]],'rf','16 通道',1490,300,True)
edge(g,[[545,620],[545,400]],'ctrl','SPI / GPIO',615,510,True)
edge(g,[[280,695],[410,695]],'ctrl','I²C / UART',345,680,True)
edge(g,[[680,695],[800,695]],'ctrl','SPI',740,680,True)
edge(g,[[935,620],[935,400]],'clock','时钟 / LO',1000,515)
edge(g,[[1310,620],[1310,400]],'power','多路供电',1375,515)
edge(g,[[1190,695],[1070,695]],'power','电源',1130,680)
edge(g,[[90,400],[90,525],[435,525],[435,620]],'ctrl','STM32 USB CDC 管理连接',267,509,True)
label(g,40,840,'点击任一模块查看型号、作用与本地资料依据。扩展功放和共享收发路径在“收发链路”中展开。',18)

g=graph('rf','收发链路','蓝色为数字采样接口，青色为模拟 / 射频通道；共用路径的双箭头表示分时收发。',2150,1000)
label(g,40,56,'收发链路与 16 通道阵列',29,'#152e46')
label(g,40,95,'TX 沿上行向右 →；RX 沿下行向左 ←；右侧为共用波束赋形链路。',19)
node(g,'rf_fpga',40,170,200,420,'FPGA','{fpgaShort}','TX / RX','data','同一 FPGA 的上方端口输出 DAC 波形，下方端口输入 ADC 数据；本框为一个物理器件。',['main','tx','rx'])
node(g,'dac',330,170,200,100,'AD9708','8 位 DAC','U3 · 120 MHz 设计时钟','data','由 FPGA 并行输出 8 位 Chirp 数据，经 AD9708 形成模拟波形。120 MHz 为项目时钟规划 / RTL 域，未做实板验证。',['main','tx','ref'])
node(g,'tx_lpf',620,170,200,100,'重建低通','DAC LPF','抑制采样镜像','rf','DAC 输出进入模拟重建滤波器，然后接入上变频混频器。这里只表达功能与连接，不对滤波器性能做仿真结论。',['main','ref'])
node(g,'tx_mix',910,170,200,100,'TX 上变频','LTC5552','独立 TX 本振输入','rf','发射混频器接收 DAC 滤波后的信号与 ADF4382A TX 本振；上变频输出再经过 RF 带通滤波。',['main','clock','ref'])
node(g,'tx_bpf',1200,170,200,100,'RF 带通','TX BPF','选取发射频段','rf','连接 TX 混频器输出与共用收发开关。项目射频目标约为 10.5 GHz，具体 LO / Chirp 设置需与固件一致。',['main','ref','settings'])
node(g,'switch',1510,320,200,140,'收发开关','M3SWA2-34DR+','TX / RX 分时切换','rf','发射带通和接收带通分别接开关两侧，共用端连接 EP4RKU+。两条模拟链路分时共享阵列。',['main','ref'])
node(g,'splitter',1840,320,240,140,'功分 / 合成','EP4RKU+','1 ↔ 4 公共支路','rf','发射时将公共 RF 信号分配到四个 ADAR1000；接收时反向合成四个 ADAR1000 输出。',['main','ref'])
node(g,'adc',330,490,200,100,'AD9484','8 位 ADC','U1 · 400 MS/s 设计值','data','原理图器件为 AD9484BCPZ-500；该项目 RTL 按 400 MHz ADC 采样 / DCO 域处理，8 位 LVDS 数据送入 FPGA。器件后缀 -500 不等于项目运行在 500 MS/s。',['main','rx','ddc'])
node(g,'rx_driver',620,490,200,100,'IF 差分驱动','AD8352 + 输出滤波','原理图含 U4 / U8','rf','接收中频经 AD8352 差分放大 / 驱动及滤波网络进入 AD9484；本图将 IF 调理级合并展示。',['main','ref'])
node(g,'rx_if',910,490,200,100,'IF 滤波','模拟滤波网络','连接混频器与驱动级','rf','对下变频后的中频信号进行模拟滤波。DDC RTL 默认 IF_FREQ=120 MHz，该数字默认值不证明模拟链路已按相同参数完成板上验证。',['main','ref','ddc'])
node(g,'rx_mix',1200,490,200,100,'RX 下变频','RF BPF + LTC5552','独立 RX 本振输入','rf','接收信号从共用开关进入 RF 带通，再进入 LTC5552 下变频器；本块合并了这两个功能。',['main','clock','ref'])
node(g,'adar',1840,740,240,130,'ADAR1000 ×4','相位 / 增益控制','4 × 4 = 16 路','rf','四个独立 RF 公共支路分别接四片 ADAR1000，每片展开四路收发，连接共 16 片 ADTR1107。',['main','readme'])
node(g,'adtr',1510,740,240,130,'ADTR1107 ×16','每通道收发前端','TX 放大 / RX 低噪放大','rf','阵列每通道一片 ADTR1107。模拟波束赋形后的多通道信号在 RF 域合成，然后由公共 ADC 接收链采样。',['main','readme'])
node(g,'pa_route',1180,740,240,130,'{routeTitle}','{routeSub}','{routeMeta}','rf','基础方案：前端连接贴片阵列，无外置 QPA2962。增强方案：外部 RF 开关 → QPA2962 功放 → 环行器 → 天线；接收回波从环行器经旁路返回 ADTR1107，不经过外置 GaN 功放。功放及路由按原始系统图表达，实际装配选项仍需与板级连接确认。',['pa','ref','readme'])
node(g,'rf_ant',840,740,240,130,'阵列天线','{antenna}','16 路子阵馈电','rf','8×16 贴片与 32×16 波导为项目所述不同整机方案。尺寸和制造验证不由本系统图推导。',['readme','ref'])
for a,b in [(240,330),(530,620),(820,910),(1110,1200)]:edge(g,[[a,220],[b,220]],'data' if a==240 else 'rf')
edge(g,[[1400,220],[1460,220],[1460,350],[1510,350]],'rf')
edge(g,[[1510,425],[1460,425],[1460,540],[1400,540]],'rf')
for a,b in [(1200,1110),(910,820),(620,530),(330,240)]:edge(g,[[a,540],[b,540]],'data' if a==330 else 'rf')
edge(g,[[1710,390],[1840,390]],'rf','共用 RF',1775,375,True)
edge(g,[[1960,460],[1960,740]],'rf','4 路',2010,612,True)
edge(g,[[1840,805],[1750,805]],'rf',both=True)
edge(g,[[1510,805],[1420,805]],'rf',both=True)
edge(g,[[1180,805],[1080,805]],'rf',both=True)
label(g,840,929,'增强方案接收路径绕过 QPA2962；双向连接表示整个收发路由组合，不表示 PA 双向放大。',19)
label(g,40,940,'本振与时钟连接见“时钟与控制”；射频性能及最终频率配置尚需整机确认。',18)

g=graph('dsp','FPGA 处理','按当前 RTL 实例连接顺序整理。选择 50T / 200T 改变目标器件和 USB 接口，不代表对应构建已经实板验收。',1830,1040)
label(g,40,56,'FPGA 数据处理与脉冲时序',29,'#152e46')
label(g,40,100,'ADC → 数字下变频 → 脉压 → MTI → Doppler → DC notch → CFAR → USB',19)
specs=[
('capture','ADC 接口','LVDS → 8 位采样','400 MHz / DCO','ADC LVDS 采样经 ad9484_interface_400m 进入 DDC；DCO 经 MMCM / 缓冲建立采样域。',['rx']),
('ddc','数字下变频','NCO × I / Q','默认 IF = 120 MHz','ddc_400m 的 IF_FREQ=120000000、FS=400000000；NCO 与乘法器产生 I/Q。',['ddc']),
('cic','CIC 抽取','4 倍抽取','400 → 100 MS/s','两路 I/Q 使用 CIC 抽取，后续跨域连接到 100 MHz 处理域。',['ddc']),
('cdc','跨时钟域','I / Q 数据同步','400 MHz → 100 MHz','真实采样域到处理域跨越在 DDC 内部的 CIC 与 FIR 之间处理。',['ddc','rx']),
('fir','FIR 低通','I/Q 滤波与缩放','100 MHz 处理域','FIR 低通后经 ddc_input_interface 转为接收处理链使用的数据格式。',['ddc','rx']),
('gain','数字增益 / AGC','峰值与饱和监测','主机可配置','rx_gain_control 位于 DDC 输出与匹配滤波之间；可自动调节数字移位增益。',['rx']),
]
for i,(id,t,s,m,d,src) in enumerate(specs):node(g,id,40+300*i,170,230,110,t,s,m,'data',d,src)
specs2=[
('cfar','CFAR 检测','CA / GO / SO 模式','门限 / 保护单元可配置','cfar_ca 接收经过 DC notch 的 Doppler 数据，输出检测标记、距离 / Doppler 索引与幅度；禁用时支持简单幅度门限。',['top']),
('notch','DC notch','抑制零多普勒附近','可配置宽度 / 可旁路','在两段 16 点 Doppler FFT 的输出上分别处理 DC 区域，然后进入 CFAR。原始 Doppler 上传支路在该滤波之前取数。',['top']),
('doppler','Doppler FFT','32 Chirps / 帧','2 个 16 点子帧 FFT','当前实例设置 DOPPLER_FFT_SIZE=16、CHIRPS_PER_FRAME=32、CHIRPS_PER_SUBFRAME=16；不是单次 32 点 Doppler FFT。',['rx']),
('mti','MTI 杂波抑制','两脉冲相消','64 个距离单元','MTI 位于距离单元抽取后、Doppler 处理前，关闭时透明传递。',['rx']),
('range','距离单元抽取','1024 → 64','峰值模式 / 16 倍','range_bin_decimator 输出 64 个距离单元供 MTI / Doppler。完整距离像仍通过单独 USB 支路提供。',['rx','top']),
('mf','匹配滤波 / 脉压','FFT → 频域相乘 → IFFT','长 / 短 Chirp 参考','matched_filter_multi_segment 使用长 / 短脉冲参考数据执行匹配滤波，输出复数距离像。',['rx']),
]
for i,(id,t,s,m,d,src) in enumerate(specs2):node(g,id,40+300*i,480,230,110,t,s,m,'data',d,src)
for i in range(5):edge(g,[[270+300*i,225],[340+300*i,225]])
edge(g,[[1655,280],[1655,480]],'data','I/Q',1700,385)
for i in range(5):edge(g,[[340+300*i,535],[270+300*i,535]])
node(g,'usb',40,800,370,130,'USB 数据与命令','{usbLong}','距离像 · Doppler · 检测结果','data','USB 数据接口汇集三类数据流，支持主机下行配置命令。图中 CFAR 箭头仅表示检测流；距离像取自匹配滤波输出，Doppler 流取自 DC notch 之前。50T 使用 8 位 / 60 MHz FT2232H，200T 使用 32 位 / 100 MHz FT601。',['top','targets','build200'])
edge(g,[[155,590],[155,800]],'data','检测流',217,706)
node(g,'sequencer',670,800,300,130,'脉冲 / 扫描时序','Chirp 控制器','保护间隔 · TX/RX · 帧同步','ctrl','FPGA 时序控制逻辑协调 DAC 发射、混频器使能、波束加载和接收帧同步；MCU 负责配置与系统管理。',['tx','top','rx'])
node(g,'txlut',1110,800,300,130,'波形 LUT → DAC 接口','长 / 短 Chirp 数据','8 位并行 → AD9708','data','radar_transmitter 使用波形数据与 DAC 接口生成发射波形；120 MHz DAC 逻辑域与 100 MHz DSP 域分开。',['tx','top'])
node(g,'reference',1540,800,230,130,'匹配参考存储','Chirp 参考 + 延时对齐','供脉压模块使用','data','参考数据存储与延时对齐位于匹配滤波参考路径，不是把发射 LUT 的数据线直接接入接收输入。',['rx'])
edge(g,[[970,865],[1110,865]],'ctrl','使能 / 时序',1040,850)
edge(g,[[1655,800],[1655,590]],'data','参考 I/Q',1720,706)
label(g,40,995,'USB 还接收完整距离像与原始 Doppler 支路；为保持主链清晰，这两条上传线未在图中展开。',18)

g=graph('control','时钟与控制','控制关系按接口分组展示；左侧共用竖线是逻辑关系汇总，不是将 SPI、I²C、UART 接到同一物理总线。',1810,1220)
label(g,40,50,'系统时钟、控制与辅助模块',29,'#152e46')
node(g,'manager',45,510,275,170,'STM32F746ZGT7','系统配置与运行管理','USB CDC ↔ 上位机','ctrl','同一 MCU 使用不同的 SPI、I²C、UART 与 GPIO 接口完成右侧各组功能；实时 Chirp / 收发控制还需要与 FPGA 协同。',['main','mcu'])
rows=[
 (130,'clockcfg','时钟与本振配置','AD9523 · ADF4382A ×2','SPI / 状态 / 同步 GPIO','clock','配置低抖动时钟分配及 TX / RX 本振，读取锁定状态。参考振荡器来源为频率合成板；旧图与原理图参考频率标注有差异，未将旧振荡器频率照搬。',['clock','mcu'],
  'clockout','参考源 → 分配 / 合成 → 输出','ADC 400M · DAC 120M · FPGA 100M','独立 TX LO / RX LO','时钟输出频率按项目框图及 RTL 域标注；具体 AD9523 通道分配、LO 频点与实际采样应在整机调试时统一。',['clock','ref','top','ddc']),
 (350,'beamcfg','波束与收发控制','ADAR1000 ×4','SPI 配置 + FPGA TR / LOAD','ctrl','MCU 配置相位与增益表；FPGA 与 MCU 的脉冲 / 扫描逻辑协同控制 ADAR 的 TR、RX_LOAD、TX_LOAD。',['main','mcu','top'],
  'beamout','ADTR1107 ×16 / RF 开关','模拟波束赋形与分时收发','16 路前端','ADAR1000 与 ADTR1107 组成模拟阵列收发前端；公共 RF 经开关选择发射或接收链。',['main','ref']),
 (570,'biascfg','扩展 PA 偏置与监测','DAC5578 ×2 · OPA4703 ×4','INA241A3 ×16 · ADS7830 ×2','ctrl','两片八通道 DAC5578 控制 16 路栅压，经四片四通道 OPA4703 调理；16 路 INA241A3 配合两片 ADS7830 回读电流。旧图将偏置 DAC 写为 AD9708，按主板原理图更正。',['main','readme','mcu'],
  'biasout','QPA2962 ×16（增强方案）','Vg 设置 / Idq 回读 / Vd 继电器','基础方案不装外置 PA','功放板使用 QPA2962。MCU 执行偏置校准与漏极电源控制；外置 PA 是整机增强配置，不由 50T / 200T FPGA 选择决定。',['pa','readme','mcu']),
 (790,'sensorcfg','定位 / 姿态 / 温度采集','UM982 · GY-85 · BMP180','热敏电阻 ×8 → ADS7830 ×1','ctrl','GPS 经 UART，惯性 / 气压与外部 ADC 通过相应接口接入 MCU；温度监控使用 U10 ADS7830，因此全板 ADS7830 共三片。',['main','mcu','readme'],
  'sensorout','状态与位置数据','地图定位 · 姿态修正 · 过温判断','由 MCU 汇总至主机 / 控制逻辑','这些是传感器数据的用途；模块间箭头表示逻辑处理关系，不代表传感器直接连接 USB 数据桥。',['readme','mcu']),
 (1010,'powercfg','电源 / 电机 / 冷却管理','PowerBoard · 步进驱动 · 风扇','GPIO / 电源使能 / 脉冲','power','MCU 执行电源时序、步进电机控制和散热开关。电源板中的负电源与分组使能不能按普通单路 3.3 V 系统简化。',['power','mcu','readme'],
  'powerout','数字 / 模拟 / RF / 时钟供电','1.0V · 1.8V · 3.3V · 5V 等','另含负电源 / 偏置电源','电源网络包括 +1V0_FPGA、+1V8_FPGA、+1V8_CLOCK、多组 +3V3 / +5V0、-5V0_ADAR、-3V3_SW 及 ±5V5_PA 等。此列表不是上电顺序表，精确顺序以固件和电源管理资料为准。',['power','mcu']),
]
edge(g,[[320,595],[440,595]],'ctrl',arrow=False)
edge(g,[[440,190],[440,1070]],'ctrl',arrow=False)
for y,id,t,s,m,k,d,src,id2,t2,s2,m2,d2,src2 in rows:
 node(g,id,600,y,410,120,t,s,m,k,d,src)
 node(g,id2,1260,y,480,120,t2,s2,m2,k,d2,src2)
 edge(g,[[440,y+60],[600,y+60]],'ctrl')
 edge(g,[[1010,y+60],[1260,y+60]],k,'配置 / 状态' if y<500 else '控制 / 数据',1135,y+44,both=y==570)
 g['dots'].append([440,y+60])
label(g,40,1182,'原理图确认：4×ADAR1000、16×ADTR1107、2×DAC5578、4×OPA4703、16×INA241A3、3×ADS7830。',18)

DEFAULT={'fpgaShort':'XC7A50T · Artix-7','usbShort':'FT2232H · USB 2.0','usbLong':'FT2232H · 8 位 / 60 MHz','antenna':'8 × 16 贴片阵列','frontEnd':'基础阵列方案','routeTitle':'基础直连路径','routeSub':'ADTR1107 ↔ 贴片阵列','routeMeta':'不配置外置 QPA2962'}
def subst(v):
 for k,x in DEFAULT.items():v=v.replace('{'+k+'}',x)
 return v
def esc(v):return html.escape(str(v),quote=True)

def svg(g):
 s=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {g["w"]} {g["h"]}" role="img" aria-label="{g["title"]}" class="diagram-svg" data-graph="{g["id"]}">', '<style>text{font-family:"Segoe UI","Microsoft YaHei",sans-serif}.block{cursor:pointer}.block:focus{outline:none}.block:focus rect,.block:hover rect{stroke-width:3}.node-title{font-weight:650}.wire-label{paint-order:stroke;stroke:white;stroke-width:7;stroke-linejoin:round}.selected rect{stroke-width:4}</style>',f'<rect width="{g["w"]}" height="{g["h"]}" fill="white"/>','<defs>']
 for k,c in COLORS.items():s.append(f'<marker id="{g["id"]}-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{c}"/></marker>')
 s.append('</defs>')
 for e in g['edges']:
  pts=[p[:] for p in e['points']]
  # Stop just before the destination box; retain a visible arrow / border gap.
  if e['arrow']:
   p,q=pts[-2:]; dx,dy=q[0]-p[0],q[1]-p[1]; dist=abs(dx)+abs(dy);q[0]-=dx/dist*7;q[1]-=dy/dist*7
  if e['both']:
   p,q=pts[:2];dx,dy=q[0]-p[0],q[1]-p[1];dist=abs(dx)+abs(dy);p[0]+=dx/dist*7;p[1]+=dy/dist*7
  d='M '+' L '.join(f'{x:g} {y:g}' for x,y in pts)
  end=f' marker-end="url(#{g["id"]}-{e["kind"]})"' if e['arrow'] else ''
  start=f' marker-start="url(#{g["id"]}-{e["kind"]})"' if e['both'] else ''
  s.append(f'<path class="wire" d="{d}" fill="none" stroke="{COLORS[e["kind"]]}" stroke-width="2.4"{end}{start}/>' )
  if e['label']:s.append(f'<text class="wire-label" x="{e["lx"]}" y="{e["ly"]}" text-anchor="middle" fill="{COLORS[e["kind"]]}" font-size="17">{esc(e["label"])}</text>')
 for x,y in g['dots']:s.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{COLORS["ctrl"]}"/>')
 for n in g['nodes']:
  x,y,w,h=n['x'],n['y'],n['w'],n['h'];c=COLORS[n['kind']];cy=y+h/2
  s.append(f'<g class="block" data-id="{n["id"]}" role="button" tabindex="0" aria-label="{esc(subst(n["title"])+"，"+subst(n["sub"])+"，查看模块详情")}"><title>{esc(subst(n["title"]))}：{esc(n["detail"])}</title><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="white" stroke="{c}" stroke-width="1.6"/><path d="M{x} {y+4} H{x+w}" stroke="{c}" stroke-width="5"/>')
  for key,dy,size,fill in [('title',-22,22,'#183249'),('sub',10,18,c),('meta',38,15,'#536374')]:
   s.append(f'<text class="node-{key}" x="{x+w/2}" y="{cy+dy}" text-anchor="middle" fill="{fill}" font-size="{size}" data-template="{esc(n[key])}">{esc(subst(n[key]))}</text>')
  s.append('</g>')
 for l in g['labels']:s.append(f'<text x="{l["x"]}" y="{l["y"]}" font-size="{l["size"]}" fill="{l["color"]}">{esc(l["text"])}</text>')
 s.append('</svg>');return '\n'.join(s)

def drawio():
 root=ET.Element('mxfile',host='app.diagrams.net',version='26.0.0')
 for g in graphs:
  dia=ET.SubElement(root,'diagram',name=g['title'],id=g['id']); model=ET.SubElement(dia,'mxGraphModel',page='1',pageWidth=str(g['w']),pageHeight=str(g['h']),background='#ffffff'); cells=ET.SubElement(model,'root');ET.SubElement(cells,'mxCell',id='0');ET.SubElement(cells,'mxCell',id='1',parent='0')
  for n in g['nodes']:
   c=ET.SubElement(cells,'mxCell',id=n['id'],parent='1',vertex='1',value='\n'.join(subst(n[k]) for k in ['title','sub','meta']),style=f'rounded=0;whiteSpace=wrap;html=0;fillColor=#ffffff;strokeColor={COLORS[n["kind"]]};fontColor=#183249;fontSize=18;')
   ET.SubElement(c,'mxGeometry',{'x':str(n['x']),'y':str(n['y']),'width':str(n['w']),'height':str(n['h']),'as':'geometry'})
  for i,e in enumerate(g['edges']):
   c=ET.SubElement(cells,'mxCell',id=f'e{i}',parent='1',edge='1',style=f'edgeStyle=none;rounded=0;strokeColor={COLORS[e["kind"]]};strokeWidth=2;endArrow={"block" if e["arrow"] else "none"};startArrow={"block" if e["both"] else "none"};')
   for endpoint, attr, prefix in [(e['points'][0],'source','exit'),(e['points'][-1],'target','entry')]:
    x,y=endpoint
    for n in g['nodes']:
     if n['x']<=x<=n['x']+n['w'] and n['y']<=y<=n['y']+n['h'] and (x in (n['x'],n['x']+n['w']) or y in (n['y'],n['y']+n['h'])):
      c.set(attr,n['id']);c.set('style',c.get('style')+f'{prefix}X={(x-n["x"])/n["w"]};{prefix}Y={(y-n["y"])/n["h"]};{prefix}Dx=0;{prefix}Dy=0;');break
   geo=ET.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'})
   for p,key in [(e['points'][0],'sourcePoint'),(e['points'][-1],'targetPoint')]:ET.SubElement(geo,'mxPoint',{'x':str(p[0]),'y':str(p[1]),'as':key})
   if len(e['points'])>2:
    a=ET.SubElement(geo,'Array',{'as':'points'})
    for x,y in e['points'][1:-1]:ET.SubElement(a,'mxPoint',x=str(x),y=str(y))
  texts=g['labels']+[dict(x=e['lx']-100,y=e['ly']-20,text=e['label'],size=17,color=COLORS[e['kind']]) for e in g['edges'] if e['label']]
  for i,l in enumerate(texts):
   c=ET.SubElement(cells,'mxCell',id=f'label{i}',parent='1',vertex='1',value=l['text'],style=f'text;html=0;align=left;verticalAlign=middle;whiteSpace=wrap;strokeColor=none;fillColor=#ffffff;fontSize={l["size"]};fontColor={l["color"]};')
   ET.SubElement(c,'mxGeometry',{'x':str(l['x']),'y':str(l['y']-18 if l in g['labels'] else l['y']),'width':str(min(g['w']-l['x']-20,1400) if l in g['labels'] else 200),'height':'30','as':'geometry'})
 ET.indent(root);return ET.tostring(root,encoding='unicode',xml_declaration=True)

CSS='''
:root{--navy:#142f46;--muted:#627384;--border:#d9e2e9;--blue:#245dcc;--surface:#f2f5f8}*{box-sizing:border-box}body{margin:0;background:var(--surface);color:var(--navy);font:15px/1.65 "Segoe UI","Microsoft YaHei",sans-serif}button,select{font:inherit}button,a,select{touch-action:manipulation}button{cursor:pointer}button:focus-visible,select:focus-visible,a:focus-visible{outline:3px solid #3683d8;outline-offset:3px}header{background:#fff;border-bottom:1px solid var(--border);padding:26px 36px 23px}.head{max-width:1680px;margin:auto;display:flex;align-items:flex-start;justify-content:space-between;gap:22px}.eyebrow{font-size:12px;color:var(--blue);font-weight:700;letter-spacing:.16em}.title{font-size:30px;line-height:1.3;margin:6px 0 8px;font-weight:650}.subtitle{margin:0;color:var(--muted);font-size:14px}.stamp{font-size:12px;color:var(--muted);white-space:nowrap;text-align:right;border-left:3px solid #91b5d5;padding-left:16px;margin-top:7px}.stamp strong{display:block;font-size:14px;color:var(--navy)}main{max-width:1752px;margin:auto;padding:22px 36px 34px}.settings{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:19px}.choices{display:flex;gap:18px;flex-wrap:wrap;align-items:center}.choices label{display:flex;align-items:center;gap:9px;color:var(--muted);font-size:13px}select{border:1px solid #cbd7e1;border-radius:5px;background:white;color:var(--navy);padding:8px 32px 8px 11px;font-size:13px;max-width:100%}.badge{font-size:12px;color:#53748e;display:flex;gap:7px;align-items:center}.badge:before{content:'';width:6px;height:6px;border-radius:50%;background:#578d9a}.diagram-shell{background:white;border:1px solid var(--border);border-radius:8px;overflow:hidden}.toolbar{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border);padding:0 20px;gap:15px;flex-wrap:wrap}.tabs{display:flex;gap:23px;overflow-x:auto;max-width:100%}.tabs button{border:0;border-bottom:3px solid transparent;padding:17px 0 14px;background:none;color:var(--muted);font-size:14px;white-space:nowrap}.tabs button[aria-selected=true]{color:var(--blue);border-color:var(--blue);font-weight:650}.tools{display:flex;gap:7px;align-items:center;padding:9px 0}.tools button{background:white;border:1px solid var(--border);border-radius:4px;font-size:12px;color:#39566d;padding:5px 10px}.tools button:hover{background:#f0f5fa}.tools output{font-size:12px;color:var(--muted);min-width:39px;text-align:center}.caption{padding:12px 21px 0;margin:0;font-size:13px;color:var(--muted)}.viewport{overflow:auto;padding:8px 4px 0;max-height:75vh;scroll-behavior:smooth}.panel[hidden]{display:none}.diagram-svg{display:block;width:100%;min-width:1130px;height:auto}.legend{display:flex;flex-wrap:wrap;gap:22px;padding:13px 22px 16px;font-size:12px;color:var(--muted);border-top:1px solid #edf1f4}.legend span{display:flex;align-items:center;gap:7px}.legend i{width:21px;height:3px;background:var(--c)}.legend .hint{margin-left:auto}.detail{display:grid;grid-template-columns:240px 1fr;gap:24px;border-top:1px solid var(--border);padding:19px 24px;background:#f9fbfd;min-height:127px}.detail .label{font-size:11px;letter-spacing:.1em;color:var(--blue);font-weight:650}.detail h2{font-size:19px;margin:2px 0}.detail p{margin:0;font-size:14px;color:#425b6e}.detail-links{display:flex;flex-wrap:wrap;gap:5px 14px;margin-top:7px;font-size:12px}a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}.notes{display:grid;grid-template-columns:1fr 1fr;gap:27px;margin:24px 0 20px}.notes h2{font-size:15px;margin:0 0 6px}.notes p{margin:0;font-size:13px;color:var(--muted)}details{border-top:1px solid #cdd9e3;padding-top:14px}summary{font-size:14px;cursor:pointer;font-weight:600}.source-table{overflow:auto;margin-top:13px}table{border-collapse:collapse;width:100%;font-size:12px;background:#fff}td,th{text-align:left;padding:9px 13px;border-bottom:1px solid #e5ebf0;vertical-align:top}th{background:#eaf0f5;color:#50687c}td.path{max-width:600px;overflow-wrap:anywhere;color:var(--muted)}code{font-size:11px;color:#61758a}footer{font-size:12px;color:var(--muted);margin-top:16px;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}.downloads{display:flex;gap:17px}.screen-reader{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}@media(max-width:760px){header{padding:21px 18px}.title{font-size:25px}.head{display:block}.stamp{display:none}main{padding:16px 12px}.settings{gap:9px}.choices{gap:9px;width:100%}.choices label{width:100%;justify-content:space-between}select{width:76%;font-size:12px}.toolbar{padding:0 14px;gap:0}.tabs{gap:19px;width:100%}.tools{margin-left:auto}.caption{padding:11px 14px 0}.viewport{max-height:67vh}.detail{grid-template-columns:1fr;gap:8px;padding:17px}.notes{grid-template-columns:1fr;gap:16px}.legend .hint{width:100%;margin:0}}@media print{@page{size:A3 landscape;margin:10mm}body{background:#fff}header{padding:0 0 12px}main{padding:10px 0}.stamp,.settings,.toolbar,.notes,details,footer,.detail,.legend .hint{display:none}.diagram-shell{border:0}.viewport{max-height:none;overflow:visible;padding:0}.diagram-svg{min-width:0!important;width:100%!important}.caption{padding:0}.legend{padding:4px;border:0}.title{font-size:24px}}
'''
JS=r'''
const data=JSON.parse(document.getElementById('diagram-data').textContent);
let active='overview',zoom=100,selected=null;
const vars=()=>{const dev=document.getElementById('board').value==='200';const ext=document.getElementById('array').value==='extended';return{fpgaShort:dev?'XC7A200T · Artix-7':'XC7A50T · Artix-7',usbShort:dev?'FT601 · USB 3.0':'FT2232H · USB 2.0',usbLong:dev?'FT601 · 32 位 / 100 MHz':'FT2232H · 8 位 / 60 MHz',antenna:ext?'32 × 16 波导阵列':'8 × 16 贴片阵列',frontEnd:ext?'外置 PA 增强方案':'基础阵列方案',routeTitle:ext?'扩展 PA / 收发路由':'基础直连路径',routeSub:ext?'QPA2962 ×16 · T/R':'ADTR1107 ↔ 贴片阵列',routeMeta:ext?'TX 经 PA · RX 经旁路':'不配置外置 QPA2962'}};
const sub=s=>s.replace(/\{(\w+)\}/g,(m,k)=>vars()[k]||m);
function updateText(){document.querySelectorAll('[data-template]').forEach(e=>e.textContent=sub(e.dataset.template));document.querySelectorAll('.block').forEach(e=>{const n=data.graphs.flatMap(g=>g.nodes).find(n=>n.id===e.dataset.id);e.setAttribute('aria-label',sub(n.title)+'，'+sub(n.sub)+'，查看模块详情')});if(selected)showDetails(selected);}
function showDetails(id){selected=id;const n=data.graphs.flatMap(g=>g.nodes).find(n=>n.id===id);document.getElementById('detail-title').textContent=sub(n.title);document.getElementById('detail-text').textContent=n.detail;const links=document.getElementById('detail-links');links.replaceChildren();n.sources.forEach(key=>{const s=data.sources[key],a=document.createElement('a');a.href='../'+s.path;a.textContent=s.title;links.append(a)});document.querySelectorAll('.block').forEach(e=>e.classList.toggle('selected',e.dataset.id===id));}
function setZoom(v){zoom=Math.max(70,Math.min(180,v));document.querySelectorAll('.diagram-svg').forEach(e=>{e.style.width=zoom+'%';e.style.minWidth=(1130*zoom/100)+'px'});document.getElementById('zoom-label').textContent=zoom+'%';}
function setTab(id){active=id;selected=null;document.querySelectorAll('[role=tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab===id)));document.querySelectorAll('.panel').forEach(p=>p.hidden=p.id!=='panel-'+id);document.getElementById('detail-title').textContent='选择一个模块';document.getElementById('detail-text').textContent='点击图中的方框，查看功能、关键型号和资料来源。图中的频率为设计或代码配置值。';document.getElementById('detail-links').replaceChildren();document.querySelectorAll('.selected').forEach(e=>e.classList.remove('selected'));setZoom(100)}
document.querySelectorAll('[role=tab]').forEach(b=>b.addEventListener('click',()=>setTab(b.dataset.tab)));
document.querySelector('.tabs').addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;const bs=[...document.querySelectorAll('[role=tab]')];let i=bs.indexOf(document.activeElement);if(i<0)return;e.preventDefault();i=e.key==='Home'?0:e.key==='End'?bs.length-1:(i+(e.key==='ArrowRight'?1:-1)+bs.length)%bs.length;bs[i].focus();setTab(bs[i].dataset.tab)});
document.querySelectorAll('.block').forEach(e=>{e.addEventListener('click',()=>showDetails(e.dataset.id));e.addEventListener('keydown',k=>{if(k.key==='Enter'||k.key===' '){k.preventDefault();showDetails(e.dataset.id)}})});
document.getElementById('board').addEventListener('change',updateText);document.getElementById('array').addEventListener('change',updateText);
document.getElementById('zoom-in').onclick=()=>setZoom(zoom+15);document.getElementById('zoom-out').onclick=()=>setZoom(zoom-15);document.getElementById('fit').onclick=()=>setZoom(100);document.getElementById('print').onclick=()=>window.print();
document.getElementById('export-svg').onclick=()=>{const svg=document.querySelector('#panel-'+active+' svg').cloneNode(true);svg.querySelectorAll('.selected').forEach(e=>e.classList.remove('selected'));svg.removeAttribute('style');const g=data.graphs.find(g=>g.id===active);svg.setAttribute('width',g.w);svg.setAttribute('height',g.h);svg.querySelectorAll('[tabindex]').forEach(e=>e.removeAttribute('tabindex'));const blob=new Blob([new XMLSerializer().serializeToString(svg)],{type:'image/svg+xml;charset=utf-8'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='AERIS-10-'+active+'-'+document.getElementById('board').value+'-'+document.getElementById('array').value+'.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
'''

def validate_geometry():
 issues=[]
 for g in graphs:
  for n in g['nodes']:
   if min(n['x'],n['y'])<0 or n['x']+n['w']>g['w'] or n['y']+n['h']>g['h']:issues.append((g['id'],n['id'],'bounds'))
  for i,e in enumerate(g['edges']):
   for a,b in zip(e['points'],e['points'][1:]):
    if a[0]!=b[0] and a[1]!=b[1]:issues.append((g['id'],i,'diagonal'))
    for n in g['nodes']:
     x1,y1,x2,y2=n['x']+.1,n['y']+.1,n['x']+n['w']-.1,n['y']+n['h']-.1
     if a[1]==b[1] and y1<a[1]<y2 and max(min(a[0],b[0]),x1)<min(max(a[0],b[0]),x2):issues.append((g['id'],i,n['id'],'through-block'))
     if a[0]==b[0] and x1<a[0]<x2 and max(min(a[1],b[1]),y1)<min(max(a[1],b[1]),y2):issues.append((g['id'],i,n['id'],'through-block'))
   if e['arrow']:
    a,b=e['points'][-2:]
    if abs(a[0]-b[0])+abs(a[1]-b[1])<45:issues.append((g['id'],i,'short-arrow'))
 return issues

def build():
 HERE.mkdir(exist_ok=True)
 assert not validate_geometry(),validate_geometry()
 payload=dict(graphs=graphs,sources=SOURCED,reviewDate='2026-09-28')
 (HERE/'diagram-source.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
 pages=[]
 for i,g in enumerate(graphs):
  s=svg(g);ET.fromstring(s);(HERE/f'{g["id"]}.svg').write_text(s,encoding='utf-8')
  pages.append(f'<section class="panel" id="panel-{g["id"]}" role="tabpanel" aria-labelledby="tab-{g["id"]}"{ " hidden" if i else ""}><p class="caption">{g["caption"]}</p><div class="viewport">{s}</div></section>')
 xml=drawio();tree=ET.fromstring(xml);(HERE/'AERIS-10_system.drawio').write_text(xml,encoding='utf-8')
 tabs=''.join(f'<button type="button" id="tab-{g["id"]}" role="tab" aria-controls="panel-{g["id"]}" aria-selected="{str(i==0).lower()}" data-tab="{g["id"]}">0{i+1} {g["title"]}</button>' for i,g in enumerate(graphs))
 source_rows=''.join(f'<tr><td><a href="../{esc(s["path"])}">{s["title"]}</a></td><td>{s["use"]}</td><td class="path">{esc(s["path"])}<br><code>SHA-256: {s["sha256"][:20]}…</code></td></tr>' for s in SOURCED.values())
 legend=''.join(f'<span><i style="--c:{COLORS[k]}"></i>{v}</span>' for k,v in [('data','数字 / 数据'),('rf','模拟 / 射频'),('ctrl','控制 / 状态'),('clock','时钟 / 本振'),('power','电源')])
 doc=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PLFM_RADAR · AERIS-10 系统框图</title><style>{CSS}</style></head><body>
<header><div class="head"><div><div class="eyebrow">AERIS-10 / ENGINEERING OVERVIEW</div><h1 class="title">PLFM_RADAR 系统框图</h1><p class="subtitle">脉冲线性调频相控阵雷达 · 从整机组成到收发、处理与控制链路</p></div><div class="stamp"><strong>本地设计资料整理</strong>2026.09.28 · v1<br>原理图 + 当前 RTL + 项目说明</div></div></header>
<main><div class="settings"><div class="choices"><label for="board">数字平台 <select id="board"><option value="50">50T 主板 / FT2232H USB 2.0</option><option value="200">200T 开发版 / FT601 USB 3.0</option></select></label><label for="array">阵列方案 <select id="array"><option value="patch">8×16 贴片 / 基础前端</option><option value="extended">32×16 波导 / QPA2962 增强</option></select></label></div><div class="badge">离线可用 · 点击模块查看依据</div></div>
<div class="diagram-shell"><div class="toolbar"><nav class="tabs" role="tablist" aria-label="框图视图">{tabs}</nav><div class="tools"><button id="zoom-out" aria-label="缩小">−</button><output id="zoom-label">100%</output><button id="zoom-in" aria-label="放大">+</button><button id="fit">重置</button><button id="export-svg">导出 SVG</button><button id="print">打印</button></div></div>
{''.join(pages)}<div class="legend">{legend}<span class="hint">双箭头：双向 / 分时收发　·　窄屏可横向滚动</span></div>
<aside class="detail" aria-live="polite"><div><div class="label">MODULE DETAILS</div><h2 id="detail-title">选择一个模块</h2></div><div><p id="detail-text">点击图中的方框，查看功能、关键型号和资料来源。图中的频率为设计或代码配置值。</p><div class="detail-links" id="detail-links"></div></div></aside></div>
<div class="notes"><section><h2>版本关系已分开</h2><p>50T 原理图确认使用 FT2232H，200T 构建脚本选择 FT601；旧框图的 GPS 与 PA 偏置 DAC 已按当前资料改为 UM982 和 DAC5578。数字平台与阵列 / PA 方案分别选择，选项不表示所有组合已验证。</p></section><section><h2>设计目标与实测边界</h2><p>10.5 GHz、ADC 400 MS/s 等来自项目设计资料。MCU 默认设置还保留 10.0 GHz，与概述不同；具体频率配置需整机确认。此图整理文件中的结构，不代表射频性能、探测距离或上板测试通过。</p></section></div>
<details><summary>查看资料依据与文件清单（{len(SOURCED)} 项）</summary><div class="source-table"><table><thead><tr><th>资料</th><th>用于确认</th><th>本地相对路径与摘要</th></tr></thead><tbody>{source_rows}</tbody></table></div></details>
<footer><span>参考风格：原项目 RADAR_V6_V2.png · 原始文件保持不变</span><div class="downloads"><a href="system-block-diagram/AERIS-10_system.drawio">可编辑 draw.io（4 页）</a><a href="system-block-diagram/diagram-source.json">结构化数据与完整哈希</a></div></footer>
<noscript><p>请启用 JavaScript 以切换视图。也可打开附带的 SVG：<a href="system-block-diagram/overview.svg">整机</a> · <a href="system-block-diagram/rf.svg">收发</a> · <a href="system-block-diagram/dsp.svg">FPGA</a> · <a href="system-block-diagram/control.svg">控制</a>。</p></noscript>
</main><script type="application/json" id="diagram-data">{json.dumps(payload,ensure_ascii=False).replace('</','<\\/')}</script><script>{JS}</script></body></html>'''
 OUT.write_text(doc,encoding='utf-8')
 report=dict(geometry_errors=validate_geometry(),pages=len(graphs),vertices=len(tree.findall('.//mxCell[@vertex="1"]')),edges=len(tree.findall('.//mxCell[@edge="1"]')),html_bytes=OUT.stat().st_size,source_hashes_verified=True)
 (HERE/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));print(OUT)

if __name__=='__main__':build()

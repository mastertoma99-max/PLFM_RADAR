"""Render the actual two inner Gerbers with drill holes; annotations are explanatory only."""
from pathlib import Path
import io,json,sys
OUT=Path(__file__).resolve().parent.parent
ROOT=next(x for x in OUT.parents if (x/'.git').exists())
sys.path.insert(0,str(ROOT/'5_Simulations/generated/antenna_4L_cam_tools'))
from gerbonara import GerberFile
from PIL import Image,ImageDraw,ImageFont
import resvg_py
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
nodes=json.loads((OUT/'verification/physical_net_nodes.json').read_text())
canvas=Image.new('RGB',(1460,840),'#0b1722'); draw=ImageDraw.Draw(canvas)
draw.text((26,16),'L2 / L3 地孔连接回读 · J1 区域',font=font(30),fill='white')
draw.text((26,62),'金色为实际铜形；黑色孔洞来自 PTH 钻孔。绿色标注地孔，蓝色标注信号孔。',font=font(21),fill='#c6d2dd')
for idx,(layer,ext) in enumerate([('In1_Cu','g1'),('In2_Cu','g2')]):
    f=OUT/f'cam/Phased_Array_Ant_IPEX1-{layer}.{ext}'
    svg=str(GerberFile.open(f).to_svg(force_bounds=((9.5,6),(19,15.5)),fg='#efc76c',bg='#0b1722'))
    pic=Image.open(io.BytesIO(resvg_py.svg_to_bytes(svg_string=svg,width=660,height=660,dpi=96,background='#0b1722'))).convert('RGB')
    d=ImageDraw.Draw(pic)
    def pt(x,y):return ((x-9.5)*660/9.5,(15.5-y)*660/9.5)
    for v in nodes['vias']:
        if 9.5<v['x']<19 and 6<v['y']<15.5:
            x,y=pt(v['x'],v['y']); r=v['drill']/2*660/9.5
            d.ellipse((x-r,y-r,x+r,y+r),fill='#080b10')
            color='#075d46' if v['net']=='GND' else '#165dce'
            rr=35 if v['net']=='GND' else 43
            d.ellipse((x-rr,y-rr,x+rr,y+rr),outline=color,width=3)
            if v['net']=='GND':
                label='GND 直连'; lx=x-60; ly=y+48
            else:
                label='信号孔：与 GND 隔离'; lx=x-126; ly=y-85
            d.text((lx,ly),label,font=font(23),fill=color)
    left=35+idx*730
    draw.text((left,105),f'L{idx+2} · {layer.replace("_", ".")} · GND',font=font(26),fill='white')
    canvas.paste(pic,(left,151))
draw.text((26,811),'全板逐孔检查：每层 44 个 GND 孔直连、16 个信号孔隔离；本图仅放大 J1 附近。',font=font(19),fill='#c6d2dd')
canvas.save(OUT/'preview/inner_ground_connections.png')

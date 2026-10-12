"""Original teaching diagrams, emitted as editable SVG and portable PNG.

Only Pillow is needed (pinned in requirements-figures.txt). Use --font with a
locally licensed CJK font; font files are never copied into the repository.
All geometry and wording live here. PNG output is rendered from these same
primitives at 2x; SVG text remains editable. No downloaded art, model or API.
"""
from __future__ import annotations
import argparse
import html
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
W=760
C={'ink':'#16263D','muted':'#42556C','blue':'#285AC8','teal':'#087E82','amber':'#9B5E08','red':'#AC343C',
   'bg':'#F6F8FC','line':'#CED8E4','pale_blue':'#EAF0FF','pale_teal':'#E5F5F2','pale_amber':'#FFF3DD','pale_red':'#FDECEE','white':'#FFFFFF'}

class Figure:
    def __init__(self,name,height,title,description,font,scale):
        self.name,self.height,self.font,self.scale=name,height,font,scale
        self.image=Image.new('RGB',(round(W*scale),round(height*scale)),C['bg'])
        self.draw=ImageDraw.Draw(self.image)
        self.svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" role="img" aria-labelledby="title desc">',
          f'<title id="title">{html.escape(title)}</title>',f'<desc id="desc">{html.escape(description)}</desc>',
          f'<rect width="{W}" height="{height}" fill="{C["bg"]}"/>']
        self.text(32,58,title,42)
    def text(self,x,baseline,text,size=30,color='ink'):
        ink=C.get(color,color); font=ImageFont.truetype(self.font,round(size*self.scale))
        xy=(round(x*self.scale),round(baseline*self.scale))
        bbox=self.draw.textbbox(xy,text,font=font,anchor='ls')
        assert bbox[0]>=0 and bbox[2]<=W*self.scale-16*self.scale,(self.name,text,bbox)
        assert bbox[1]>=0 and bbox[3]<=self.height*self.scale,(self.name,text,bbox)
        self.draw.text(xy,text,font=font,fill=ink,anchor='ls')
        self.svg.append(f'<text x="{x}" y="{baseline}" font-size="{size}" fill="{ink}" font-family="Hiragino Sans GB, PingFang SC, Noto Sans CJK SC, Microsoft YaHei, sans-serif">{html.escape(text)}</text>')
    def rect(self,x,y,w,h,fill='white',stroke='line',radius=16):
        a=self.scale
        self.draw.rounded_rectangle((round(x*a),round(y*a),round((x+w)*a),round((y+h)*a)),radius=round(radius*a),fill=C[fill],outline=C[stroke],width=max(1,round(2*a)))
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{C[fill]}" stroke="{C[stroke]}" stroke-width="2"/>')
    def line(self,x1,y1,x2,y2,color='muted',arrow=True,dashed=False):
        a=self.scale;ink=C[color]
        if dashed:
            length=((x2-x1)**2+(y2-y1)**2)**.5
            for at in range(0,round(length),16):
                end=min(at+8,length)
                self.draw.line((round((x1+(x2-x1)*at/length)*a),round((y1+(y2-y1)*at/length)*a),round((x1+(x2-x1)*end/length)*a),round((y1+(y2-y1)*end/length)*a)),fill=ink,width=max(1,round(3*a)))
        else:self.draw.line((round(x1*a),round(y1*a),round(x2*a),round(y2*a)),fill=ink,width=max(1,round(3*a)))
        dash=' stroke-dasharray="8 8"' if dashed else ''
        self.svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{ink}" stroke-width="3"{dash}/>')
        if arrow:
            import math
            angle=math.atan2(y2-y1,x2-x1)
            pts=[(x2,y2)]+[(x2-12*math.cos(angle+t),y2-12*math.sin(angle+t)) for t in [-.5,.5]]
            self.draw.polygon([(round(x*a),round(y*a)) for x,y in pts],fill=ink)
            self.svg.append(f'<polygon points="{" ".join(f"{x:.2f},{y:.2f}" for x,y in pts)}" fill="{ink}"/>')
    def save(self,out,svg=True):
        out.mkdir(parents=True,exist_ok=True)
        self.image.save(out/(self.name+'.png'),optimize=True)
        if svg:(out/(self.name+'.svg')).write_text('\n'.join(self.svg+['</svg>'])+'\n')

def figures(font,scale,out,svg=True):
    f=Figure('01-code-evidence-layer',1220,'代码索引要交付什么？','开发助手的建议分工，非现成功能或实测输出。Microsoft GraphRAG从文本抽取关系并检索候选材料；路径版本和程序事实需要回到源码核对。编辑、执行测试和补丁审查属于下游系统。',font,scale)
    f.text(32,104,'先找对证据，再让开发助手修改代码。',28,'muted')
    rows=[('1  固定一份代码快照','输入还应包括相关测试和项目约定。','明确目录、版本，以及哪些文件未纳入。','white','line'),
          ('2  Microsoft GraphRAG 整理与检索','文本分块 → 抽取实体关系 → 选取材料','社区报告是辅助材料，不是调用证明。','pale_blue','blue'),
          ('3  得到候选证据，回查源码','核对函数身份、位置、调用方向和条件。','还要检查遗漏的调用者、测试与旧版本。','pale_amber','amber'),
          ('4  下游工具编辑、测试与审查','同一份证据交给编辑模型或开发者。','找到材料、写出补丁、改对，是三件事。','pale_teal','teal')]
    for i,(title,a,b,fill,stroke) in enumerate(rows):
        y=145+i*221;f.rect(32,y,696,182,fill,stroke)
        f.text(54,y+43,title,30);f.text(54,y+93,a,28);f.text(54,y+139,b,27,'muted')
        if i<3:f.line(380,y+188,380,y+214)
    f.text(32,1090,'第 3、4 步是开发助手额外负责的工作。',28,'teal')
    f.text(32,1137,'不是微软默认索引自带的正确性保证。',28)
    f.text(32,1181,'教学分工示意；本轮未运行微软模型。',26,'muted')
    f.save(out,svg)

    f=Figure('02-feature-context',1380,'实现一个小功能，要找什么？','人工阅读原创小店代码所得的教学图，不是GraphRAG输出。需求是从下单入口指定回执主题，保持默认兼容。place_order调用confirm_order，后者调用make_receipt。需要现有测试和约定，analytics.order_count不在此链路。feature尚未实现。',font,scale)
    f.text(32,105,'需求：从下单入口指定回执主题，默认不变。',26,'muted')
    rows=[('checkout.place_order','入口怎样接收新参数？旧调用还兼容吗？'),
          ('orders.confirm_order','中间层是否需要继续传递参数？'),
          ('mailer.make_receipt','主题在这里形成；这里只返回回执数据。')]
    for i,(title,line) in enumerate(rows):
        y=155+i*183;f.rect(32,y,696,140,'pale_teal','teal')
        f.text(56,y+49,title,31);f.text(56,y+103,line,27)
        if i<2:f.line(380,y+147,380,y+177,'teal')
    f.text(32,726,'实线向下是源码调用；分析影响还要反向找。',26)
    f.rect(32,771,696,190,'pale_blue','blue')
    f.text(56,816,'还需要：测试与项目约定',31,'blue')
    f.text(56,863,'test_shop.py：旧入口、默认主题、订单不变',25)
    f.text(56,909,'CONVENTIONS.md：兼容、只返回数据、不发信',24)
    f.rect(32,1001,696,141,'pale_amber','amber')
    f.text(56,1048,'干扰材料：analytics.order_count',29,'amber')
    f.text(56,1099,'也谈订单，但不在这条待改调用链上。',28)
    f.text(32,1208,'需新增测试：自定义主题从入口传至回执。',27)
    f.text(32,1257,'这是所需证据清单，不是微软已检索到的结果。',25,'red')
    f.text(32,1306,'当前例子停在新功能实现前；本轮未做改码实验。',24,'muted')
    f.save(out,svg)

    f=Figure('03-identity-and-freshness',1220,'名字相同，代码也可能不同','两类源码机制的教学示意，不是运行实验。默认实体名称合并不保证区别同名符号；v3.3.0标准update按文档title识别新增，同title内容修改不会进入新增集合，删除也不由该默认合并路径同步清除。',font,scale)
    f.text(32,104,'代码索引需要身份，也需要与当前版本一致。',27,'muted')
    f.rect(32,151,696,348,'pale_blue','blue')
    f.text(56,199,'第一关：这是哪一个 send？',32,'blue')
    f.text(56,255,'billing.py::send    /    alerts.py::send',28)
    f.text(56,307,'若都抽成 SEND ＋ 同一类型，就会合并。',27)
    f.text(56,362,'原版按名称键处理，不自动绑定文件和签名。',26)
    f.text(56,418,'提示词能提供线索，但不能保证可靠消歧。',26)
    f.text(56,465,'这里是机制风险，不是已测出的错误率。',25,'muted')
    f.rect(32,545,696,421,'pale_amber','amber')
    f.text(56,594,'第二关：索引看到的还是旧代码吗？',31,'amber')
    f.text(56,651,'v1：mailer.py 已在索引中',29)
    f.text(56,706,'v2：同名文件里的函数已经修改',29)
    f.text(56,766,'标准更新按文档标题（title）判断新增。',27)
    f.text(56,819,'标题相同、内容改了，也不算新增。',26)
    f.text(56,873,'删除源码后，该路径不清除旧索引记录。',27)
    f.text(56,928,'有更新命令，不等于能同步所有代码变化。',25,'muted')
    f.text(32,1047,'使用前要核对：代码版本、来源范围、更新覆盖。',26,'teal')
    f.text(32,1101,'全量重建或自定义同步也需单独验证。',28)
    f.text(32,1157,'固定版本 v3.3.0 源码核查；不是实测截图。',26,'muted')
    f.save(out,svg)

    f=Figure('04-three-variants',1190,'三种方案，不能混称原版能力','Microsoft GraphRAG默认文本图、代码提示词定制、外接程序分析图是三个不同配置。外接图的程序语义来自外部分析器，GraphRAG下游仍需验证身份方向和来源映射是否保留；收益需与外部图单独使用比较。',font,scale)
    f.text(32,104,'同样叫 GraphRAG，证据从哪里来很关键。',28,'muted')
    rows=[('A  原版默认流程','模型从文本解释实体和关系。','不是内置的函数／调用／影响集合分析器。','pale_blue','blue'),
          ('B  定制代码提示词','让模型抽函数、类，提供路径等线索。','仍是模型抽取；不会自动验证函数身份与调用。','pale_amber','amber'),
          ('C  外接程序分析图','先由外部工具生成定义、引用、调用等。','这部分语义来自外部工具；接入后仍需核查。','pale_teal','teal')]
    for i,(title,a,b,fill,stroke) in enumerate(rows):
        y=160+i*262;f.rect(32,y,696,212,fill,stroke)
        f.text(56,y+49,title,32);f.text(56,y+106,a,28);f.text(56,y+164,b,26)
    f.text(32,974,'定制要公开：版本、输入格式与字段含义、改动。',26)
    f.text(32,1033,'C 还应比较：同一外部代码图单独使用会怎样？',25,'teal')
    f.text(32,1091,'不能拿改造系统的好成绩证明 A 已有同等能力。',25,'red')
    f.text(32,1144,'方案边界示意；收益均须按目标任务实测。',27,'muted')
    f.save(out,svg)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--font');ap.add_argument('--preview',action='store_true');a=ap.parse_args()
    fonts=[a.font,'/System/Library/Fonts/Hiragino Sans GB.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    font=next((p for p in fonts if p and Path(p).is_file()),None)
    if not font:ap.error('Supply --font with a locally installed CJK font; no font is redistributed.')
    figures(font,2,ROOT/'docs/figures')
    if a.preview:figures(font,390/W,ROOT/'.cache/figure-previews',svg=False)
    print('Generated 4 SVG + 4 PNG teaching diagrams; CJK font:',Path(font).name)
if __name__=='__main__':main()

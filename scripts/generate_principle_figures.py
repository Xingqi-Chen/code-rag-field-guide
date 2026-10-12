"""Original teaching diagrams, emitted as editable SVG and portable PNG.

Only Pillow is needed (already in requirements.lock.txt). Use --font with a
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
    f=Figure('01-search-and-relations',1190,'从“找相似”到“查关系”','教学示例。普通检索可命中下单和统计，也可能直接命中回执。图从下单入口沿明确的调用边找到确认和回执；统计代码不因词语相似就成为调用邻居。',font,scale)
    f.text(32,104,'教学示例：下单后，谁生成回执？',30,'muted')
    f.rect(32,132,696,270,'pale_blue','blue')
    f.text(56,179,'普通检索：按词语或意思找',34,'blue')
    f.text(56,227,'可能找到：下单代码、订单统计')
    f.text(56,272,'也可能直接找到：回执代码')
    f.text(56,323,'像查图书馆目录：先找相关章节')
    f.text(56,368,'“内容相近”不代表“彼此调用”',28,'blue')
    f.text(32,465,'加上代码图：从入口顺着关系查',34,'teal')
    for y,file,fn,label in [(498,'checkout.py','place_order()','入口：下单'),(688,'orders.py','confirm_order()','确认订单'),(878,'mailer.py','make_receipt()','生成回执')]:
        f.rect(64,y,632,140,'pale_teal','teal')
        f.text(88,y+43,label,32,'teal');f.text(88,y+83,file,29);f.text(88,y+120,fn,29)
    for y in [638,828]:
        f.line(380,y+6,380,y+44,'teal');f.text(408,y+36,'调用',28,'teal')
    f.text(32,1074,'箭头：A 的代码里调用了 B。',30)
    f.text(32,1120,'没画边的订单统计，不会自动接入。',30)
    f.text(32,1163,'它仍可能被普通检索返回。图也可能漏边。',26,'muted')
    f.save(out,svg)

    f=Figure('02-five-steps',1160,'图怎样参与一次回答','教学流程分五步：先按固定版本建图，收到问题后搜索入口，有限沿边扩展，按预算选择原始证据，最后由模型阅读并附来源。本仓库实验只测检索，不执行最后的回答生成。',font,scale)
    f.text(32,104,'先找资料，再让模型阅读资料。',30,'muted')
    steps=[('1  建图','读取固定版本，识别函数和调用。','地图保留文件名、行号和边的依据。','pale_blue','blue'),
           ('2  找入口','用关键词或语义检索定位下单代码。','入口找错，沿图走也可能越走越偏。','white','line'),
           ('3  沿边扩展','从下单查到确认，再查到回执。','这是两跳示意；实际系统要限制跳数。','pale_teal','teal'),
           ('4  选证据','回到原代码，去重并比较相关性。','背包有限：保护关键证据，舍弃噪声。','white','line'),
           ('5  回答并附来源','模型依据选中的代码组织解释。','来源指向版本、文件和具体行。','pale_amber','amber')]
    for i,(title,a,b,fill,stroke) in enumerate(steps):
        y=132+i*188
        f.rect(32,y,696,156,fill,stroke)
        f.text(56,y+43,title,34)
        f.text(56,y+88,a,28)
        f.text(56,y+130,b,28,'muted')
        if i<4:f.line(380,y+160,380,y+183,'muted')
    f.text(32,1100,'本仓库：只测检索，未运行第 5 步。',30,'amber')
    f.text(32,1140,'本地实验只扩展一跳；上图两跳用于教学。',26,'muted')
    f.save(out,svg)

    f=Figure('03-failures-and-budget',1210,'地图会出错，背包也会满','教学反例：同名函数可能造成错误边；动态调用可能漏边；通用日志工具会增加噪声；在四块示意预算中，新增邻居可能挤掉关键的回执证据。没有图边不证明运行时没有调用。',font,scale)
    f.text(32,104,'多拿邻居，不保证多拿到有用证据。',30,'muted')
    f.rect(32,132,696,208,'pale_red','red')
    f.text(56,177,'错误边：认错同名函数',34,'red')
    f.text(56,224,'本应调用回执函数，却连到测试替身。',28)
    f.text(56,275,'订单确认',29);f.line(210,269,445,269,'red',True,True);f.text(466,275,'错误目标',29,'red')
    f.text(56,315,'修法：核对定义身份和调用位置。',28)
    f.rect(32,364,696,162,'white','line')
    f.text(56,407,'遗漏：运行时才决定调用谁',34)
    f.text(56,452,'插件、回调、反射可能让静态图漏边。',28)
    f.text(56,498,'没查到关系，不等于关系不存在。',28,'muted')
    f.rect(32,550,696,152,'white','line')
    f.text(56,593,'噪声：路很多，却未必通向答案',32)
    f.text(56,638,'日志、通用工具可能连接很多函数。',28)
    f.text(56,678,'连得多，不表示与这次问题更相关。',28,'muted')
    f.rect(32,726,696,372,'pale_amber','amber')
    f.text(56,770,'预算：背包只能装 4 块',34,'amber')
    f.text(56,816,'原先已选：',29)
    for i,label in enumerate(['入口','确认','回执','配置']):
        f.rect(56+i*165,838,148,58,'white','teal',8);f.text(71+i*165,877,label,30,'teal')
    f.text(56,940,'如果邻居挤掉回执：',29)
    for i,label in enumerate(['入口','确认','日志','工具']):
        f.rect(56+i*165,960,148,58,'white','red' if i>1 else 'teal',8);f.text(71+i*165,999,label,30,'red' if i>1 else 'teal')
    f.text(56,1067,'材料数量相同，关键证据反而变少。',28,'amber')
    f.text(32,1146,'4 块是教学预算；主实验预算是 8 块。',28,'muted')
    f.text(32,1184,'应比较同预算结果，不能默认扩展就有益。',26,'muted')
    f.save(out,svg)

    f=Figure('04-two-kinds-of-graph',1110,'两种图，不要混为一谈','代码结构图的节点是函数或文件，边是调用引用等程序关系。本实验使用简单的代码块结构扩展。Microsoft GraphRAG的典型文档流程则抽取实体关系，将相关实体分为社区并生成摘要；两者都需要回查原始来源。',font,scale)
    f.text(32,104,'Graph 都是“事物＋关系”，来源不同。',29,'muted')
    f.rect(32,134,696,356,'pale_teal','teal')
    f.text(56,181,'代码结构图',36,'teal')
    f.text(56,229,'点：函数、类、文件或代码块',30)
    f.text(56,273,'线：调用、引用、导入等关系',30)
    f.text(56,323,'下单函数',29);f.line(210,315,445,315,'teal');f.text(466,323,'确认函数',29)
    f.text(56,372,'主要从代码解析；也可能漏连或误连。',28)
    f.text(56,421,'本实验：简单结构图＋有限扩展检索。',28,'teal')
    f.text(56,465,'没有让 LLM 建文档实体图或写社区摘要。',26,'muted')
    f.rect(32,518,696,432,'pale_blue','blue')
    f.text(56,565,'文档实体图与社区摘要',34,'blue')
    f.text(56,614,'典型 Microsoft GraphRAG 流程：',29)
    stages=[('文档','抽取实体与关系'),('社区','把关联紧密的实体分组'),('摘要','为这些组归纳主要内容')]
    for i,(a,b) in enumerate(stages):
        y=646+i*74
        f.text(72,y+29,a,31,'blue');f.text(180,y+29,b,28)
        if i<2:f.line(108,y+37,108,y+62,'blue')
    f.text(56,903,'可帮助跨文档概括；还有其他查询模式。',27)
    f.text(32,1008,'两者都要回查原文、版本和出处。',30)
    f.text(32,1056,'有图、有摘要，都不保证答案正确。',30,'red')
    f.text(32,1093,'这里是机制说明，不是商业产品效果排名。',26,'muted')
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

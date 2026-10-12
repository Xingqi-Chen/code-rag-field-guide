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
    f=Figure('01-ms-graphrag-pipeline',1360,'它先整理资料，再回答','Microsoft GraphRAG标准流程的教学示意，并非实测输出。输入文本，切块，模型抽取实体与关系，算法划分社区，模型写社区报告，最后按问题选择查询方式。关系不等于经程序分析验证的调用。',font,scale)
    f.text(32,103,'像整理一柜资料：做卡片、分组、写导读。',28,'muted')
    steps=[('1  输入材料','代码可以作为文本读入，文档也可以。','要配置读取范围，并保留文件和版本。','white','line'),
           ('2  切成小段','默认按文字长度切，不是按函数切。','每段称为 TextUnit，方便模型处理。','white','line'),
           ('3  提取事物与关系','模型读每段，写实体卡片和关系说明。','这是从文本理解出的关联，可能出错。','pale_blue','blue'),
           ('4  把关系紧密的事物分组','算法在图上划分社区，还可形成层级。','社区只是分组，不保证就是代码模块。','pale_teal','teal'),
           ('5  为分组写报告','模型把相关材料整理成社区报告。','导读便于概括，但可能丢失代码细节。','pale_blue','blue'),
           ('6  收到问题后选查询方式','可查原文、实体附近材料，或社区报告。','选好的材料再交给模型组织回答。','pale_amber','amber')]
    for i,(title,a,b,fill,stroke) in enumerate(steps):
        y=130+i*187
        f.rect(32,y,696,155,fill,stroke)
        f.text(56,y+44,title,32);f.text(56,y+88,a,28);f.text(56,y+130,b,27,'muted')
        if i<5:f.line(380,y+160,380,y+182)
    f.text(32,1305,'蓝色标出抽取与报告；最后回答也调用模型。',27,'blue')
    f.text(32,1344,'教学图；本轮未运行这套索引与回答流程。',26,'muted')
    f.save(out,svg)

    f=Figure('02-query-modes',1200,'四种查资料的方式','查询模式教学示意。Basic检索原始文本，Local围绕实体结合关系和原文，Global用社区报告概括全局，DRIFT结合社区概览与进一步局部查询。示例问题不是评测成绩，更多步骤不保证更准确。',font,scale)
    f.text(32,103,'同一套资料，不同问题要用不同入口。',29,'muted')
    modes=[('Basic｜按意思找原文','像查相关章节，主要用文本向量检索。','例如：回执数据里放了哪些字段？','pale_blue','blue'),
           ('Local｜围绕一个事物找','先定位实体，再取关系和相关原文等。','例如：订单确认与哪些功能有关？','pale_teal','teal'),
           ('Global｜先读各组导读','用社区报告组织整体概括。','例如：这套系统大致有哪些职责？','pale_blue','blue'),
           ('DRIFT｜概览后继续追问','结合社区信息与多轮局部查询。','例如：从下单到回执还缺哪些线索？','pale_teal','teal')]
    for i,(title,a,b,fill,stroke) in enumerate(modes):
        y=139+i*224;f.rect(32,y,696,194,fill,stroke)
        f.text(56,y+49,title,33);f.text(56,y+100,a,28);f.text(56,y+148,b,28)
    f.text(32,1084,'这些是查询思路和教学问题，不是实测。',28)
    f.text(32,1130,'Global 不等于逐行检查了全仓代码。',29,'red')
    f.text(32,1173,'多轮、多材料，也不保证回答更准确。',27,'muted')
    f.save(out,svg)

    f=Figure('03-code-is-not-a-call-graph',1280,'读懂关联，不等于验证调用','原创小店教学示例：orders中的confirm_order调用mailer中的make_receipt，但后者只返回回执数据。模型可能概括成通知客户，不能把这种假设当源码事实。同名符号、动态选择与摘要都会带来额外风险。',font,scale)
    f.text(32,104,'同一个小店例子：确认订单后生成回执。',28,'muted')
    f.rect(32,134,696,225,'pale_teal','teal')
    f.text(56,179,'源码能直接支持的事实',34,'teal')
    f.text(56,229,'confirm_order → make_receipt',30)
    f.text(56,276,'make_receipt 只返回一份回执数据。',28)
    f.text(56,321,'这段示例没有发送邮件，也没有支付。',28)
    f.line(380,369,380,412,'muted',True,True)
    f.rect(32,430,696,219,'pale_amber','amber')
    f.text(56,478,'模型可能写出的概括',34,'amber')
    f.text(56,526,'“订单确认后会通知客户”',32)
    f.text(56,575,'听起来合理，却超出了这段源码。',29)
    f.text(56,621,'这是风险示意，不是微软系统实测输出。',26,'muted')
    risks=[('同名函数','不同文件的 send，可能被混成一个实体。'),
           ('动态调用','运行时才决定目标，文字关系图未必知道。'),
           ('摘要压缩','漏掉 if、异常或参数，流程就可能讲错。')]
    for i,(a,b) in enumerate(risks):
        y=681+i*150;f.rect(32,y,696,126)
        f.text(56,y+43,a,32);f.text(56,y+89,b,27,'muted')
    f.text(32,1193,'要追调用：回查定义、导入、条件和原文。',28,'teal')
    f.text(32,1241,'图中的线，是待核对的证据线索。',30)
    f.save(out,svg)

    f=Figure('04-communities-and-reports',1230,'从关系卡片到社区导读','人为教学假设，不是Microsoft GraphRAG真实输出。下单、确认、回执等实体可通过关系连接；算法可能划分为订单处理和订单统计两个社区，再由模型为社区写报告。社区不是源码文件夹，也不是经过程序分析验证的模块边界。',font,scale)
    f.text(32,104,'假想整理结果；不是微软系统的运行输出。',27,'muted')
    f.rect(32,145,332,520,'pale_teal','teal')
    f.rect(396,145,332,520,'pale_blue','blue')
    f.text(57,191,'社区 A：订单处理',29,'teal');f.text(421,191,'社区 B：订单统计',29,'blue')
    f.line(198,300,198,365,'teal',False);f.line(198,435,198,500,'teal',False)
    f.line(562,370,562,460,'blue',False);f.line(318,400,442,335,'muted',False)
    for x,y,label in [(78,230,'下单'),(78,365,'确认'),(78,500,'回执'),(442,300,'统计'),(442,460,'订单数量')]:
        f.rect(x,y,240,70,'white','line',12);f.text(x+32,y+47,label,31)
    f.text(56,621,'关联紧密的一组事物',26,'teal');f.text(420,621,'不是源码文件夹',26,'blue')
    f.text(32,714,'点是事物，线是提取出的关联。',30)
    f.text(32,759,'社区由算法划分，不保证就是代码模块。',28,'muted')
    f.line(198,791,198,837,'teal');f.line(562,791,562,837,'blue')
    f.rect(32,860,332,187,'pale_teal','teal');f.rect(396,860,332,187,'pale_blue','blue')
    f.text(56,908,'社区报告 A',32,'teal');f.text(420,908,'社区报告 B',32,'blue')
    f.text(56,958,'“下单、确认与',28);f.text(56,1002,'回执有关联……”',28)
    f.text(420,958,'“统计功能涉及',28);f.text(420,1002,'订单数量……”',28)
    f.text(32,1100,'模型为分组写导读，Global 可据此概括。',28)
    f.text(32,1150,'导读可能省略条件和细节，仍要回查原文。',27,'red')
    f.text(32,1197,'图中的具体分组与报告，全部为教学假设。',27,'muted')
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

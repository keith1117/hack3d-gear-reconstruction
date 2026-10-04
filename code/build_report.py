from pathlib import Path
from html import escape
import re

from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak


ROOT = Path(__file__).resolve().parents[1]
FONT = 'Times-Roman'
BOLD = 'Times-Bold'
font_folder = Path('/System/Library/Fonts/Supplemental')
if (font_folder / 'Times New Roman.ttf').exists():
    pdfmetrics.registerFont(TTFont('TNR', str(font_folder / 'Times New Roman.ttf')))
    pdfmetrics.registerFont(TTFont('TNR-Bold', str(font_folder / 'Times New Roman Bold.ttf')))
    pdfmetrics.registerFontFamily('TNR', normal='TNR', bold='TNR-Bold')
    FONT, BOLD = 'TNR', 'TNR-Bold'


def build(source, destination, weekly=False):
    styles = {
        'title': ParagraphStyle('title', fontName=BOLD, fontSize=16, leading=19, spaceAfter=5),
        'heading': ParagraphStyle('heading', fontName=BOLD, fontSize=12, leading=15,
                                  spaceBefore=4, spaceAfter=5),
        'body': ParagraphStyle('body', fontName=FONT, fontSize=12 if weekly else 11,
                               leading=16 if weekly else 14, spaceAfter=9),
        'caption': ParagraphStyle('caption', fontName=FONT, fontSize=10, leading=12, spaceAfter=7)
    }
    story = []
    for block in source.read_text().strip().split('\n\n'):
        if block == '<!-- pagebreak -->':
            story.append(PageBreak())
        elif block.startswith('!['):
            path = ROOT / re.search(r'\]\((.*?)\)', block).group(1)
            picture = Image(str(path))
            picture.drawHeight *= 468 / picture.imageWidth
            picture.drawWidth = 468
            story.append(picture)
            story.append(Spacer(1, 5))
        else:
            key = 'body'
            if block.startswith('# '):
                key, block = 'title', block[2:]
            elif block.startswith('## '):
                key, block = 'heading', block[3:]
            elif block.startswith('Figure '):
                key = 'caption'
            text = escape(block.replace('\n', ' '))
            if text.startswith('GitHub Repository: '):
                url = text.split(' ', 2)[2]
                text = 'GitHub Repository: <link href="' + url + '">' + url + '</link>'
            story.append(Paragraph(text, styles[key]))
    document = SimpleDocTemplate(str(destination), pagesize=(612, 792),
                                 leftMargin=72, rightMargin=72, topMargin=72, bottomMargin=60)
    document.build(story)


if __name__ == '__main__':
    build(ROOT / 'report.md', ROOT / 'report.pdf')
    build(ROOT / 'weekly_update.md', ROOT / 'weekly_update.pdf', weekly=True)

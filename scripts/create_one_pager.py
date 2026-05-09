#!/usr/bin/env python3
"""Generate AllowED sales one-pager PDF."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable)
from reportlab.lib import colors

# Brand colors
DARK = HexColor("#0F172A")
BLUE = HexColor("#1E40AF")
ORANGE = HexColor("#F97316")
GREEN = HexColor("#10B981")
SLATE_50 = HexColor("#F8FAFC")
SLATE_100 = HexColor("#F1F5F9")
SLATE_200 = HexColor("#E2E8F0")
SLATE_400 = HexColor("#94A3B8")
SLATE_600 = HexColor("#475569")
SLATE_700 = HexColor("#334155")
WHITE = HexColor("#FFFFFF")

W, H = letter
MARGIN = 0.6 * inch

doc = SimpleDocTemplate(
    "/sessions/keen-fervent-ptolemy/mnt/AllowED/AllowED_One_Pager.pdf",
    pagesize=letter,
    topMargin=0.4*inch, bottomMargin=0.4*inch,
    leftMargin=MARGIN, rightMargin=MARGIN,
)

# Styles
sTitle = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=26, textColor=ORANGE, leading=30, alignment=TA_LEFT)
sTagline = ParagraphStyle("tagline", fontName="Helvetica", fontSize=13, textColor=SLATE_600, leading=17, alignment=TA_LEFT)
sSection = ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=12, textColor=BLUE, leading=16, spaceBefore=14, spaceAfter=6)
sBody = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, textColor=DARK, leading=13)
sBodyBold = ParagraphStyle("bodybold", fontName="Helvetica-Bold", fontSize=9.5, textColor=DARK, leading=13)
sSmall = ParagraphStyle("small", fontName="Helvetica", fontSize=8, textColor=SLATE_400, leading=11)
sStatNum = ParagraphStyle("statnum", fontName="Helvetica-Bold", fontSize=22, textColor=BLUE, leading=26, alignment=TA_CENTER)
sStatLabel = ParagraphStyle("statlabel", fontName="Helvetica", fontSize=8, textColor=SLATE_600, leading=11, alignment=TA_CENTER)
sCTA = ParagraphStyle("cta", fontName="Helvetica-Bold", fontSize=11, textColor=WHITE, leading=14, alignment=TA_CENTER)
sCTASub = ParagraphStyle("ctasub", fontName="Helvetica", fontSize=9, textColor=HexColor("#CBD5E1"), leading=12, alignment=TA_CENTER)
sQuote = ParagraphStyle("quote", fontName="Helvetica-Oblique", fontSize=10, textColor=SLATE_700, leading=14, leftIndent=8, rightIndent=8)

story = []

# === HEADER ===
header_data = [[
    Paragraph("Allow<font color='#F97316'><b>ED</b></font>", ParagraphStyle("logo", fontName="Helvetica-Bold", fontSize=22, textColor=DARK, leading=26)),
    Paragraph("allowedcert.com", ParagraphStyle("url", fontName="Helvetica", fontSize=9, textColor=BLUE, leading=12, alignment=TA_RIGHT)),
]]
header_table = Table(header_data, colWidths=[4*inch, 3.3*inch])
header_table.setStyle(TableStyle([
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('BOTTOMPADDING', (0,0), (-1,-1), 0),
]))
story.append(header_table)
story.append(Spacer(1, 4))
story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceBefore=0, spaceAfter=8))

# === TITLE + TAGLINE ===
story.append(Paragraph("VA Certification, Automated.", sTitle))
story.append(Spacer(1, 2))
story.append(Paragraph("AllowED replaces spreadsheets, dual screens, and 15-minute-per-student manual workflows with an AI-powered engine that certifies veteran enrollments automatically.", sTagline))
story.append(Spacer(1, 10))

# === STAT BOXES ===
def stat_cell(num, label):
    return [Paragraph(num, sStatNum), Paragraph(label, sStatLabel)]

stats_data = [[
    stat_cell("93%", "Time Savings"),
    stat_cell("525→35", "SCO Hours/Semester"),
    stat_cell("$24,500", "Savings/Semester"),
    stat_cell("4,000+", "Target Schools"),
]]

# Flatten for table
stats_row = []
for cell_content in stats_data[0]:
    stats_row.append(Table([[cell_content[0]], [cell_content[1]]], colWidths=[1.75*inch]))

stats_table = Table([stats_row], colWidths=[1.825*inch]*4)
stats_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), SLATE_50),
    ('BOX', (0,0), (0,0), 0.5, SLATE_200),
    ('BOX', (1,0), (1,0), 0.5, SLATE_200),
    ('BOX', (2,0), (2,0), 0.5, SLATE_200),
    ('BOX', (3,0), (3,0), 0.5, SLATE_200),
    ('TOPPADDING', (0,0), (-1,-1), 8),
    ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
]))
story.append(stats_table)
story.append(Spacer(1, 12))

# === TWO COLUMN LAYOUT: BEFORE/AFTER + HOW IT WORKS ===
# Before / After
story.append(Paragraph("The Problem", sSection))
story.append(Paragraph(
    "School Certifying Officials manually process every VA enrollment certification. "
    "At SDSU alone, that's <b>2,100 students per semester</b> — each requiring 15 minutes of "
    "cross-referencing PeopleSoft, DARS, WEAMS, and VA Enrollment Manager across dual screens. "
    "One SCO. 525 hours. Every semester. And one mistake means a VA audit.",
    sBody))
story.append(Spacer(1, 8))

# Before/After comparison table
ba_data = [
    [Paragraph("<b>BEFORE AllowED</b>", ParagraphStyle("bah", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE, leading=12)),
     Paragraph("<b>AFTER AllowED</b>", ParagraphStyle("bah", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE, leading=12))],
    [Paragraph("15 min per student, manual entry", sBody), Paragraph("<b>&lt;1 min per student</b>, automated", sBody)],
    [Paragraph("Dual-screen PeopleSoft + EM workflow", sBody), Paragraph("<b>Single workstation</b>, all data unified", sBody)],
    [Paragraph("Spreadsheet tracking, error-prone", sBody), Paragraph("<b>Real-time dashboard</b>, batch certification", sBody)],
    [Paragraph("Manual WEAMS cross-reference", sBody), Paragraph("<b>6,543 programs auto-matched</b> with confidence scoring", sBody)],
    [Paragraph("SCO catches errors by memory", sBody), Paragraph("<b>63-check decision tree</b> catches everything", sBody)],
    [Paragraph("Audit = weeks of pulling records", sBody), Paragraph("<b>Full audit trail</b>, every decision traceable", sBody)],
]

ba_table = Table(ba_data, colWidths=[3.65*inch, 3.65*inch])
ba_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (0,0), HexColor("#DC2626")),
    ('BACKGROUND', (1,0), (1,0), GREEN),
    ('TEXTCOLOR', (0,0), (-1,0), WHITE),
    ('BACKGROUND', (0,1), (0,-1), HexColor("#FEF2F2")),
    ('BACKGROUND', (1,1), (1,-1), HexColor("#F0FDF4")),
    ('BOX', (0,0), (-1,-1), 0.5, SLATE_200),
    ('INNERGRID', (0,0), (-1,-1), 0.5, SLATE_200),
    ('TOPPADDING', (0,0), (-1,-1), 5),
    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ('LEFTPADDING', (0,0), (-1,-1), 8),
    ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
]))
story.append(ba_table)
story.append(Spacer(1, 12))

# === HOW IT WORKS ===
story.append(Paragraph("How It Works", sSection))

steps_data = [
    [Paragraph("<b>1</b>", ParagraphStyle("stepnum", fontName="Helvetica-Bold", fontSize=14, textColor=WHITE, alignment=TA_CENTER)),
     Paragraph("<b>Connect</b><br/>AllowED reads enrollment data from PeopleSoft, Ellucian, or CSV upload. No SIS changes required.", sBody)],
    [Paragraph("<b>2</b>", ParagraphStyle("stepnum", fontName="Helvetica-Bold", fontSize=14, textColor=WHITE, alignment=TA_CENTER)),
     Paragraph("<b>Automate</b><br/>7-step decision tree evaluates every course against VA rules: DARS, WEAMS, modality, training time, rate of pursuit. 63 checks per student.", sBody)],
    [Paragraph("<b>3</b>", ParagraphStyle("stepnum", fontName="Helvetica-Bold", fontSize=14, textColor=WHITE, alignment=TA_CENTER)),
     Paragraph("<b>Certify</b><br/>Clean enrollments batch-certify in one click. Flagged students route to SCO review queue. Amendments auto-generate. Submit to VA via API.", sBody)],
]

steps_table = Table(steps_data, colWidths=[0.45*inch, 6.85*inch])
steps_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (0,0), BLUE),
    ('BACKGROUND', (0,1), (0,1), BLUE),
    ('BACKGROUND', (0,2), (0,2), BLUE),
    ('BACKGROUND', (1,0), (1,-1), SLATE_50),
    ('BOX', (0,0), (-1,-1), 0.5, SLATE_200),
    ('INNERGRID', (0,0), (-1,-1), 0.5, SLATE_200),
    ('TOPPADDING', (0,0), (-1,-1), 8),
    ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ('LEFTPADDING', (0,0), (0,-1), 6),
    ('LEFTPADDING', (1,0), (1,-1), 10),
    ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
]))
story.append(steps_table)
story.append(Spacer(1, 12))

# === QUOTE ===
story.append(Paragraph(
    '"I built AllowED because nobody else who\'s building VA tech has ever sat in the SCO chair. '
    'Every rule in this system comes from 2,100 certifications per semester — not a whiteboard."',
    sQuote))
story.append(Paragraph("— Paulina Enriquez, SCO at San Diego State University & Founder, AllowED", 
    ParagraphStyle("quoteattr", fontName="Helvetica-Bold", fontSize=8.5, textColor=SLATE_600, leading=12, leftIndent=8)))
story.append(Spacer(1, 12))

# === TRACTION ===
story.append(Paragraph("Platform Status", sSection))
traction_data = [
    [Paragraph("<b>Feature</b>", ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE)),
     Paragraph("<b>Status</b>", ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE))],
    [Paragraph("7-step decision tree (63 checks)", sBody), Paragraph("✓  Live", ParagraphStyle("g", fontName="Helvetica-Bold", fontSize=9, textColor=GREEN))],
    [Paragraph("WEAMS crosswalk (6,543 programs, 25 schools)", sBody), Paragraph("✓  Live", ParagraphStyle("g", fontName="Helvetica-Bold", fontSize=9, textColor=GREEN))],
    [Paragraph("SCO Workstation with Supabase backend", sBody), Paragraph("✓  Live", ParagraphStyle("g", fontName="Helvetica-Bold", fontSize=9, textColor=GREEN))],
    [Paragraph("Batch certification + HITL review queue", sBody), Paragraph("✓  Live", ParagraphStyle("g", fontName="Helvetica-Bold", fontSize=9, textColor=GREEN))],
    [Paragraph("Amendment detection + auto-generation", sBody), Paragraph("✓  Live", ParagraphStyle("g", fontName="Helvetica-Bold", fontSize=9, textColor=GREEN))],
    [Paragraph("VA Benefits Intake API (sandbox)", sBody), Paragraph("✓  Live", ParagraphStyle("g", fontName="Helvetica-Bold", fontSize=9, textColor=GREEN))],
    [Paragraph("Multi-institution support (25 universities)", sBody), Paragraph("✓  Live", ParagraphStyle("g", fontName="Helvetica-Bold", fontSize=9, textColor=GREEN))],
    [Paragraph("PeopleSoft live integration (SDSU pilot)", sBody), Paragraph("◐  Q3 2026", ParagraphStyle("o", fontName="Helvetica-Bold", fontSize=9, textColor=ORANGE))],
]

traction_table = Table(traction_data, colWidths=[5.8*inch, 1.5*inch])
traction_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), DARK),
    ('TEXTCOLOR', (0,0), (-1,0), WHITE),
    ('BACKGROUND', (0,1), (-1,-1), WHITE),
    ('BOX', (0,0), (-1,-1), 0.5, SLATE_200),
    ('INNERGRID', (0,0), (-1,-1), 0.5, SLATE_200),
    ('TOPPADDING', (0,0), (-1,-1), 4),
    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ('LEFTPADDING', (0,0), (-1,-1), 8),
    ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
]))
story.append(traction_table)
story.append(Spacer(1, 14))

# === CTA FOOTER ===
cta_data = [[
    Paragraph("<b>Request a Demo</b>", sCTA),
], [
    Paragraph("paulina0101@gmail.com  ·  (858) 208-7354  ·  allowedcert.com", sCTASub),
]]

cta_table = Table(cta_data, colWidths=[7.3*inch])
cta_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), DARK),
    ('TOPPADDING', (0,0), (0,0), 10),
    ('BOTTOMPADDING', (0,0), (0,0), 2),
    ('TOPPADDING', (0,1), (0,1), 0),
    ('BOTTOMPADDING', (0,1), (0,1), 10),
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('ROUNDEDCORNERS', [6,6,6,6]),
]))
story.append(cta_table)

# Build
doc.build(story)
print("One-pager created: AllowED_One_Pager.pdf")

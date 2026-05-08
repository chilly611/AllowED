const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
        ShadingType, PageNumber, PageBreak, LevelFormat } = require("docx");

const border = { style: BorderStyle.SINGLE, size: 1, color: "CBD5E1" };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0 };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function heading(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 200 },
    children: [new TextRun({ text, bold: true, size: 32, font: "Arial", color: "1E40AF" })] });
}

function subheading(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 160 },
    children: [new TextRun({ text, bold: true, size: 26, font: "Arial", color: "0F172A" })] });
}

function body(text, opts = {}) {
  return new Paragraph({ spacing: { after: 160 },
    children: [new TextRun({ text, size: 22, font: "Arial", ...opts })] });
}

function bodyMulti(runs) {
  return new Paragraph({ spacing: { after: 160 },
    children: runs.map(r => typeof r === "string" ? new TextRun({ text: r, size: 22, font: "Arial" }) : new TextRun({ size: 22, font: "Arial", ...r })) });
}

function talkingPoint(label, script) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [1800, 7560],
    rows: [new TableRow({ children: [
      new TableCell({ borders, width: { size: 1800, type: WidthType.DXA },
        shading: { fill: "1E40AF", type: ShadingType.CLEAR },
        margins: { top: 100, bottom: 100, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: label, size: 20, font: "Arial", bold: true, color: "FFFFFF" })] })] }),
      new TableCell({ borders, width: { size: 7560, type: WidthType.DXA },
        margins: { top: 100, bottom: 100, left: 160, right: 160 },
        children: [new Paragraph({ children: [new TextRun({ text: script, size: 22, font: "Arial" })] })] }),
    ]})]
  });
}

function demoStep(step, action, say) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [600, 3380, 5380],
    rows: [new TableRow({ children: [
      new TableCell({ borders, width: { size: 600, type: WidthType.DXA },
        shading: { fill: "F97316", type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 80, right: 80 },
        verticalAlign: "center",
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: step, size: 22, font: "Arial", bold: true, color: "FFFFFF" })] })] }),
      new TableCell({ borders, width: { size: 3380, type: WidthType.DXA },
        shading: { fill: "FFF7ED", type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: action, size: 20, font: "Arial", italics: true, color: "9A3412" })] })] }),
      new TableCell({ borders, width: { size: 5380, type: WidthType.DXA },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: say, size: 22, font: "Arial" })] })] }),
    ]})]
  });
}

function spacer() {
  return new Paragraph({ spacing: { after: 120 }, children: [] });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: "1E40AF" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: "0F172A" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
    ]
  },
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }]
    }]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        children: [
          new TextRun({ text: "AllowED", size: 20, font: "Arial", bold: true, color: "F97316" }),
          new TextRun({ text: "  |  TechCrunch Demo Script  |  Confidential", size: 18, font: "Arial", color: "94A3B8" }),
        ]
      })] })
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Page ", size: 18, font: "Arial", color: "94A3B8" }), new TextRun({ children: [PageNumber.CURRENT], size: 18, font: "Arial", color: "94A3B8" })]
      })] })
    },
    children: [
      // TITLE
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
        children: [new TextRun({ text: "AllowED", size: 52, bold: true, font: "Arial", color: "F97316" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
        children: [new TextRun({ text: "VA Certification, Automated.", size: 28, font: "Arial", color: "0F172A" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
        children: [new TextRun({ text: "5-Minute Live Demo Script", size: 24, font: "Arial", color: "64748B" })] }),

      // OVERVIEW
      heading("The Setup (30 seconds)"),
      talkingPoint("OPEN WITH", "Every semester, I personally certify 2,100 veterans for their GI Bill benefits at San Diego State. Each one takes 15 minutes of manual data entry across two government systems. That\u2019s 525 hours of work. AllowED does it in under a minute per student."),
      spacer(),
      talkingPoint("CONTEXT", "I\u2019m Paulina Enriquez. I\u2019m the School Certifying Official at SDSU \u2014 I\u2019m the person who actually does this work every day. I built AllowED because nobody else who\u2019s building VA tech has ever sat in this chair."),
      spacer(),

      // DEMO FLOW
      heading("Live Demo (4 minutes)"),
      subheading("Act 1: The Dashboard (45 sec)"),
      demoStep("1", "Open workstation, log in as sco@sdsu.test", "This is the SCO Workstation \u2014 what I see when I start my day. 739 VA students this term. The system has already run every student through the VA\u2019s certification rules automatically."),
      spacer(),
      demoStep("2", "Point to dashboard cards", "480 are ready to certify right now \u2014 no manual review needed. 35 got flagged for human review. 135 already submitted. 113 certified by the VA. This used to be a spreadsheet."),
      spacer(),

      subheading("Act 2: The Decision Tree (60 sec)"),
      demoStep("3", "Click Students, search \u201CBahena\u201D", "Let me show you what the automation actually does. Daniel Bahena, undergraduate, BA Journalism, Chapter 33."),
      spacer(),
      demoStep("4", "Click Daniel Bahena\u2019s row", "Five courses. The system checked each one against VA rules: Is it in DARS? Is it required for the degree? What\u2019s the modality? Is it a repeat, audit, or remedial course?"),
      spacer(),
      demoStep("5", "Point to ENS 331 (excluded)", "ENS 331, Environmental Studies \u2014 3 units, excluded. It\u2019s not required for his BA in Journalism according to DARS. The VA won\u2019t pay for it. I would have caught this manually, but it takes me 10 minutes of cross-referencing. AllowED caught it in milliseconds."),
      spacer(),
      demoStep("6", "Point to unit totals: R:6, D:6, T:12", "Result: 6 residential units, 6 distance units, 12 total certifiable. Full-time. That\u2019s exactly what I\u2019d submit to the VA \u2014 AllowED got it right automatically."),
      spacer(),

      subheading("Act 3: Human-in-the-Loop (45 sec)"),
      demoStep("7", "Click HITL in sidebar", "Not everything is automatic. 35 students got flagged for my review. Low rate of pursuit, WEAMS program mismatch, unusual enrollment patterns. The system doesn\u2019t guess \u2014 it escalates."),
      spacer(),
      demoStep("8", "Click Approve on one item", "I review, I approve. One click. The VA requires a human SCO to sign off \u2014 AllowED makes that sign-off informed, not blind."),
      spacer(),

      subheading("Act 4: Batch Certification (45 sec)"),
      demoStep("9", "Click Students, select multiple checkboxes", "Here\u2019s where the time savings really hit. I select 20 students who are ready \u2014 all pre-validated by the decision tree."),
      spacer(),
      demoStep("10", "Click \u201CCertify Selected\u201D, show confirmation", "One click: 20 students submitted to the VA. That\u2019s 5 hours of manual work done in 10 seconds."),
      spacer(),

      subheading("Act 5: Multi-School (30 sec)"),
      demoStep("11", "Log out, log in as admin@allowed.test", "AllowED is multi-tenant. As a superadmin, I can see every school on the platform."),
      spacer(),
      demoStep("12", "Switch institution dropdown to CSU Fullerton", "Switch to CSU Fullerton \u2014 their data, their students, their rules. Same platform. That\u2019s how we scale: one school at a time, same infrastructure."),
      spacer(),

      // CLOSE
      new PageBreak(),
      heading("The Close (30 seconds)"),
      talkingPoint("THE ASK", "4,000 schools in America certify VA benefits. Every single one does it by hand. AllowED is the only platform that automates the actual certification logic \u2014 not just the paperwork, but the decisions. We\u2019re starting with the 23 CSU campuses and expanding from there."),
      spacer(),
      talkingPoint("DIFFERENTIATOR", "I\u2019m not a developer who read about VA certification. I\u2019m the SCO who does it every day. That\u2019s why AllowED gets the rules right \u2014 because I wrote them from the chair."),
      spacer(),

      // LOGISTICS
      heading("Demo Logistics"),
      body("URL: Open ~/Desktop/AllowED/allowed_workstation.html in Chrome"),
      body("Account 1: sco@sdsu.test / AllowED2026! (SCO view)"),
      body("Account 2: admin@allowed.test / AllowED2026! (superadmin view)"),
      body("Backup: If wifi fails, the demo works offline with cached data"),
      spacer(),

      heading("Key Numbers to Remember"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [4680, 4680],
        rows: [
          new TableRow({ children: [
            new TableCell({ borders, width: { size: 4680, type: WidthType.DXA }, shading: { fill: "0F172A", type: ShadingType.CLEAR },
              margins: { top: 80, bottom: 80, left: 120, right: 120 },
              children: [new Paragraph({ children: [new TextRun({ text: "Metric", bold: true, size: 22, font: "Arial", color: "FFFFFF" })] })] }),
            new TableCell({ borders, width: { size: 4680, type: WidthType.DXA }, shading: { fill: "0F172A", type: ShadingType.CLEAR },
              margins: { top: 80, bottom: 80, left: 120, right: 120 },
              children: [new Paragraph({ children: [new TextRun({ text: "Number", bold: true, size: 22, font: "Arial", color: "FFFFFF" })] })] }),
          ]}),
          ...[ ["VA students at SDSU per semester", "2,100"],
               ["Manual time per student", "15 minutes"],
               ["SCO hours per semester (manual)", "525 hours"],
               ["SCO hours per semester (AllowED)", "~35 hours"],
               ["Time savings", "93%"],
               ["Cost savings per semester ($50/hr)", "$24,500"],
               ["Schools approved for VA benefits (US)", "4,000+"],
               ["Target market (CSU system)", "23 campuses"],
             ].map(([metric, num]) => new TableRow({ children: [
              new TableCell({ borders, width: { size: 4680, type: WidthType.DXA },
                margins: { top: 60, bottom: 60, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: metric, size: 22, font: "Arial" })] })] }),
              new TableCell({ borders, width: { size: 4680, type: WidthType.DXA },
                margins: { top: 60, bottom: 60, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: num, size: 22, font: "Arial", bold: true })] })] }),
            ]}))
        ]
      }),
      spacer(),

      heading("Objection Handling"),
      talkingPoint("\"Can\u2019t the VA just build this?\"", "The VA builds tools for their side. They don\u2019t build tools for schools. That\u2019s like saying the IRS should build TurboTax. We\u2019re the school-side automation layer."),
      spacer(),
      talkingPoint("\"What about compliance?\"", "Every rule in AllowED comes from the SCO Handbook, 38 CFR, and 10 years of my certification experience. The system doesn\u2019t replace the SCO \u2014 it makes the SCO faster and more accurate."),
      spacer(),
      talkingPoint("\"How do you onboard a new school?\"", "Each school connects their student information system, we import their WEAMS-approved programs, and they\u2019re certifying within a week. The VA rules are universal \u2014 only the student data is different."),
      spacer(),
      talkingPoint("\"Who\u2019s your competition?\"", "Nobody. There is no product that automates VA certification decisions. Schools either do it by hand or they don\u2019t do it at all. That\u2019s a $100M+ market with zero automation."),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/sessions/keen-fervent-ptolemy/mnt/AllowED/AllowED_Demo_Script.docx", buffer);
  console.log("Demo script created: AllowED_Demo_Script.docx");
});

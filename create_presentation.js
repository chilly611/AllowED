const pptxgen = require("pptxgenjs");

let pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';
pres.author = 'Paulina';
pres.title = 'AllowED Strategy Presentation';

// Color palette
const colors = {
  darkBg: "0F172A",      // near-black navy
  primary: "1E40AF",     // electric blue
  orange: "F97316",      // vibrant orange
  green: "10B981",       // emerald
  light: "F8FAFC",       // near-white
  white: "FFFFFF",
  darkText: "0F172A",
  muted: "64748B"        // slate gray
};

// Helper function for fade transition
function addTransition(slide) {
  slide.transition = { type: 'fade' };
}

// Helper function to create a shadow
function makeShadow() {
  return { type: "outer", color: "000000", blur: 6, offset: 2, angle: 135, opacity: 0.15 };
}

// ============================================================================
// SLIDE 1: TITLE SLIDE
// ============================================================================
let slide1 = pres.addSlide();
addTransition(slide1);
slide1.background = { color: colors.darkBg };

slide1.addText("AllowED", {
  x: 0.5, y: 1.5, w: 9, h: 1.2,
  fontSize: 72, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

slide1.addText("AI-Powered VA Certification. Simplified.", {
  x: 0.5, y: 2.8, w: 9, h: 0.6,
  fontSize: 22, fontFace: "Calibri",
  color: colors.white, align: "center", valign: "middle"
});

slide1.addText("Strategy & Vision Document — 2026", {
  x: 0.5, y: 5.0, w: 9, h: 0.4,
  fontSize: 12, fontFace: "Calibri",
  color: colors.muted, align: "center", valign: "middle"
});

// ============================================================================
// SLIDE 2: THE OPENING STAT
// ============================================================================
let slide2 = pres.addSlide();
addTransition(slide2);
slide2.background = { color: colors.darkBg };

slide2.addText("2,500", {
  x: 0.5, y: 1.2, w: 9, h: 1.4,
  fontSize: 96, bold: true, fontFace: "Georgia",
  color: colors.orange, align: "center", valign: "middle", margin: 0
});

slide2.addText("certification requests per semester. One spreadsheet. Zero automation.", {
  x: 1, y: 2.8, w: 8, h: 1,
  fontSize: 24, fontFace: "Calibri",
  color: colors.white, align: "center", valign: "middle"
});

// ============================================================================
// SLIDE 3: SECTION - THE PROBLEM
// ============================================================================
let slide3 = pres.addSlide();
addTransition(slide3);
slide3.background = { color: colors.primary };

slide3.addText("THE PROBLEM", {
  x: 0.5, y: 2.2, w: 9, h: 1,
  fontSize: 54, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

// ============================================================================
// SLIDE 4: THE CURRENT WORKFLOW
// ============================================================================
let slide4 = pres.addSlide();
addTransition(slide4);
slide4.background = { color: colors.light };

slide4.addText("The Current Workflow", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 32, bold: true, fontFace: "Georgia",
  color: colors.darkText, align: "left", margin: 0
});

// 7-step flow
const steps = [
  { num: "1", label: "Student\nrequests" },
  { num: "2", label: "SCO runs\nquery" },
  { num: "3", label: "Copy to\nGoogle Sheet" },
  { num: "4", label: "Work-study\npreps (stale)" },
  { num: "5", label: "PeopleSoft\n+ EM" },
  { num: "6", label: "Manual\ncopy units" },
  { num: "7", label: "Submit,\nrepeat" }
];

let stepStartX = 0.6;
let stepGap = 1.27;

steps.forEach((step, idx) => {
  let x = stepStartX + idx * stepGap;

  // Circle
  slide4.addShape(pres.shapes.OVAL, {
    x: x, y: 1.3, w: 0.5, h: 0.5,
    fill: { color: colors.primary },
    line: { color: colors.primary, width: 1 }
  });

  // Number in circle
  slide4.addText(step.num, {
    x: x, y: 1.3, w: 0.5, h: 0.5,
    fontSize: 18, bold: true, fontFace: "Georgia",
    color: colors.white, align: "center", valign: "middle", margin: 0
  });

  // Label below
  slide4.addText(step.label, {
    x: x - 0.1, y: 1.9, w: 0.7, h: 0.8,
    fontSize: 10, fontFace: "Calibri",
    color: colors.darkText, align: "center", valign: "top"
  });
});

// Red callout bar
slide4.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 3.2, w: 9, h: 0.8,
  fill: { color: "DC2626" },
  line: { type: "none" }
});

slide4.addText("Target: 20/day. Reality: rarely achieved.", {
  x: 0.5, y: 3.2, w: 9, h: 0.8,
  fontSize: 16, bold: true, fontFace: "Calibri",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

// Additional text below
slide4.addText([
  { text: "All text dark on light background. ", options: {} },
  { text: "Manual workflows are error-prone and slow.", options: { italic: true } }
], {
  x: 0.5, y: 4.2, w: 9, h: 0.8,
  fontSize: 14, fontFace: "Calibri",
  color: colors.darkText, align: "left", valign: "top"
});

// ============================================================================
// SLIDE 5: WHAT WE LEARNED FROM SRA LOG
// ============================================================================
let slide5 = pres.addSlide();
addTransition(slide5);
slide5.background = { color: colors.light };

slide5.addText("What the Spreadsheet Really Does", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 32, bold: true, fontFace: "Georgia",
  color: colors.darkText, align: "left", margin: 0
});

// Three cards
const cardData = [
  { title: "Assignment\nTracking", desc: "Log daily requests" },
  { title: "Certification\nStatus", desc: "Mark as processed" },
  { title: "Safety Alerts", desc: "Ch.33 exhaustion" }
];

let cardX = 0.6;
let cardGap = 3;

cardData.forEach((card, idx) => {
  let x = cardX + idx * cardGap;

  slide5.addShape(pres.shapes.RECTANGLE, {
    x: x, y: 1.2, w: 2.8, h: 1.8,
    fill: { color: colors.white },
    line: { color: colors.primary, width: 2 },
    shadow: makeShadow()
  });

  slide5.addText(card.title, {
    x: x + 0.15, y: 1.35, w: 2.5, h: 0.6,
    fontSize: 14, bold: true, fontFace: "Georgia",
    color: colors.primary, align: "center", valign: "top"
  });

  slide5.addText(card.desc, {
    x: x + 0.15, y: 2.1, w: 2.5, h: 0.7,
    fontSize: 12, fontFace: "Calibri",
    color: colors.darkText, align: "center", valign: "top"
  });
});

// Orange callout
slide5.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 3.4, w: 9, h: 1.2,
  fill: { color: colors.orange },
  line: { type: "none" }
});

slide5.addText("One spreadsheet doing three jobs. Manual color-coding. No automation.", {
  x: 0.7, y: 3.5, w: 8.6, h: 0.5,
  fontSize: 16, bold: true, fontFace: "Calibri",
  color: colors.white, align: "left", valign: "top"
});

slide5.addText("Ch.33 exhaustion warnings are a SAFETY function — currently tracked by eye.", {
  x: 0.7, y: 4.05, w: 8.6, h: 0.5,
  fontSize: 14, fontFace: "Calibri",
  color: colors.white, align: "left", valign: "top", italic: true
});

// ============================================================================
// SLIDE 6: SECTION - THE OPPORTUNITY
// ============================================================================
let slide6 = pres.addSlide();
addTransition(slide6);
slide6.background = { color: colors.primary };

slide6.addText("THE OPPORTUNITY", {
  x: 0.5, y: 2.2, w: 9, h: 1,
  fontSize: 54, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

// ============================================================================
// SLIDE 7: MARKET NUMBERS
// ============================================================================
let slide7 = pres.addSlide();
addTransition(slide7);
slide7.background = { color: colors.light };

slide7.addText("Market Numbers", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 32, bold: true, fontFace: "Georgia",
  color: colors.darkText, align: "left", margin: 0
});

// Three stat callouts
const stats = [
  { num: "5,000+", label: "VA-Certifying\nInstitutions" },
  { num: "1.5M+", label: "Certifications\nper Year" },
  { num: "$564M", label: "Benefits Processed\n(DGB, Month 1)" }
];

let statX = 0.7;
let statGap = 3;

stats.forEach((stat, idx) => {
  let x = statX + idx * statGap;

  slide7.addText(stat.num, {
    x: x, y: 1.4, w: 2.6, h: 0.8,
    fontSize: 40, bold: true, fontFace: "Georgia",
    color: colors.primary, align: "center", valign: "bottom"
  });

  slide7.addText(stat.label, {
    x: x, y: 2.2, w: 2.6, h: 0.8,
    fontSize: 11, fontFace: "Calibri",
    color: colors.muted, align: "center", valign: "top"
  });
});

// Bottom text
slide7.addText("VA is automating THEIR side (50-62%). Universities are still 100% manual.", {
  x: 0.5, y: 3.4, w: 9, h: 0.6,
  fontSize: 16, fontFace: "Calibri",
  color: colors.darkText, align: "left", valign: "top", italic: true
});

// ============================================================================
// SLIDE 8: NO DIRECT COMPETITOR
// ============================================================================
let slide8 = pres.addSlide();
addTransition(slide8);
slide8.background = { color: colors.darkBg };

slide8.addText("No one is doing this.", {
  x: 0.5, y: 0.9, w: 9, h: 0.8,
  fontSize: 42, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

// Four competitor items
const competitors = [
  { title: "PeopleSoft", desc: "Data storage, not automation" },
  { title: "Enrollment Manager", desc: "VA's tool, not the university's" },
  { title: "Generic RPA", desc: "Doesn't understand VA rules" },
  { title: "Financial Aid Tools", desc: "Wrong domain entirely" }
];

let compY = 2.0;
let compLineHeight = 0.75;

competitors.forEach((comp) => {
  // Left circle
  slide8.addShape(pres.shapes.OVAL, {
    x: 0.6, y: compY + 0.05, w: 0.3, h: 0.3,
    fill: { color: colors.orange },
    line: { type: "none" }
  });

  // Title
  slide8.addText(comp.title, {
    x: 1.1, y: compY + 0.05, w: 2, h: 0.35,
    fontSize: 14, bold: true, fontFace: "Calibri",
    color: colors.white, align: "left", valign: "middle"
  });

  // Description
  slide8.addText(comp.desc, {
    x: 3.2, y: compY + 0.05, w: 6, h: 0.35,
    fontSize: 12, fontFace: "Calibri",
    color: colors.muted, align: "left", valign: "middle"
  });

  compY += compLineHeight;
});

// Footer
slide8.addText("First mover advantage in a category that doesn't exist yet.", {
  x: 0.5, y: 4.9, w: 9, h: 0.5,
  fontSize: 14, italic: true, fontFace: "Calibri",
  color: colors.orange, align: "center", valign: "middle"
});

// ============================================================================
// SLIDE 9: SECTION - ALLOWED
// ============================================================================
let slide9 = pres.addSlide();
addTransition(slide9);
slide9.background = { color: colors.primary };

slide9.addText("ALLOWED", {
  x: 0.5, y: 1.6, w: 9, h: 0.8,
  fontSize: 54, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

slide9.addText("The Solution", {
  x: 0.5, y: 2.5, w: 9, h: 0.6,
  fontSize: 28, fontFace: "Calibri",
  color: colors.orange, align: "center", valign: "middle"
});

// ============================================================================
// SLIDE 10: WHAT ALLOWED DOES
// ============================================================================
let slide10 = pres.addSlide();
addTransition(slide10);
slide10.background = { color: colors.light };

slide10.addText("What AllowED Does", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 32, bold: true, fontFace: "Georgia",
  color: colors.darkText, align: "left", margin: 0
});

// Left: big statement
slide10.addText("An AI workstation that replaces the entire SCO workflow", {
  x: 0.5, y: 1.1, w: 4.3, h: 1.2,
  fontSize: 18, bold: true, fontFace: "Georgia",
  color: colors.primary, align: "left", valign: "top"
});

// Right: 4 bullet points
const bullets = [
  "Auto-pulls fresh enrollment + degree eval (no stale data)",
  "Decision tree evaluates every course against VA rules",
  "Clean students batch-certify. Exceptions surface for SCO.",
  "One click to approve and submit. Done."
];

let bulletY = 1.1;
bullets.forEach((bullet) => {
  // Green circle
  slide10.addShape(pres.shapes.OVAL, {
    x: 5.0, y: bulletY + 0.08, w: 0.2, h: 0.2,
    fill: { color: colors.green },
    line: { type: "none" }
  });

  slide10.addText(bullet, {
    x: 5.4, y: bulletY, w: 4, h: 0.45,
    fontSize: 12, fontFace: "Calibri",
    color: colors.darkText, align: "left", valign: "top"
  });

  bulletY += 0.48;
});

// Dark footer bar
slide10.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 4.9, w: 10, h: 0.7,
  fill: { color: colors.darkBg },
  line: { type: "none" }
});

slide10.addText("AllowED assists. The SCO decides.", {
  x: 0.5, y: 4.9, w: 9, h: 0.7,
  fontSize: 16, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

// ============================================================================
// SLIDE 11: THE ALLOWED WORKFLOW
// ============================================================================
let slide11 = pres.addSlide();
addTransition(slide11);
slide11.background = { color: colors.light };

slide11.addText("The AllowED Workflow", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 32, bold: true, fontFace: "Georgia",
  color: colors.darkText, align: "left", margin: 0
});

// 4-step streamlined flow
const streamlined = [
  { num: "1", label: "Student\nrequests", color: colors.green },
  { num: "2", label: "AllowED\nauto-evaluates", color: colors.primary },
  { num: "3", label: "SCO reviews\nexceptions", color: colors.orange },
  { num: "4", label: "Certified &\nsubmitted", color: colors.green }
];

let streamlineX = 1.0;
let streamlineGap = 2.0;

streamlined.forEach((step) => {
  slide11.addShape(pres.shapes.OVAL, {
    x: streamlineX, y: 1.5, w: 0.6, h: 0.6,
    fill: { color: step.color },
    line: { type: "none" }
  });

  slide11.addText(step.num, {
    x: streamlineX, y: 1.5, w: 0.6, h: 0.6,
    fontSize: 20, bold: true, fontFace: "Georgia",
    color: colors.white, align: "center", valign: "middle", margin: 0
  });

  slide11.addText(step.label, {
    x: streamlineX - 0.2, y: 2.25, w: 1, h: 0.8,
    fontSize: 11, fontFace: "Calibri",
    color: colors.darkText, align: "center", valign: "top"
  });

  streamlineX += streamlineGap;
});

// Callout box
slide11.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 3.4, w: 9, h: 1.5,
  fill: { color: colors.white },
  line: { color: colors.primary, width: 2 },
  shadow: makeShadow()
});

slide11.addText([
  { text: "7 steps → 4. ", options: { bold: true } },
  { text: "Manual copy → automated. ", options: {} },
  { text: "Stale data → real-time.", options: { italic: true } }
], {
  x: 0.8, y: 3.55, w: 8.4, h: 1.2,
  fontSize: 14, fontFace: "Calibri",
  color: colors.darkText, align: "left", valign: "top"
});

// ============================================================================
// SLIDE 12: THREE INTERFACES
// ============================================================================
let slide12 = pres.addSlide();
addTransition(slide12);
slide12.background = { color: colors.light };

slide12.addText("Three Interfaces", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 32, bold: true, fontFace: "Georgia",
  color: colors.darkText, align: "left", margin: 0
});

// Three cards
const interfaces = [
  { title: "SCO Workstation", desc: "Queue, certify, benefit alerts, PO tracking", color: colors.primary },
  { title: "Student Status Page", desc: "\"Where's my GI Bill?\" answered instantly", color: colors.green },
  { title: "Admin Dashboard", desc: "Volume, performance, audit compliance", color: colors.orange }
];

let intX = 0.6;
let intGap = 3;

interfaces.forEach((intf) => {
  // Accent bar on left
  slide12.addShape(pres.shapes.RECTANGLE, {
    x: intX, y: 1.2, w: 0.08, h: 2,
    fill: { color: intf.color },
    line: { type: "none" }
  });

  // Card
  slide12.addShape(pres.shapes.RECTANGLE, {
    x: intX, y: 1.2, w: 2.8, h: 2,
    fill: { color: colors.white },
    line: { color: colors.primary, width: 1 },
    shadow: makeShadow()
  });

  slide12.addText(intf.title, {
    x: intX + 0.15, y: 1.4, w: 2.5, h: 0.6,
    fontSize: 13, bold: true, fontFace: "Georgia",
    color: colors.darkText, align: "left", valign: "top"
  });

  slide12.addText(intf.desc, {
    x: intX + 0.15, y: 2.1, w: 2.5, h: 0.9,
    fontSize: 11, fontFace: "Calibri",
    color: colors.darkText, align: "left", valign: "top"
  });

  intX += intGap;
});

// ============================================================================
// SLIDE 13: WHAT'S ALREADY BUILT
// ============================================================================
let slide13 = pres.addSlide();
addTransition(slide13);
slide13.background = { color: colors.darkBg };

slide13.addText("200+", {
  x: 0.5, y: 0.8, w: 9, h: 1,
  fontSize: 80, bold: true, fontFace: "Georgia",
  color: colors.orange, align: "center", valign: "middle", margin: 0
});

slide13.addText("regression checks. All passing.", {
  x: 0.5, y: 1.8, w: 9, h: 0.6,
  fontSize: 22, fontFace: "Calibri",
  color: colors.white, align: "center", valign: "middle"
});

// Grid of 7 modules (2 rows)
const modules = [
  { title: "Decision Tree", check: "63/63" },
  { title: "WEAMS Matching", check: "853 programs" },
  { title: "EM Integration", check: "31/31" },
  { title: "Enrollment Monitor", check: "90/90" },
  { title: "T&F Certification", check: "21/21" },
  { title: "Rounding Out", check: "4/4" },
  { title: "Pipeline Orchestrator", check: "6/6" }
];

let modX = 0.5;
let modGap = 1.32;
let modRow = 2.8;

modules.forEach((mod, idx) => {
  if (idx === 4) {
    modX = 0.5;
    modRow = 4.0;
  }

  // Module box
  slide13.addShape(pres.shapes.RECTANGLE, {
    x: modX, y: modRow, w: 1.2, h: 0.8,
    fill: { color: colors.primary },
    line: { type: "none" },
    shadow: makeShadow()
  });

  slide13.addText([
    { text: mod.title, options: { fontSize: 9, bold: true, breakLine: true } },
    { text: mod.check, options: { fontSize: 8, color: colors.orange } }
  ], {
    x: modX + 0.05, y: modRow + 0.05, w: 1.1, h: 0.7,
    fontSize: 9, fontFace: "Calibri",
    color: colors.white, align: "center", valign: "middle"
  });

  // Green checkmark circle
  slide13.addShape(pres.shapes.OVAL, {
    x: modX + 1.05, y: modRow - 0.15, w: 0.35, h: 0.35,
    fill: { color: colors.green },
    line: { type: "none" }
  });

  slide13.addText("✓", {
    x: modX + 1.05, y: modRow - 0.15, w: 0.35, h: 0.35,
    fontSize: 20, bold: true, fontFace: "Calibri",
    color: colors.white, align: "center", valign: "middle", margin: 0
  });

  modX += modGap;
});

// ============================================================================
// SLIDE 14: SECTION - THE PLAYBOOK
// ============================================================================
let slide14 = pres.addSlide();
addTransition(slide14);
slide14.background = { color: colors.darkBg };

slide14.addText("THE PLAYBOOK", {
  x: 0.5, y: 2.2, w: 9, h: 1,
  fontSize: 54, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

// ============================================================================
// SLIDE 15: HOW CATEGORY CREATORS WIN
// ============================================================================
let slide15 = pres.addSlide();
addTransition(slide15);
slide15.background = { color: colors.light };

slide15.addText("How Category Creators Win", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 32, bold: true, fontFace: "Georgia",
  color: colors.darkText, align: "left", margin: 0
});

const companies = [
  { name: "Veeva", stat: "80% pharma market share", tagline: "Niche compliance" },
  { name: "Palantir", stat: "$20B government platform", tagline: "Build with the customer" },
  { name: "TurboTax", stat: "70% tax filing share", tagline: "Make the complex effortless" },
  { name: "Stripe", stat: "$95B payments standard", tagline: "Developer-first wedge" }
];

let compCardX = 0.6;
let compCardGap = 2.3;

companies.forEach((comp) => {
  // Card background
  slide15.addShape(pres.shapes.RECTANGLE, {
    x: compCardX, y: 1.2, w: 2.2, h: 1.8,
    fill: { color: colors.white },
    line: { color: colors.orange, width: 2 },
    shadow: makeShadow()
  });

  // Company name
  slide15.addText(comp.name, {
    x: compCardX + 0.1, y: 1.35, w: 2, h: 0.35,
    fontSize: 13, bold: true, fontFace: "Georgia",
    color: colors.primary, align: "left", valign: "top"
  });

  // Tagline
  slide15.addText(comp.tagline, {
    x: compCardX + 0.1, y: 1.75, w: 2, h: 0.4,
    fontSize: 10, fontFace: "Calibri",
    color: colors.muted, align: "left", valign: "top"
  });

  // Stat
  slide15.addText(comp.stat, {
    x: compCardX + 0.1, y: 2.2, w: 2, h: 0.7,
    fontSize: 11, bold: true, fontFace: "Calibri",
    color: colors.darkText, align: "left", valign: "top"
  });

  compCardX += compCardGap;
});

// Footer
slide15.addText("AllowED follows the playbook: own the niche, prove it works, become the standard.", {
  x: 0.5, y: 3.3, w: 9, h: 0.6,
  fontSize: 14, italic: true, fontFace: "Calibri",
  color: colors.darkText, align: "center", valign: "middle"
});

// ============================================================================
// SLIDE 16: GO-TO-MARKET PHASES
// ============================================================================
let slide16 = pres.addSlide();
addTransition(slide16);
slide16.background = { color: colors.light };

slide16.addText("Go-to-Market: Phase by Phase", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 32, bold: true, fontFace: "Georgia",
  color: colors.darkText, align: "left", margin: 0
});

const phases = [
  { label: "Phase 1", color: colors.primary, text: "CSU System — SDSU + CSUN pilot, expand to 23 campuses" },
  { label: "Phase 2", color: colors.green, text: "Large Veteran Schools — ASU (8,900 GI Bill), Texas A&M, UMGC" },
  { label: "Phase 3", color: colors.orange, text: "Community Colleges — Understaffed, high need, 1000+ campuses" },
  { label: "Phase 4", color: colors.darkBg, text: "National Standard — Banner + Workday SIS. Every VA-certifying school." }
];

let phaseY = 1.3;
phases.forEach((phase) => {
  // Phase block
  slide16.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: phaseY, w: 2, h: 0.65,
    fill: { color: phase.color },
    line: { type: "none" },
    shadow: makeShadow()
  });

  slide16.addText(phase.label, {
    x: 0.5, y: phaseY, w: 2, h: 0.65,
    fontSize: 12, bold: true, fontFace: "Georgia",
    color: colors.white, align: "center", valign: "middle", margin: 0
  });

  // Description
  slide16.addText(phase.text, {
    x: 2.7, y: phaseY, w: 6.8, h: 0.65,
    fontSize: 12, fontFace: "Calibri",
    color: colors.darkText, align: "left", valign: "middle"
  });

  phaseY += 0.75;
});

// ============================================================================
// SLIDE 17: SALES CHANNELS
// ============================================================================
let slide17 = pres.addSlide();
addTransition(slide17);
slide17.background = { color: colors.light };

slide17.addText("Sales Channels", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 32, bold: true, fontFace: "Georgia",
  color: colors.darkText, align: "left", margin: 0
});

// Left column
slide17.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 1.1, w: 4.4, h: 0.5,
  fill: { color: colors.primary },
  line: { type: "none" }
});

slide17.addText("Conferences & Community", {
  x: 0.5, y: 1.1, w: 4.4, h: 0.5,
  fontSize: 14, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

const confs = [
  "NAVPA Annual Conference (Dallas 2026, 400+ institutions)",
  "NASPA (2,000+ higher-ed leaders)",
  "NASPA Military-Connected Students Symposium"
];

let confY = 1.8;
confs.forEach((conf) => {
  slide17.addText(conf, {
    x: 0.7, y: confY, w: 4, h: 0.45,
    fontSize: 11, fontFace: "Calibri",
    color: colors.darkText, align: "left", valign: "top"
  });
  confY += 0.5;
});

// Right column
slide17.addShape(pres.shapes.RECTANGLE, {
  x: 5.1, y: 1.1, w: 4.4, h: 0.5,
  fill: { color: colors.green },
  line: { type: "none" }
});

slide17.addText("Grants & Government", {
  x: 5.1, y: 1.1, w: 4.4, h: 0.5,
  fontSize: 14, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

const grants = [
  "VA SBIR/STTR ($150K-$1.5M R&D grants)",
  "CEVSS (Dept of Education, $500K+ for veteran student tech)",
  "VA OIT Industry Day (March 2026)",
  "CSU System-level procurement"
];

let grantY = 1.8;
grants.forEach((grant) => {
  slide17.addText(grant, {
    x: 5.3, y: grantY, w: 4, h: 0.45,
    fontSize: 11, fontFace: "Calibri",
    color: colors.darkText, align: "left", valign: "top"
  });
  grantY += 0.5;
});

// ============================================================================
// SLIDE 18: WHY NOW
// ============================================================================
let slide18 = pres.addSlide();
addTransition(slide18);
slide18.background = { color: colors.darkBg };

slide18.addText("Why Now", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 32, bold: true, fontFace: "Georgia",
  color: colors.white, align: "left", margin: 0
});

const reasons = [
  { num: "1", text: "VA staffing cuts (1,000+ in 2026) degrading approval speed" },
  { num: "2", text: "Digital GI Bill modernization creating expectation of speed" },
  { num: "3", text: "No competitor in the space — category is empty" },
  { num: "4", text: "Students waiting MONTHS for GI Bill payments" },
  { num: "5", text: "CSU deployed ChatGPT Edu system-wide — open to EdTech innovation" }
];

let reasonY = 1.1;
reasons.forEach((reason) => {
  // Circle
  slide18.addShape(pres.shapes.OVAL, {
    x: 0.5, y: reasonY + 0.05, w: 0.35, h: 0.35,
    fill: { color: colors.orange },
    line: { type: "none" }
  });

  slide18.addText(reason.num, {
    x: 0.5, y: reasonY + 0.05, w: 0.35, h: 0.35,
    fontSize: 16, bold: true, fontFace: "Georgia",
    color: colors.white, align: "center", valign: "middle", margin: 0
  });

  slide18.addText(reason.text, {
    x: 1.0, y: reasonY, w: 8.5, h: 0.45,
    fontSize: 12, fontFace: "Calibri",
    color: colors.white, align: "left", valign: "top"
  });

  reasonY += 0.55;
});

// Footer
slide18.addText("The gap between VA automation and university automation is growing every day.", {
  x: 0.5, y: 4.9, w: 9, h: 0.5,
  fontSize: 14, italic: true, fontFace: "Calibri",
  color: colors.orange, align: "center", valign: "middle"
});

// ============================================================================
// SLIDE 19: COMPLIANCE BUILT IN
// ============================================================================
let slide19 = pres.addSlide();
addTransition(slide19);
slide19.background = { color: colors.light };

slide19.addText("Compliance Built In", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 32, bold: true, fontFace: "Georgia",
  color: colors.darkText, align: "left", margin: 0
});

// Left column: Safety
slide19.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 1.1, w: 4.4, h: 0.5,
  fill: { color: colors.primary },
  line: { type: "none" }
});

slide19.addText("Safety", {
  x: 0.5, y: 1.1, w: 4.4, h: 0.5,
  fontSize: 14, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

const safety = [
  "HITL escalation (7 triggers)",
  "No cert without SCO approval",
  "Full audit trail",
  "Census-date-aware logic"
];

let safetyY = 1.8;
safety.forEach((item) => {
  slide19.addText("• " + item, {
    x: 0.7, y: safetyY, w: 4, h: 0.4,
    fontSize: 11, fontFace: "Calibri",
    color: colors.darkText, align: "left", valign: "top"
  });
  safetyY += 0.45;
});

// Right column: Compliance
slide19.addShape(pres.shapes.RECTANGLE, {
  x: 5.1, y: 1.1, w: 4.4, h: 0.5,
  fill: { color: colors.green },
  line: { type: "none" }
});

slide19.addText("Compliance", {
  x: 5.1, y: 1.1, w: 4.4, h: 0.5,
  fontSize: 14, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

const compliance = [
  "VA Handbook rules in code (38 CFR Part 21)",
  "Dual certification model",
  "Section 508 accessible",
  "FERPA-ready architecture"
];

let complianceY = 1.8;
compliance.forEach((item) => {
  slide19.addText("• " + item, {
    x: 5.3, y: complianceY, w: 4, h: 0.4,
    fontSize: 11, fontFace: "Calibri",
    color: colors.darkText, align: "left", valign: "top"
  });
  complianceY += 0.45;
});

// Dark footer bar
slide19.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 4.9, w: 10, h: 0.7,
  fill: { color: colors.darkBg },
  line: { type: "none" }
});

slide19.addText("Built by an SCO. Validated against 200+ real-world checks.", {
  x: 0.5, y: 4.9, w: 9, h: 0.7,
  fontSize: 14, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

// ============================================================================
// SLIDE 20: FOUNDER
// ============================================================================
let slide20 = pres.addSlide();
addTransition(slide20);
slide20.background = { color: colors.darkBg };

slide20.addText("PAULINA", {
  x: 0.5, y: 0.8, w: 9, h: 0.7,
  fontSize: 48, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

slide20.addText("Teacher. VA Compliance Consultant. SCO. Academic Advisor. Founder.", {
  x: 0.5, y: 1.65, w: 9, h: 0.6,
  fontSize: 14, fontFace: "Calibri",
  color: colors.orange, align: "center", valign: "middle"
});

slide20.addText("Certifies 2,500 students/semester at SDSU. Built AllowED from the real workflow — not from imagination.", {
  x: 1, y: 2.5, w: 8, h: 1.2,
  fontSize: 16, fontFace: "Calibri",
  color: colors.white, align: "center", valign: "top"
});

slide20.addText("paulina0101@gmail.com", {
  x: 0.5, y: 4.8, w: 9, h: 0.5,
  fontSize: 14, fontFace: "Calibri",
  color: colors.orange, align: "center", valign: "middle"
});

// ============================================================================
// SLIDE 21: THE ASK
// ============================================================================
let slide21 = pres.addSlide();
addTransition(slide21);
slide21.background = { color: colors.primary };

slide21.addText("The Ask", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 32, bold: true, fontFace: "Georgia",
  color: colors.white, align: "left", margin: 0
});

// Three columns
const asks = [
  { title: "Pilot Partners", text: "SDSU + CSUN, Fall 2026" },
  { title: "Strategic Investment", text: "Scale to all 23 CSU campuses" },
  { title: "VA Partnership", text: "OIT Industry Day, SBIR/STTR" }
];

let askX = 0.6;
let askGap = 3;

asks.forEach((ask) => {
  // Card
  slide21.addShape(pres.shapes.RECTANGLE, {
    x: askX, y: 1.2, w: 2.8, h: 2.5,
    fill: { color: colors.white },
    line: { color: colors.orange, width: 2 },
    shadow: makeShadow()
  });

  slide21.addText(ask.title, {
    x: askX + 0.15, y: 1.4, w: 2.5, h: 0.6,
    fontSize: 14, bold: true, fontFace: "Georgia",
    color: colors.primary, align: "center", valign: "top"
  });

  slide21.addText(ask.text, {
    x: askX + 0.15, y: 2.2, w: 2.5, h: 1.2,
    fontSize: 13, fontFace: "Calibri",
    color: colors.darkText, align: "center", valign: "top"
  });

  askX += askGap;
});

// Bottom quote
slide21.addText("We didn't imagine the workflow. We automated the real one.", {
  x: 0.5, y: 4.2, w: 9, h: 0.6,
  fontSize: 16, italic: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle"
});

// ============================================================================
// SLIDE 22: CLOSING
// ============================================================================
let slide22 = pres.addSlide();
addTransition(slide22);
slide22.background = { color: colors.darkBg };

slide22.addText("AllowED", {
  x: 0.5, y: 1.4, w: 9, h: 1,
  fontSize: 68, bold: true, fontFace: "Georgia",
  color: colors.white, align: "center", valign: "middle", margin: 0
});

slide22.addText("Allowing education to flow.", {
  x: 0.5, y: 2.6, w: 9, h: 0.6,
  fontSize: 26, fontFace: "Calibri",
  color: colors.orange, align: "center", valign: "middle"
});

slide22.addText("paulina0101@gmail.com", {
  x: 0.5, y: 3.5, w: 9, h: 0.4,
  fontSize: 14, fontFace: "Calibri",
  color: colors.white, align: "center", valign: "middle"
});

// ============================================================================
// SAVE
// ============================================================================
pres.writeFile({ fileName: "AllowED_Strategy_v2.pptx" });
console.log("Presentation created: AllowED_Strategy_v2.pptx");

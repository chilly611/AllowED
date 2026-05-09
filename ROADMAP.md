# AllowED — Go-to-Market Roadmap

## Key Dates
- **May 27** — TechCrunch (live demo, all materials ready)
- **June** — First pilot school onboarding
- **Summer 2026** — SDSU summer session = first real certification run

## Completed ✅
- [x] Demo script written (AllowED_Demo_Script.docx)
- [x] Amendment flow added to workstation
- [x] Batch certification workflow added to workstation
- [x] 25 schools seeded with synthetic data (10,929 students)
- [x] HITL queue with real flags
- [x] Benefits Intake PDF generation (mock mode)
- [x] Superadmin institution switcher

## Phase 1: Sales Materials (May 8-14) ← NOW
**Goal: Everything you need to email an SCO, pitch an investor, or walk into a meeting.**

### One-Pager PDF (for SCOs at other CSUs)
- [ ] "Before/After" comparison: manual process vs AllowED
- [ ] Key numbers: 2,100 students, 525→35 hours, 93% time savings
- [ ] Screenshot of the working dashboard
- [ ] "Request a Demo" CTA with contact info
- [ ] Print-friendly, one page, professional

### Marketing Website (for everyone)
- [ ] Update allowed_website.html with real platform screenshots
- [ ] Value prop hero: "VA Certification, Automated."
- [ ] How It Works section (3 steps: Connect → Automate → Certify)
- [ ] ROI calculator or savings callout
- [ ] "Request Demo" form (name, school, email, role)
- [ ] Social proof: "Built by an SCO who certifies 2,100 students/semester"
- [ ] SEO: title, meta description, OG tags

### Pitch Deck Update (for investors + TechCrunch)
- [ ] Update AllowED_Strategy_v2.pptx with live screenshots
- [ ] Add demo video link or QR code
- [ ] Market size slide: 4,000+ schools × avg contract value
- [ ] Traction slide: working platform, 25 schools in demo, SDSU pilot

## Phase 2: Pricing & Outreach (May 14-20)
**Goal: Know what you're charging and start conversations.**

- [ ] Pricing model: per-institution SaaS, tiered by VA student count
  - Pilot: Free for first 3-5 schools (build case studies)
  - Small (<500 VA students): $X/year
  - Medium (500-2000): $X/year
  - Large (2000+): $X/year
- [ ] ROI calculator: hours saved × SCO hourly cost vs subscription
- [ ] Draft one-page school agreement template
- [ ] Email template for reaching out to SCO contacts at other CSUs
- [ ] LinkedIn post announcing AllowED (link to website)

## Phase 3: TechCrunch Prep (May 20-27)
**Goal: Polished demo, all materials battle-tested.**

- [ ] Practice 5-minute demo 3+ times
- [ ] Record backup demo video (in case wifi fails)
- [ ] Print one-pagers to hand out
- [ ] Business cards or QR code to website
- [ ] Prepare for Q&A: compliance, competition, onboarding, pricing
- [ ] Dress rehearsal with someone who'll give honest feedback

## Phase 4: School Onboarding Flow (June)
**Goal: When an SCO says "yes," they can start within a week.**

- [ ] Superadmin "Add School" wizard
- [ ] Institution configuration: name, facility code, term dates, training time standards
- [ ] SCO account creation and invitation flow
- [ ] WEAMS program import (auto-pull or CSV upload)
- [ ] PeopleSoft connection or CSV enrollment upload
- [ ] Onboarding checklist for new schools

## Phase 5: Production Hardening (June-July)
- [ ] VA Lighthouse sandbox keys → live Benefits Intake API
- [ ] Session-aware certification (SDSU summer, ASU sub-sessions)
- [ ] Real PeopleSoft adapter (Jen Christensen at SDSU)
- [ ] FERPA compliance documentation
- [ ] Security audit
- [ ] Monitoring and error alerting

## What We're Selling

AllowED automates VA enrollment certification for universities. SCOs currently spend 15-20 minutes per student doing manual data entry across PeopleSoft and VA Enrollment Manager. AllowED reduces that to under 1 minute per student.

**For a school like SDSU (2,100 VA students/semester):**
- Current: ~525 SCO hours per semester on certification alone
- With AllowED: ~35 SCO hours (review + approve batches)
- Savings: ~490 hours per semester = $24,500/semester at $50/hr

**Target market:** 4,000+ schools approved for VA benefits nationwide. Starting with CSU system (23 campuses), expanding to UC, state universities, community colleges.

**Differentiator:** Built by the only SCO in America who's also building the software. Every rule comes from the chair, not a whiteboard.

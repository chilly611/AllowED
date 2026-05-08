# AllowED — Go-to-Market Roadmap

## Phase 1: Demo & Pitch Deck (May 6-10) ← NOW
- [ ] Write 5-minute live demo script (login → dashboard → drill-down → HITL → batch cert → institution switch)
- [ ] Update AllowED_Strategy_v2.pptx with live platform screenshots
- [ ] Add amendment flow to workstation (needed for demo)
- [ ] Add batch certification workflow to workstation (needed for demo)
- [ ] Visual polish — loading states, professional feel, brand consistency
- [ ] Practice run: record a screen capture of the full demo flow
- [ ] Talking points for TechCrunch, investor meetings, school meetings

## Phase 2: Sales One-Pager & Website (May 10-17)
- [ ] Update allowed_website.html with real screenshots from working platform
- [ ] Clear value prop: "2,100 certifications per semester — hours, not weeks"
- [ ] Add "Request Demo" form (collect name, school, email)
- [ ] Create PDF one-pager for emailing SCOs at other schools
- [ ] Testimonial / case study section (use SDSU workflow comparison)
- [ ] SEO basics: title, meta, OG tags for sharing

## Phase 3: Pricing & Contracts (May 12-20)
- [ ] Define pricing model: per-institution SaaS, tiered by student count
- [ ] Suggested tiers: Small (<500 VA students), Medium (500-2000), Large (2000+)
- [ ] Draft one-page school agreement template
- [ ] ROI calculator: hours saved × SCO hourly cost vs subscription price
- [ ] Free pilot offer for first 3-5 schools (build case studies)

## Phase 4: School Onboarding Flow (May 17-31)
- [ ] Superadmin "Add School" wizard in the workstation
- [ ] Institution configuration: name, facility code, term dates, training time standards
- [ ] SCO account creation and invitation flow
- [ ] WEAMS program import (auto-pull from VA GI Bill Comparison Tool or CSV upload)
- [ ] PeopleSoft connection setup (or CSV enrollment upload as fallback)
- [ ] Onboarding checklist that guides new school through first certification

## Phase 5: Production Hardening (June)
- [ ] Register for VA Lighthouse sandbox keys → switch Benefits Intake from mock to live
- [ ] Session-aware certification for SDSU summer and ASU sub-sessions
- [ ] Real PeopleSoft adapter (work with Jen Christensen at SDSU)
- [ ] FERPA compliance review and data handling documentation
- [ ] Security audit: RLS policies, API authentication, data encryption
- [ ] Monitoring and error alerting

## Key Dates
- **May 27** — TechCrunch (demo must be polished)
- **June** — Target first pilot school onboarding
- **Summer 2026** — SDSU summer session = first real certification run

## What We're Selling
AllowED automates VA enrollment certification for universities. SCOs currently spend 15-20 minutes per student doing manual data entry across PeopleSoft and VA Enrollment Manager. AllowED reduces that to under 1 minute per student by automating the decision tree (course applicability, modality, training time, WEAMS matching) and formatting the output for VA submission.

**For a school like SDSU (2,100 VA students/semester):**
- Current: ~525 SCO hours per semester on certification alone
- With AllowED: ~35 SCO hours (review + approve batches)
- Savings: ~490 hours per semester = $24,500/semester at $50/hr SCO cost

**Target market:** 4,000+ schools approved for VA benefits nationwide. Starting with CSU system (23 campuses), expanding to UC, state universities, community colleges.

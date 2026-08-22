# Hermes-Notion

**Autonomous Internship Application Pipeline — automate one real job, with Notion as the interface**

| | |
|---|---|
| **Team** | DeepMinds |
| **Team ID** | team-B6FA2C3BE946 |
| **Track** | Notion Track |
| **College** | SRM Institute of Science and Technology, Delhi NCR Campus |

---

## The Problem

Searching for internships is a manual grind:

- **Manual Repetition** — Searching listings, reading JDs, guessing keywords, and tailoring resumes for every single application is unsustainable.
- **The Outreach Gap** — Generic resumes rarely get noticed at startups. Personalized cold outreach works, but takes hours of research per company.
- **Passive Alerts** — LinkedIn and Indeed surface listings but offer no follow-through or actual automation of the application workflow.
- **Fragmented Tools** — ATS checkers (Jobscan, Jobalytics) are manual, one-off checks with no persistent record or closed-loop system from discovery to outreach.

**Result:** High burnout and missed opportunities from purely manual, repetitive work — especially for students and early-career seekers applying to startups with no formal HR pipeline.

## The Solution

Hermes-Notion fully automates **discovery → ATS scoring → resume tailoring → drafting**, turning hours of manual work per application into a single approval click.

- **Autonomous Backend** — A scheduled service that autonomously discovers internships, scores ATS alignment, and tailors resumes against each role.
- **Notion Control Panel** — Uses Notion as a clean human-in-the-loop dashboard. Review, edit, and approve drafts before anything is ever sent to a recruiter.
- **Verifiable Audit Trail** — Every action, from discovery to email dispatch, is logged with real timestamps in a tamper-proof Run Log for full transparency.

**Why it's better:** Unlike passive job alerts (LinkedIn, Indeed) or one-off ATS checkers (Jobscan, Jobalytics), Hermes-Notion closes the loop — it acts, keeps a verifiable audit trail, and still keeps a human in control of what's sent.

## System Architecture

```
TRIGGER              SCRAPER                AI PIPELINE          HUMAN GATE                OUTPUT
GitHub Actions   →   Unstop + Company   →   Groq LLM         →   Notion Opportunities  →   Gmail SMTP +
Cron (3x/day)        Research               (ATS scoring &       DB (approve or edit)      Run Log
                                             tailoring)
```

| Layer | Technology |
|---|---|
| **Orchestration** | Python + GitHub Actions |
| **Intelligence** | Groq API (Llama 3) |
| **Interface** | Notion API (SDK) |

> Zero hosting: the entire pipeline runs on free tiers, triggered on a schedule — no server, no local machine.

## Features

| Feature | Description |
|---|---|
| **Scheduled Autonomy** | Runs 3x daily via GitHub Actions. Zero manual triggering required — the system works while you sleep, ensuring you never miss a new listing. |
| **Truthful AI Tailoring** | Powered by Groq LLM. Analyzes real ATS keyword gaps and tailors resumes without fabricating skills, maintaining professional integrity. |
| **Contextual Outreach** | Scrapes actual company websites to research culture and projects, drafting deeply personalized emails that stand out from generic templates. |
| **Human-in-the-Loop** | Strict approval gate inside Notion. Nothing is sent without explicit human review, combining AI efficiency with human judgment. |

*Every feature above runs in the shipped pipeline today — scheduled, logged, and gated.*

## Impact & Scalability

- **Real-World Impact** — Converts hours of repetitive manual work per application into a single approval decision, enabling high-volume, high-quality outreach.
- **Scalable Architecture** — Modular scraper design allows easy addition of new job sources. Notion's database scales to handle thousands of opportunities.
- **Zero Infrastructure Cost** — Runs entirely on free tiers: GitHub Actions, Notion, and Groq API. Zero maintenance or hosting costs for the user.
- **Broad Utility** — Empowers students and early-career seekers to compete with professional applicants through AI-enhanced personalization.

> **100% Autonomous Pipeline** — From Discovery to Outreach with Zero Local Infrastructure

## Live Execution Proof

**1. Opportunities Dashboard** — ATS score, company, draft email — every discovered role in one board.

**2. Verifiable Run Log** — Status, tailored resume, and manual-review flag, timestamped per action.

| JD Summary | Job Link | Status | Tailored Resume | Needs Manual Review |
|---|---|---|---|---|
| Internship role focused on design | unstop.com/... | Pending Approval | Deepanshu Tewathiya | ☐ |
| AI Engineer Intern role centered | unstop.com/... | Sent | Deepanshu Tewathiya | ☑ |
| Role focused on building an... | unstop.com/... | Sent | Deepanshu Tewathiya | ☐ |

---

Hermes-Notion is a production-ready service that bridges autonomous backend execution with human oversight. It satisfies every core requirement: **Real Automation, External API Actions, and a Verifiable Audit Trail.**

# Project Assignment Agent - Scoring Framework

This document outlines the scoring systems used by the **Project Assignment Agent** to evaluate resumes and calculate candidate-to-project compatibility.

---

## 1. Resume Scoring Framework (Max 120 points)

The resume evaluation pipeline generates an objective, explainable score for a candidate's background.

```
Base Categories (100 pts max)
├── 🌐 Open Source       → 0–35 pts
├── 🚀 Self Projects     → 0–30 pts
├── 🏢 Production        → 0–25 pts
└── 💻 Technical Skills  → 0–10 pts

⭐ Bonus Points          → up to +20 pts
⚠️  Deductions           → variable negative

Final Score = categories + bonus − deductions (hard capped at 120)
```

### 🌐 Open Source (0–35 pts)
* **25–35 pts**: Significant contributions to popular repos (1000+ stars), Google Summer of Code (GSoC).
* **15–24 pts**: Smaller OSS projects, active public contributions.
* **5–10 pts**: Only personal repos, Hacktoberfest alone.
* **0–4 pts**: No GitHub presence, or only basic tutorial repos.
* *Rule*: Personal repos do not count as open source. If GitHub data lists only `self_project` types, the score is capped at 10.

### 🚀 Self Projects (0–30 pts)
* **20–30 pts**: Complex, real-world impact, multi-technology stack, active user adoption.
* **10–19 pts**: Moderate complexity, good documentation, multiple features.
* **1–9 pts**: Simple tutorial apps (todo lists, calculators, basic CRUD, weather apps).
* *Rule*: A deduction of −3 to −5 is applied for each project missing a live URL or repository link.

### 🏢 Production Experience (0–25 pts)
* Evaluates internships, jobs, and volunteer work from the `work` and `volunteer` sections.
* Startup founders/co-founders or early-stage startup engineers receive extra consideration.

### 💻 Technical Skills (0–10 pts)
* Assesses the breadth and depth of languages/frameworks listed under `skills`, backed by evidence in work experience or projects.

### ⭐ Bonus Points (Max +20 pts)
* **+5**: Google Summer of Code (GSoC)
* **+3**: Girl Script Summer of Code
* **+3–5**: Startup Founder / Co-founder
* **+2–3**: Early-stage Startup Engineer (first 10-20 employees)
* **+2**: Portfolio URL present in basics
* **+1**: LinkedIn profile present
* **+1–3**: High-quality technical blog

---

## 2. Project Compatibility Scoring (0–100 pts)

To assign candidates to project specs, the agent runs a pair-level compatibility matching assessment focused strictly on technical capabilities.

```
Project Fit Score (100 pts max)
├── ⚙️ Technology Alignment  → Crucial technologies (languages/frameworks)
└── 🌐 Domain Match          → Alignment with project domain (e.g. ML, DevOps)
```

### Scoring Rubric:
* **85–100 (Exceptional Fit)**: Candidate possesses strong hands-on experience in all required technologies and domain-specific concepts, verified through their skills list, work history, or GitHub repositories.
* **70–84 (Good Fit)**: Candidate matches the main technology stack and domain, with minor gaps that can be easily picked up.
* **50–69 (Moderate Fit)**: Candidate has transferable skills (e.g. knows Java/C++ but project requires Go) but lacks direct experience in the domain or primary technologies.
* **0–49 (Poor Fit)**: Major technology mismatch and domain misalignment (e.g., matching a pure frontend designer to a low-level C++ embedded systems project).

## 3. Team Anchor Derivation (Post-Assignment)
To respect skills compatibility as the primary assignment driver, team anchors/leads are never determined during matching. Instead, after assignments are resolved:
1. Assigned candidates are grouped by their matched project.
2. Within each team, candidates are ranked by their general resume quality score (0–120 points).
3. The candidate with the highest general quality score is designated as the **Team Anchor/Lead** (`👑`).

---

## 4. Pipeline Execution Flows

### A. Resume Evaluation Flow
```
PDF → PDFHandler (PyMuPDF) → JSONResume
                            └─► GitHub API Enrichment
                                  └─► ResumeEvaluator (Ollama) → EvaluationData JSON
                                        ├─► Print To Console
                                        └─► Append to resume_evaluations.csv
```

### B. Project Matching & Assignment Flow
```
Resumes Dir (PDFs)  ──► PDFHandler ──► JSONResumes List ──┐
Projects Dir (PDFs) ──► PDFHandler ──► ProjectSpecs List ─┼─► MatchEvaluator (Ollama)
                                                          │     ├─► Check Pair Cache
                                                          │     └─► ProjectFit JSON
                                                          ▼
                                                   Cost Matrix (N x N)
                                                          │
                                                          ▼
                                                  AssignmentEngine
                                            (SciPy linear_sum_assignment)
                                                          │
                                                          ▼
                                                Stdout Team Reports &
                                              project_assignments.csv
```

---

## 5. Key Orchestration Files

| File | Role |
| --- | --- |
| [main.py](file:///C:/My-Files/Github/hiring-agent/main.py) | Entry point (CLI argument router). |
| [hiring_agent/main.py](file:///C:/My-Files/Github/hiring-agent/hiring_agent/main.py) | Orchestration pipeline, handles folder batch runs and project assignment flows. |
| [hiring_agent/schemas/resume.py](file:///C:/My-Files/Github/hiring-agent/hiring_agent/schemas/resume.py) | Pydantic data schemas representing resume, project, and matching objects. |
| [hiring_agent/pipeline/pdf_handler.py](file:///C:/My-Files/Github/hiring-agent/hiring_agent/pipeline/pdf_handler.py) | Converts PDFs to Markdown, structures sections. |
| [hiring_agent/pipeline/evaluator.py](file:///C:/My-Files/Github/hiring-agent/hiring_agent/pipeline/evaluator.py) | Resume scoring LLM coordinator. |
| [hiring_agent/pipeline/match_evaluator.py](file:///C:/My-Files/Github/hiring-agent/hiring_agent/pipeline/match_evaluator.py) | Pair compatibility evaluator with cache layer. |
| [hiring_agent/pipeline/assignment_engine.py](file:///C:/My-Files/Github/hiring-agent/hiring_agent/pipeline/assignment_engine.py) | Balanced optimization engine using SciPy. |
| [hiring_agent/prompts/templates/](file:///C:/My-Files/Github/hiring-agent/hiring_agent/prompts/templates/) | Jinja prompt templates for parsing and matching. |

# Hiring Agent - Scoring Framework

## Score Structure - Max 120 points

```
Base Categories (100 pts max)
├── 🌐 Open Source       → 0–35 pts
├── 🚀 Self Projects     → 0–30 pts
├── 🏢 Production        → 0–25 pts
└── 💻 Technical Skills  → 0–10 pts

⭐ Bonus Points          → up to +20 pts
⚠️  Deductions           → variable negative

Final = categories + bonus − deductions  (hard capped at 120)
```

---

## Open Source (0–35 pts)

| Range  | Criteria                                                        |
| ------ | --------------------------------------------------------------- |
| 25–35 | Contributions to 1000+ star repos, Google Summer of Code (GSoC) |
| 15–24 | Smaller OSS projects, active contributions to other repos       |
| 5–10  | Only personal repos, Hacktoberfest alone                        |
| 0–4   | No GitHub presence, only tutorial repos                         |

> **Key rule:** Personal GitHub repos do **not** count as open source. If GitHub data shows all projects as `self_project` type, score is forced ≤ 10.

---

## Self Projects (0–30 pts)

| Range  | Criteria                                                            |
| ------ | ------------------------------------------------------------------- |
| 20–30 | Complex, real-world impact, multi-tech stack, user adoption         |
| 10–19 | Moderate complexity, good documentation, multiple features          |
| 1–9   | Todo apps, calculators, basic CRUD, weather apps, note-taking apps  |
| 0      | No projects or extremely basic with no technical skill demonstrated |

> **No link penalty:** −3 to −5 per project without a GitHub link or live demo URL.

### Complex vs. Simple Projects

**Simple (low scores):** Todo lists, calculators, basic CRUD, weather apps, note-taking apps, recipe apps, basic sentiment analysis, simple e-commerce clones.

**Complex (high scores):** Full-stack with auth + DB, ML/AI apps, real-time apps (chat/streaming), microservices architecture, mobile apps with native features, projects with significant user adoption.

---

## Production (0–25 pts)

- Internships, full-time jobs, volunteer/contract work
- Analyzed from `work` and `volunteer` resume sections
- **Extra consideration** for founder/co-founder roles or early-stage startup engineers (first 10–20 employees)

---

## Technical Skills (0–10 pts)

- Breadth of languages and frameworks from the `skills` section
- Evidence drawn from project descriptions, work history, and competitions

---

## Bonus Points (max 20 total)

| Points | Trigger                                               |
| ------ | ----------------------------------------------------- |
| +5     | Google Summer of Code (GSoC) participation            |
| +3     | Girl Script Summer of Code participation              |
| +3–5  | Startup founder / co-founder experience               |
| +2–3  | Early-stage startup engineer (first 10–20 employees) |
| +2     | Portfolio website present in`basics.url`            |
| +1     | LinkedIn profile present                              |
| +1–3  | High-quality technical blog (if blog data provided)   |

> **Hard cap:** Total bonus points cannot exceed 20 under any circumstances.

---

## Deductions

| Trigger                                                     | Deduction       |
| ----------------------------------------------------------- | --------------- |
| Resume contains only simple tutorial projects               | −2 to −5      |
| Each additional simple project beyond the first             | −1 to −3      |
| Generic project names (e.g. "Todo App", "Calculator")       | −1 each        |
| Project with no link, GitHub, or live demo                  | −3 to −5 each |
| Project with GitHub link but no live demo                   | −2 to −3 each |
| Broken or inactive links                                    | −1 to −2 each |
| All GitHub projects are`self_project` type (no real OSS)  | −3 to −5      |
| Hacktoberfest without contributions to significant projects | −3 to −5      |

---

## Fairness Rules

The LLM is **explicitly instructed to ignore** the following when scoring:

- Candidate name, gender, or personal demographics
- College / university name
- CGPA / GPA / academic grades
- City, location, or geographical information

**Evaluation is based only on:**

- Technical skills and programming languages
- Project complexity and real-world impact
- Open source contributions and community involvement
- Work experience and production-level contributions
- Technical communication and documentation

---

## Program Distinction (enforced in prompt)

- **"Google Summer of Code (GSoC)"** and **"Girl Script Summer of Code"** are completely different programs.
- The prompt explicitly forbids using "GSoC" as shorthand for Girl Script Summer of Code.

---

## Pipeline Flow

```
PDF
 └─► PyMuPDF (text extraction via pymupdf_rag.to_markdown)
      └─► LLM - 6 separate calls, one per section:
           basics, work, education, skills, projects, awards
      └─► GitHub API - fetched from profile URL found in resume
      └─► Blog data (optional)
           └─► All merged into a single resume_text string
                └─► LLM - 1 evaluation call → EvaluationData JSON
                     └─► Printed to console
                     └─► Appended to resume_evaluations.csv (dev mode)
```

> **Note:** The 6-section PDF parsing is why the script hits Gemini free-tier rate limits quickly (6+ LLM calls per resume).

---

## Key Files

| File                                                         | Role                                                     |
| ------------------------------------------------------------ | -------------------------------------------------------- |
| `score.py`                                                 | Entry point, orchestrates the full pipeline              |
| `pdf.py`                                                   | PDF text extraction + per-section LLM calls              |
| `evaluator.py`                                             | Single LLM call to score the resume                      |
| `github.py`                                                | Fetches GitHub profile and repo data                     |
| `models.py`                                                | Pydantic models +`OllamaProvider` / `GeminiProvider` |
| `llm_utils.py`                                             | Provider routing based on model name                     |
| `prompt.py`                                                | Model name → provider mapping, API key loading          |
| `prompts/templates/resume_evaluation_criteria.jinja`       | Full scoring rubric sent to LLM                          |
| `prompts/templates/resume_evaluation_system_message.jinja` | System prompt for the evaluator                          |

# Project Assignment Agent

<p align="center"><strong>Resume-to-Project assignment pipeline</strong> that extracts structured data from resume and project spec PDFs, enriches profiles with GitHub signals, scores candidate-project compatibility, and distributes candidates equally to projects using a globally optimal solver.</p>

<p align="center">
  <a href="https://www.python.org/downloads/release/python-3110/">
    <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue.svg">
  </a>
  <a href="https://github.com/interviewstreet/hiring-agent/blob/master/LICENSE">
    <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-yellow.svg">
  </a>
  <a href="https://github.com/psf/black">
    <img alt="Code style: Black" src="https://img.shields.io/badge/code%20style-Black-000000.svg">
  </a>
</p>

---

## Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation and Setup](#installation-and-setup)
  - [Prerequisites](#prerequisites)
  - [Quick setup with pip](#quick-setup-with-pip)
  - [Ollama models](#ollama-models)
- [Configuration](#configuration)
- [How it works](#how-it-works)
- [CLI usage](#cli-usage)
  - [Legacy Resume Scoring](#legacy-resume-scoring)
  - [Balanced Candidate-Project Assignment](#balanced-candidate-project-assignment)
- [Directory layout](#directory-layout)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Project Assignment Agent parses resume and project specification PDFs to Markdown, structures them using a local LLM via Ollama, enriches resumes with GitHub signals, and scores candidate-to-project compatibility. Finally, it uses SciPy's Hungarian algorithm to assign candidates to projects under a strict equal distribution capacity constraint, maximizing overall suitability. The pipeline runs fully local — no cloud API required.

---

## Architecture

<table>
<tr>
<td>

**Flow**

1. `hiring_agent/utils/pymupdf_rag.py` converts resume and project PDF pages to Markdown.
2. `hiring_agent/pipeline/pdf_handler.py` parses resumes and project specifications into structured JSON using local LLM calls and Jinja templates.
3. `hiring_agent/pipeline/github.py` enriches resumes with GitHub profiles.
4. `hiring_agent/pipeline/match_evaluator.py` evaluates candidate compatibility for each project.
5. `hiring_agent/pipeline/assignment_engine.py` constructs a cost matrix and runs SciPy's Hungarian algorithm to assign candidates to project slots equally.
6. `hiring_agent/main.py` orchestrates the assignment flow and outputs reports and CSVs.

</td>
<td>

**Key modules**

- `hiring_agent/schemas/resume.py`
  Pydantic schemas for resumes, projects, and matching evaluations.

- `hiring_agent/pipeline/match_evaluator.py`
  Pair-level matching and caching system.

- `hiring_agent/pipeline/assignment_engine.py`
  Balanced distribution solver using `scipy.optimize.linear_sum_assignment`.

- `hiring_agent/providers/ollama.py`
  Ollama provider wrapper.

- `hiring_agent/prompts/`
  Jinja templates for extraction, scoring, and matching.

- `hiring_agent/config.py`
  Single source of truth for model configurations.

</td>
</tr>
</table>

---

## Installation and Setup

### Prerequisites

- **Python 3.11+**
  The repository pins `.python-version` to 3.11.13.

- **Ollama**
  Install from the [official site](https://ollama.com/), then run `ollama serve`.

### Quick setup with pip

```bash
$ git clone https://github.com/interviewstreet/hiring-agent
$ cd hiring-agent

$ python -m venv .venv
# Linux or macOS
$ source .venv/bin/activate
# Windows
# .venv\Scripts\activate

$ pip install -r requirements.txt
```

### Ollama Models

Pull the model you want to use. For example:

```bash
$ ollama pull gemma3:4b
```

---

## Configuration

Copy the template and set your environment variables.

```bash
$ cp .env.example .env
```

**Environment variables**

| Variable        | Default      | Description                                                            |
| --------------- | ------------ | ---------------------------------------------------------------------- |
| `DEFAULT_MODEL` | `gemma3:4b`  | Ollama model name passed to the provider.                              |
| `GITHUB_TOKEN`  | *(optional)* | Increases GitHub API rate limit from 60/hr to 5000/hr.                |

---

## How it works

<details>
<summary><b>1) PDF extraction & parsing</b></summary>

- Resumes and project descriptions are converted to Markdown via PyMuPDF.
- `PDFHandler` calls Ollama with custom templates to produce structured schemas (`JSONResume` and `ProjectRequirements`).

</details>

<details>
<summary><b>2) Compatibility Matching</b></summary>

- `MatchEvaluator` generates fit evaluations between every candidate and project.
- To prevent redundant LLM calls, evaluation results are aggressively cached on a per-pair basis under `cache/matchcache_<candidate>_<project>.json`.

</details>

<details>
<summary><b>3) Globally Optimal Assignment</b></summary>

- `AssignmentEngine` maps projects to available slots (e.g. for $N$ candidates and $P$ projects, capacity per project is either $\lfloor N/P \rfloor$ or $\lceil N/P \rceil$).
- It builds an $N \times N$ cost matrix where cost represents `100 - fit_score`.
- It executes SciPy's Hungarian algorithm (`linear_sum_assignment`) to find the assignment that minimizes total cost, guaranteeing balanced team sizing while maximizing alignment quality.

</details>

---

## CLI usage

### Balanced Candidate-Project Assignment

Runs the parsing, pair compatibility matching, and balanced distribution algorithm.

```bash
python main.py --resumes /path/to/resumes/ --projects /path/to/projects/
```

* Results will be printed to stdout and saved in `project_assignments.csv`.
* Individual match JSON results are cached under `cache/` to accelerate subsequent runs.

### Legacy Resume Scoring

#### Score a single resume
```bash
python main.py /path/to/resume.pdf
```

#### Score all resumes in a folder
```bash
python main.py /path/to/resumes/
```

---

## Directory layout

```text
.
├── main.py                          ← entry point (supports assignment & legacy flags)
├── .env.example
├── .python-version
├── requirements.txt
└── hiring_agent/
    ├── config.py                    ← model selection and parameters
    ├── main.py                      ← orchestration pipeline
    ├── schemas/
    │   └── resume.py                ← Pydantic schemas (added project specs)
    ├── providers/
    │   └── ollama.py                ← Ollama provider
    ├── utils/
    │   ├── llm.py                   ← response cleanup helpers
    │   ├── transform.py             ← JSON Resume normalization
    │   └── pymupdf_rag.py           ← PDF-to-Markdown vendor utility
    ├── pipeline/
    │   ├── pdf_handler.py           ← PDF extraction pipeline (added project extraction)
    │   ├── evaluator.py             ← legacy scoring pipeline
    │   ├── github.py                ← GitHub enrichment pipeline
    │   ├── match_evaluator.py       ← project compatibility matching
    │   └── assignment_engine.py     ← SciPy-based balanced assignment engine
    └── prompts/
        ├── template_manager.py      ← Jinja2 template loader (added project prompts)
        └── templates/
            ├── awards.jinja
            ├── basics.jinja
            ├── education.jinja
            ├── github_project_selection.jinja
            ├── projects.jinja
            ├── resume_evaluation_criteria.jinja
            ├── resume_evaluation_system_message.jinja
            ├── skills.jinja
            ├── system_message.jinja
            ├── work.jinja
            ├── project_parsing.jinja
            └── project_matching.jinja
```

---

## Contributing

Please read the [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines.

---

## License

[MIT](https://github.com/interviewstreet/hiring-agent/blob/master/LICENSE) © HackerRank

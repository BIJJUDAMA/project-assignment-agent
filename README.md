# Hiring Agent

<p align="center"><strong>Resume-to-Score pipeline</strong> that extracts structured data from PDFs, enriches with GitHub signals, and outputs a fair, explainable evaluation.</p>

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
- [Directory layout](#directory-layout)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Hiring Agent parses a resume PDF to Markdown, extracts sectioned JSON using a local LLM via Ollama, augments the data with GitHub profile and repository signals, then produces an objective evaluation with category scores, evidence, bonus points, and deductions. The pipeline runs fully local — no cloud API required.

---

## Architecture

<table>
<tr>
<td>

**Flow**

1. `hiring_agent/utils/pymupdf_rag.py` converts PDF pages to Markdown-like text.
2. `hiring_agent/pipeline/pdf_handler.py` calls the LLM per section using Jinja templates.
3. `hiring_agent/pipeline/github.py` fetches profile and repos, classifies projects, and asks the LLM to select the top 7.
4. `hiring_agent/pipeline/evaluator.py` runs a strict-scored evaluation with fairness constraints.
5. `hiring_agent/main.py` orchestrates everything end to end and always writes a CSV row.

</td>
<td>

**Key modules**

- `hiring_agent/schemas/resume.py`
  Pydantic schemas for all resume and evaluation data.

- `hiring_agent/providers/ollama.py`
  Ollama provider wrapper.

- `hiring_agent/utils/llm.py`
  Response cleanup (think-block stripping, JSON fence removal).

- `hiring_agent/utils/transform.py`
  Normalization from loose LLM JSON to JSON Resume style.

- `hiring_agent/prompts/`
  All Jinja templates for extraction and scoring.

- `hiring_agent/config.py`
  Single source of truth for model selection and parameters.

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

If you want different results, you can pull other models such as:

```bash
# For higher system configuration
$ ollama pull gemma3:12b

# For lower system configuration
$ ollama pull gemma3:1b
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

Model inference parameters (temperature, top_p) are configured per-model in `hiring_agent/config.py`.

---

## How it works

<details>
<summary><b>1) PDF extraction</b></summary>

- `hiring_agent/utils/pymupdf_rag.py` and `hiring_agent/pipeline/pdf_handler.py` read the PDF using PyMuPDF and convert pages to Markdown-like text.
- The `to_markdown` routine handles headings, links, tables, and basic formatting.

</details>

<details>
<summary><b>2) Section parsing with templates</b></summary>

- `hiring_agent/prompts/templates/*.jinja` define strict instructions for each section:
  Basics, Work, Education, Skills, Projects, Awards.
- `PDFHandler` calls the LLM per section and assembles a `JSONResume` object.

</details>

<details>
<summary><b>3) GitHub enrichment</b></summary>

- `hiring_agent/pipeline/github.py` extracts a username from the resume profiles, fetches profile and repos, and classifies each project.
- It asks the LLM to select exactly 7 unique projects with a minimum author commit threshold, favoring meaningful contributions.

</details>

<details>
<summary><b>4) Evaluation</b></summary>

- `hiring_agent/pipeline/evaluator.py` uses templates that encode fairness and scoring rules.
- Scores include `open_source`, `self_projects`, `production`, and `technical_skills`, plus bonus and deductions, with evidence for each category.

</details>

<details>
<summary><b>5) Output and CSV export</b></summary>

- `hiring_agent/main.py` prints a readable summary to stdout.
- A row is always appended to `resume_evaluations.csv` after every run.
- Intermediate JSON is cached under `cache/` when `DEVELOPMENT_MODE=True` in `hiring_agent/config.py`.

</details>

---

## CLI usage

### Score a single resume

```bash
$ python main.py /path/to/resume.pdf
```

### Score all resumes in a folder

```bash
$ python main.py /path/to/resumes/
```

What happens:

1. If development mode is on, the PDF extraction result is cached to `cache/resumecache_<basename>.json`.
2. If a GitHub profile is found in the resume, repositories are fetched and cached to `cache/githubcache_<basename>.json`.
3. The evaluator prints a report and appends a CSV row to `resume_evaluations.csv`.
4. For folder runs, a summary shows how many resumes were processed successfully.

---

## Directory layout

```text
.
├── main.py                          ← entry point (single file or folder)
├── .env.example
├── .python-version
├── requirements.txt
└── hiring_agent/
    ├── config.py                    ← model selection and parameters
    ├── main.py                      ← orchestration pipeline
    ├── schemas/
    │   └── resume.py                ← Pydantic schemas
    ├── providers/
    │   └── ollama.py                ← Ollama provider
    ├── utils/
    │   ├── llm.py                   ← response cleanup helpers
    │   ├── transform.py             ← JSON Resume normalization
    │   └── pymupdf_rag.py           ← PDF-to-Markdown vendor utility
    ├── pipeline/
    │   ├── pdf_handler.py           ← PDF extraction pipeline
    │   ├── evaluator.py             ← scoring pipeline
    │   └── github.py                ← GitHub enrichment pipeline
    └── prompts/
        ├── template_manager.py      ← Jinja2 template loader
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
            └── work.jinja
```

---

## Contributing

Please read the [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines on filing issues, proposing changes, and submitting pull requests. Key principles include:

- Keep prompts declarative and provider-agnostic.
- Validate changes with a couple of real resumes.
- Add or adjust unit-free smoke tests that call each stage with minimal inputs.

---

## License

[MIT](https://github.com/interviewstreet/hiring-agent/blob/master/LICENSE) © HackerRank

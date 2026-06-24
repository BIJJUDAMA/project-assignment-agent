# Project Assignment Agent - Matching and Assignment Engine

This document details the architecture, evaluation criteria, caching strategy, and mathematical optimization used by the **Project Assignment Agent** to pair candidates with projects.

---

## 1. Candidate-Project Compatibility Matching (LLM Stage)

For every candidate and project pair, the agent uses a local LLM via Ollama to evaluate compatibility.

### Inputs
1. **Candidate Profile**: Parsed resume text ([JSONResume](file:///C:/My-Files/Github/hiring-agent/hiring_agent/schemas/resume.py#L182)) enriched with public GitHub profile and repository metadata.
2. **Project Specification**: Parsed project requirements (`ProjectRequirements` schema) containing title, description, required technologies, preferred skills, and core domain.

### Prompt Template
The matching logic uses the Jinja2 template `project_matching.jinja`. It directs the LLM to perform an objective evaluation of:
* **Technology Overlap**: Does the candidate know the required languages/frameworks?
* **Domain Experience**: Does the candidate have experience in the project's core domain (e.g. ML, DevOps, Frontend)?
* **Complexity Alignment**: Does the candidate's project or work history demonstrate an ability to execute the project's requirements?

### Structured Output
The LLM returns a structured JSON response corresponding to the `ProjectFit` schema:
```json
{
  "candidate_name": "Jane Doe",
  "project_title": "ML Pipeline Optimization",
  "fit_score": 88.5,
  "strengths": [
    "Proficient in Python and PyTorch as demonstrated in their open source contributions",
    "Completed a similar project on pipeline acceleration"
  ],
  "gaps": [
    "No direct experience with CUDA or GPU performance tuning"
  ],
  "reasoning": "Jane is an exceptional fit because she has a strong Python/ML background, though she will need to adapt to GPU-level optimizations."
}
```

---

## 2. Granular Caching Layer

Because evaluating $N$ candidates against $P$ projects requires $N \times P$ local LLM calls (e.g. 1,200 calls for 80 candidates and 15 projects), the agent uses a **pair-level match cache** to avoid redundant computations:

* **Cache Directory**: `cache/`
* **File Naming Pattern**: `matchcache_<safe_candidate_name>_<safe_project_title>.json`
* **Workflow**:
  1. For each candidate-project pair, the matcher checks if the matching cache file exists.
  2. If the cache exists, it is loaded instantaneously.
  3. If it doesn't, the LLM is queried sequentially, and the result is written back to the cache directory.
* **Benefits**: Subsequent pipeline runs (e.g. after adding one new project or fixing a single resume) execute instantly, only querying the LLM for the newly introduced pairs.

---

## 3. Mathematically Optimal Assignment (SciPy Stage)

To ensure **equal distribution** of members across all projects while **maximizing overall match quality**, the engine models the assignment as a **Linear Sum Assignment Problem (LSAP)**.

### Step A: Target Capacities
For $N$ candidates and $P$ projects, we calculate the exact target capacity for each project:
* `min_slots = N // P`
* `remainder = N % P`
* Projects $1$ to `remainder` get `min_slots + 1` slots.
* The remaining projects get `min_slots` slots.
* *Example*: With 80 candidates and 15 projects:
  * 5 projects get 6 slots.
  * 10 projects get 5 slots.
  * Total slots = $(5 \times 6) + (10 \times 5) = 80$ slots.

### Step B: Cost Matrix Construction
SciPy's optimization solver minimizes total cost. To maximize compatibility, we define the cost of assigning Candidate $i$ to Project Slot $s$ as:
$$\text{Cost} = 100.0 - \text{CompatibilityScore}$$

We construct a square $N \times N$ matrix where rows represent candidates and columns represent individual project slots:
* If Project A has 6 slots, columns 0–5 represent those slots.
* If Project B has 5 slots, columns 6–10 represent those slots.

### Step C: The Hungarian Algorithm Solver
We pass the cost matrix to `scipy.optimize.linear_sum_assignment`:
```python
from scipy.optimize import linear_sum_assignment

# row_ind maps to candidates, col_ind maps to slots
row_ind, col_ind = linear_sum_assignment(cost_matrix)
```
This algorithm uses the Hungarian method (modified Jonker-Volgenant) to solve the bipartite matching in $O(N^3)$ time, yielding the globally optimal distribution.

---

## 4. Console and CSV Reporting

Once the solver runs, the orchestrator:
1. Groups the assigned candidates by project.
2. Prints a structured breakdown to stdout.
3. Saves a summary sheet in `project_assignments.csv` containing fields for candidate name, project title, fit score, strengths, gaps, and reasoning.

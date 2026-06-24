"""
Assignment Engine: distributes candidates equally among projects using SciPy's
linear sum assignment (Hungarian algorithm). Optimizes strictly for skill and domain
compatibility to maximize overall team matching quality.
"""

import logging
from typing import List, Dict, Tuple, Any
import numpy as np
from scipy.optimize import linear_sum_assignment

from schemas.resume import JSONResume, ProjectRequirements, ProjectFit

logger = logging.getLogger(__name__)


class AssignmentEngine:
    def assign_projects(
        self,
        candidates: List[Tuple[JSONResume, str, float]],  # List of (resume_data, candidate_name, quality_score)
        projects: List[ProjectRequirements],
        match_evals: Dict[str, Dict[str, ProjectFit]],
    ) -> List[Dict[str, Any]]:
        """
        Assign candidates to projects to maximize the overall compatibility score
        while ensuring an equal distribution of members.
        """
        N = len(candidates)
        P = len(projects)

        if N == 0 or P == 0:
            logger.warning("No candidates or projects provided for assignment.")
            return []

        # 1. Determine capacities for each project to ensure equal distribution
        min_slots = N // P
        remainder = N % P

        project_capacities = {}
        for idx, project in enumerate(projects):
            capacity = min_slots + (1 if idx < remainder else 0)
            project_capacities[project.title] = capacity
            logger.info(f"Project '{project.title}' target capacity: {capacity}")

        # 2. Build the slot column mapping
        slot_to_project = []
        for project in projects:
            capacity = project_capacities[project.title]
            for _ in range(capacity):
                slot_to_project.append(project)

        # Pad or truncate slot list to match N exactly (needed if N < P)
        if len(slot_to_project) < N:
            while len(slot_to_project) < N:
                slot_to_project.append(projects[len(slot_to_project) % len(projects)])
        elif len(slot_to_project) > N:
            slot_to_project = slot_to_project[:N]

        # 3. Construct the cost matrix
        # Matrix size: N candidates (rows) x N project slots (columns)
        cost_matrix = np.zeros((N, N))

        for row_idx, (_, candidate_name, _) in enumerate(candidates):
            for col_idx, project in enumerate(slot_to_project):
                # Retrieve match score, default to 0 if not found
                fit = match_evals.get(candidate_name, {}).get(project.title)
                score = fit.fit_score if fit else 0.0
                
                # SciPy minimizes cost, so cost = 100 - score
                cost_matrix[row_idx, col_idx] = 100.0 - score

        # 4. Solve the Linear Sum Assignment Problem (Hungarian Algorithm)
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        # 5. Compile assignments
        assignments = []
        for row_idx, col_idx in zip(row_ind, col_ind):
            resume, candidate_name, quality_score = candidates[row_idx]
            assigned_project = slot_to_project[col_idx]
            fit = match_evals.get(candidate_name, {}).get(assigned_project.title)

            assignments.append(
                {
                    "candidate_name": candidate_name,
                    "project_title": assigned_project.title,
                    "fit_score": fit.fit_score if fit else 0.0,
                    "strengths": fit.strengths if fit else [],
                    "gaps": fit.gaps if fit else [],
                    "reasoning": fit.reasoning if fit else "No evaluation reasoning available",
                    "resume_data": resume,
                    "is_anchor": False,
                    "quality_score": quality_score,
                }
            )

        return assignments

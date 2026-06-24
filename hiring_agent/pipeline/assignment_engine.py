"""
Assignment Engine: distributes candidates equally among projects using SciPy's
linear sum assignment (Hungarian algorithm). Utilizes a two-stage seniority 
balancing strategy to ensure every project team receives at least one high-performing
anchor candidate, while maximizing overall fit quality.
"""

import logging
from typing import List, Dict, Tuple, Any
import numpy as np
from scipy.optimize import linear_sum_assignment

from hiring_agent.schemas.resume import JSONResume, ProjectRequirements, ProjectFit

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
        while ensuring an equal distribution of members and balancing team seniority.
        """
        N = len(candidates)
        P = len(projects)

        if N == 0 or P == 0:
            logger.warning("No candidates or projects provided for assignment.")
            return []

        # Enforce equal distribution capacities
        min_slots = N // P
        remainder = N % P

        project_capacities = {}
        for idx, project in enumerate(projects):
            capacity = min_slots + (1 if idx < remainder else 0)
            project_capacities[project.title] = capacity
            logger.info(f"Project '{project.title}' target capacity: {capacity}")

        # If N < P, we fall back to standard single-stage assignment
        if N < P:
            logger.warning("Candidates count is less than projects count. Running standard single-stage assignment.")
            return self._assign_standard(candidates, projects, project_capacities, match_evals)

        # Stage 1: Sort candidates by general quality score descending
        # Candidates schema: (resume_data, candidate_name, quality_score)
        sorted_candidates = sorted(candidates, key=lambda c: c[2], reverse=True)
        
        # Select top P candidates as anchors/seniors
        seniors = sorted_candidates[:P]
        remaining_candidates = sorted_candidates[P:]

        logger.info(f"🛡️ Seniority Balancing: Selected top {P} candidates as project team anchors.")
        for s in seniors:
            logger.info(f"   Anchor: {s[1]} (General Quality Score: {s[2]:.1f})")

        # Stage 2: Round 1 - Assign one anchor to each project
        anchor_cost_matrix = np.zeros((P, P))
        for row_idx, (_, candidate_name, _) in enumerate(seniors):
            for col_idx, project in enumerate(projects):
                fit = match_evals.get(candidate_name, {}).get(project.title)
                score = fit.fit_score if fit else 0.0
                anchor_cost_matrix[row_idx, col_idx] = 100.0 - score

        s_row_ind, s_col_ind = linear_sum_assignment(anchor_cost_matrix)

        assignments = []
        assigned_anchors = {}  # project_title -> candidate_name
        
        for row_idx, col_idx in zip(s_row_ind, s_col_ind):
            resume, candidate_name, quality_score = seniors[row_idx]
            assigned_project = projects[col_idx]
            fit = match_evals.get(candidate_name, {}).get(assigned_project.title)
            
            assigned_anchors[assigned_project.title] = candidate_name
            assignments.append(
                {
                    "candidate_name": candidate_name,
                    "project_title": assigned_project.title,
                    "fit_score": fit.fit_score if fit else 0.0,
                    "strengths": fit.strengths if fit else [],
                    "gaps": fit.gaps if fit else [],
                    "reasoning": fit.reasoning if fit else "No evaluation reasoning available",
                    "resume_data": resume,
                    "is_anchor": True,
                    "quality_score": quality_score,
                }
            )

        # Stage 3: Round 2 - Assign remaining N - P candidates to remaining slots
        # For each project, decrement capacity by 1 (since 1 slot was filled by the anchor)
        remaining_capacities = {}
        for proj_title, cap in project_capacities.items():
            remaining_capacities[proj_title] = cap - 1

        # Build slot columns for remaining slots
        remaining_slots = []
        for project in projects:
            cap = remaining_capacities[project.title]
            for _ in range(cap):
                remaining_slots.append(project)

        rem_N = len(remaining_candidates)
        assert len(remaining_slots) == rem_N, f"Mismatch: slots={len(remaining_slots)}, candidates={rem_N}"

        if rem_N > 0:
            remaining_cost_matrix = np.zeros((rem_N, rem_N))
            for row_idx, (_, candidate_name, _) in enumerate(remaining_candidates):
                for col_idx, project in enumerate(remaining_slots):
                    fit = match_evals.get(candidate_name, {}).get(project.title)
                    score = fit.fit_score if fit else 0.0
                    remaining_cost_matrix[row_idx, col_idx] = 100.0 - score

            r_row_ind, r_col_ind = linear_sum_assignment(remaining_cost_matrix)

            for row_idx, col_idx in zip(r_row_ind, r_col_ind):
                resume, candidate_name, quality_score = remaining_candidates[row_idx]
                assigned_project = remaining_slots[col_idx]
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

    def _assign_standard(
        self,
        candidates: List[Tuple[JSONResume, str, float]],
        projects: List[ProjectRequirements],
        project_capacities: Dict[str, int],
        match_evals: Dict[str, Dict[str, ProjectFit]],
    ) -> List[Dict[str, Any]]:
        """Standard single-stage assignment when seniority balancing is not applicable."""
        N = len(candidates)
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

        cost_matrix = np.zeros((N, N))
        for row_idx, (_, candidate_name, _) in enumerate(candidates):
            for col_idx, project in enumerate(slot_to_project):
                fit = match_evals.get(candidate_name, {}).get(project.title)
                score = fit.fit_score if fit else 0.0
                cost_matrix[row_idx, col_idx] = 100.0 - score

        row_ind, col_ind = linear_sum_assignment(cost_matrix)

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

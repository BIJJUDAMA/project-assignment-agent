"""
Main orchestration pipeline for the hiring agent.

Entry point logic: PDF → parse → GitHub → evaluate → score → CSV output.
Run via:
    python -m hiring_agent <pdf_path>
    python score.py <pdf_path>          (backward-compatible shim)
"""

import os
import sys
import json
import logging
import csv
from pathlib import Path
from typing import Optional

from hiring_agent.pipeline.pdf_handler import PDFHandler
from hiring_agent.pipeline.github import fetch_and_display_github_info
from hiring_agent.schemas.resume import JSONResume, EvaluationData, ProjectRequirements, ProjectFit
from hiring_agent.pipeline.evaluator import ResumeEvaluator
from hiring_agent.pipeline.match_evaluator import MatchEvaluator
from hiring_agent.pipeline.assignment_engine import AssignmentEngine
from hiring_agent.config import DEFAULT_MODEL, MODEL_PARAMETERS, DEVELOPMENT_MODE
from hiring_agent.utils.transform import (
    transform_evaluation_response,
    convert_json_resume_to_text,
    convert_github_data_to_text,
    convert_blog_data_to_text,
)

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)5s - %(lineno)5d - %(funcName)33s - %(levelname)5s - %(message)s",
)


def print_evaluation_results(
    evaluation: EvaluationData, candidate_name: str = "Candidate"
):
    """Print evaluation results in a readable format."""
    print("\n" + "=" * 80)
    print(f"📊 RESUME EVALUATION RESULTS FOR: {candidate_name}")
    print("=" * 80)

    if not evaluation:
        print("❌ No evaluation data available")
        return

    # Calculate overall score
    total_score = 0
    max_score = 0

    if hasattr(evaluation, "scores") and evaluation.scores:
        for category_name, category_data in evaluation.scores.model_dump().items():
            category_score = min(category_data["score"], category_data["max"])
            total_score += category_score
            max_score += category_data["max"]

            # Log warning if score was capped
            if category_score < category_data["score"]:
                print(
                    f"⚠️  Warning: {category_name} score capped from {category_data['score']} to {category_score} (max: {category_data['max']})"
                )

    # Add bonus points
    if hasattr(evaluation, "bonus_points") and evaluation.bonus_points:
        total_score += evaluation.bonus_points.total

    # Subtract deductions
    if hasattr(evaluation, "deductions") and evaluation.deductions:
        total_score -= evaluation.deductions.total

    # Ensure total score doesn't exceed maximum possible score
    max_possible_score = max_score + 20  # 120 (100 categories + 20 bonus)
    if total_score > max_possible_score:
        total_score = max_possible_score
        print(f"⚠️  Warning: Total score capped at maximum possible value")

    # Overall Score
    print(f"\n🎯 OVERALL SCORE: {total_score:.1f}/{max_score}")

    # Detailed Scores
    print("\n📈 DETAILED SCORES:")
    print("-" * 60)

    if hasattr(evaluation, "scores") and evaluation.scores:
        # Define category maximums
        category_maxes = {
            "open_source": 35,
            "self_projects": 30,
            "production": 25,
            "technical_skills": 10,
        }

        # Open Source
        if hasattr(evaluation.scores, "open_source") and evaluation.scores.open_source:
            os_score = evaluation.scores.open_source
            capped_score = min(os_score.score, category_maxes["open_source"])
            print(f"🌐 Open Source:          {capped_score}/{os_score.max}")
            print(f"   Evidence: {os_score.evidence}")
            print()

        # Self Projects
        if (
            hasattr(evaluation.scores, "self_projects")
            and evaluation.scores.self_projects
        ):
            sp_score = evaluation.scores.self_projects
            capped_score = min(sp_score.score, category_maxes["self_projects"])
            print(f"🚀 Self Projects:        {capped_score}/{sp_score.max}")
            print(f"   Evidence: {sp_score.evidence}")
            print()

        # Production Experience
        if hasattr(evaluation.scores, "production") and evaluation.scores.production:
            prod_score = evaluation.scores.production
            capped_score = min(prod_score.score, category_maxes["production"])
            print(f"🏢 Production Experience: {capped_score}/{prod_score.max}")
            print(f"   Evidence: {prod_score.evidence}")
            print()

        # Technical Skills
        if (
            hasattr(evaluation.scores, "technical_skills")
            and evaluation.scores.technical_skills
        ):
            tech_score = evaluation.scores.technical_skills
            capped_score = min(tech_score.score, category_maxes["technical_skills"])
            print(f"💻 Technical Skills:     {capped_score}/{tech_score.max}")
            print(f"   Evidence: {tech_score.evidence}")
            print()

    # Bonus Points
    if hasattr(evaluation, "bonus_points") and evaluation.bonus_points:
        print(f"\n⭐ BONUS POINTS: {evaluation.bonus_points.total}")
        print("-" * 30)
        print(f"   {evaluation.bonus_points.breakdown}")

    # Deductions
    if (
        hasattr(evaluation, "deductions")
        and evaluation.deductions
        and evaluation.deductions.total > 0
    ):
        print(f"\n⚠️  DEDUCTIONS: -{evaluation.deductions.total}")
        print("-" * 30)
        if evaluation.deductions.reasons:
            print(f"   {evaluation.deductions.reasons}")

    # Key Strengths
    if hasattr(evaluation, "key_strengths") and evaluation.key_strengths:
        print(f"\n✅ KEY STRENGTHS:")
        print("-" * 30)
        for i, strength in enumerate(evaluation.key_strengths, 1):
            print(f"  {i}. {strength}")

    # Areas for Improvement
    if (
        hasattr(evaluation, "areas_for_improvement")
        and evaluation.areas_for_improvement
    ):
        print(f"\n🔧 AREAS FOR IMPROVEMENT:")
        print("-" * 30)
        for i, area in enumerate(evaluation.areas_for_improvement, 1):
            print(f"  {i}. {area}")

    print("\n" + "=" * 80)


def _evaluate_resume(
    resume_data: JSONResume, github_data: dict = None, blog_data: dict = None
) -> Optional[EvaluationData]:
    """Evaluate the resume using AI and display results."""

    model_params = MODEL_PARAMETERS.get(DEFAULT_MODEL)
    evaluator = ResumeEvaluator(model_name=DEFAULT_MODEL, model_params=model_params)

    # Convert JSON resume data to text
    resume_text = convert_json_resume_to_text(resume_data)

    # Add GitHub data if available
    if github_data:
        github_text = convert_github_data_to_text(github_data)
        resume_text += github_text

    # Add blog data if available
    if blog_data:
        blog_text = convert_blog_data_to_text(blog_data)
        resume_text += blog_text

    # Evaluate the enhanced resume
    evaluation_result = evaluator.evaluate_resume(resume_text)

    # print(evaluation_result)

    return evaluation_result


def is_valid_resume_data(resume_data: JSONResume) -> bool:
    """Check if the resume data has at least some extracted core content."""
    if not resume_data:
        return False
    core_sections = [
        resume_data.basics,
        resume_data.work,
        resume_data.education,
        resume_data.skills,
        resume_data.projects,
    ]
    return any(section is not None for section in core_sections)


def find_profile(profiles, network):
    if not profiles:
        return None
    return next(
        (p for p in profiles if p.network and p.network.lower() == network.lower()),
        None,
    )


def main(pdf_path):
    # Create cache filename based on PDF path
    cache_filename = (
        f"cache/resumecache_{os.path.basename(pdf_path).replace('.pdf', '')}.json"
    )
    github_cache_filename = (
        f"cache/githubcache_{os.path.basename(pdf_path).replace('.pdf', '')}.json"
    )

    resume_data = None
    cache_loaded = False

    # Check if cache exists and we're in development mode
    if DEVELOPMENT_MODE and os.path.exists(cache_filename):
        print(f"Loading cached data from {cache_filename}")
        try:
            cached_data = json.loads(Path(cache_filename).read_text(encoding="utf-8"))
            loaded_resume = JSONResume(**cached_data)
            if not is_valid_resume_data(loaded_resume):
                raise ValueError("Cached resume data contains no core content")
            resume_data = loaded_resume
            cache_loaded = True
        except Exception as e:
            print(f"⚠️ Warning: Invalid cache file {cache_filename}: {e}")
            print("Ignoring cache and reprocessing PDF...")
            try:
                os.remove(cache_filename)
            except Exception as delete_err:
                print(
                    f"Failed to delete invalid cache file {cache_filename}: {delete_err}"
                )

    if not cache_loaded:
        logger.debug(
            f"Extracting data from PDF"
            + (" and caching to " + cache_filename if DEVELOPMENT_MODE else "")
        )
        pdf_handler = PDFHandler()
        resume_data = pdf_handler.extract_json_from_pdf(pdf_path)

        if resume_data == None:
            return None

        if DEVELOPMENT_MODE:
            if is_valid_resume_data(resume_data):
                os.makedirs(os.path.dirname(cache_filename), exist_ok=True)
                Path(cache_filename).write_text(
                    json.dumps(resume_data.model_dump(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            else:
                logger.warning(
                    "Newly extracted resume data is empty/invalid. Skipping cache write."
                )

    # Check if cache exists and we're in development mode
    github_data = {}
    github_cache_loaded = False
    if DEVELOPMENT_MODE and os.path.exists(github_cache_filename):
        print(f"Loading cached data from {github_cache_filename}")
        try:
            loaded_github = json.loads(
                Path(github_cache_filename).read_text(encoding="utf-8")
            )
            if (
                not isinstance(loaded_github, dict)
                or not loaded_github
                or "profile" not in loaded_github
            ):
                raise ValueError("Cached GitHub data is invalid or empty")
            github_data = loaded_github
            github_cache_loaded = True
        except Exception as e:
            print(f"⚠️ Warning: Invalid GitHub cache file {github_cache_filename}: {e}")
            print("Ignoring GitHub cache and refetching...")
            try:
                os.remove(github_cache_filename)
            except Exception as delete_err:
                print(
                    f"Failed to delete invalid GitHub cache file {github_cache_filename}: {delete_err}"
                )

    if not github_cache_loaded:
        # Add validation to handle None values
        profiles = []
        if resume_data and hasattr(resume_data, "basics") and resume_data.basics:
            profiles = resume_data.basics.profiles or []
        github_profile = find_profile(profiles, "Github")

        if github_profile:
            print(
                f"Fetching GitHub data"
                + (
                    " and caching to " + github_cache_filename
                    if DEVELOPMENT_MODE
                    else ""
                )
            )
            github_data = fetch_and_display_github_info(github_profile.url)

            if (
                DEVELOPMENT_MODE
                and github_data
                and isinstance(github_data, dict)
                and "profile" in github_data
            ):
                os.makedirs(os.path.dirname(github_cache_filename), exist_ok=True)
                Path(github_cache_filename).write_text(
                    json.dumps(github_data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

    score = _evaluate_resume(resume_data, github_data)

    # Get candidate name for display
    candidate_name = os.path.basename(pdf_path).replace(".pdf", "")
    if (
        resume_data
        and hasattr(resume_data, "basics")
        and resume_data.basics
        and resume_data.basics.name
    ):
        candidate_name = resume_data.basics.name

    # Print evaluation results in readable format
    print_evaluation_results(score, candidate_name)

    # Always write CSV output
    csv_row = transform_evaluation_response(
        file_name=os.path.basename(pdf_path),
        evaluation=score,
        resume_data=resume_data,
        github_data=github_data,
    )

    csv_path = "resume_evaluations.csv"
    file_exists = os.path.exists(csv_path)

    with open(csv_path, "a", newline="", encoding="utf-8") as csvfile:
        fieldnames = list(csv_row.keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(csv_row)

    print(f"📄 Results appended to {csv_path}")

    return score


def main_batch(folder_path: str):
    """Process all PDF files found in a folder."""
    pdf_files = sorted(
        p for p in Path(folder_path).iterdir()
        if p.suffix.lower() == ".pdf" and p.is_file()
    )

    if not pdf_files:
        print(f"❌ No PDF files found in: {folder_path}")
        return

    print(f"📂 Found {len(pdf_files)} PDF(s) in {folder_path}")
    print("=" * 80)

    results = []
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")
        print("-" * 60)
        try:
            result = main(str(pdf_path))
            results.append({"file": pdf_path.name, "result": result})
        except Exception as e:
            logger.error(f"❌ Failed to process {pdf_path.name}: {e}")
            results.append({"file": pdf_path.name, "result": None})

    # Summary
    succeeded = sum(1 for r in results if r["result"] is not None)
    print("\n" + "=" * 80)
    print(f"✅ Batch complete: {succeeded}/{len(pdf_files)} processed successfully")
    print(f"📄 All results written to resume_evaluations.csv")

    return results


def main_assignment(resumes_path: str, projects_path: str):
    """Orchestrate parsing, matching, and balanced project assignment."""
    logger.info("🚀 Starting Candidate-Project Assignment Pipeline")

    # 1. Resolve Resume PDFs
    resumes_dir = Path(resumes_path)
    if resumes_dir.is_file():
        resume_files = [resumes_dir]
    elif resumes_dir.is_dir():
        resume_files = sorted(
            p for p in resumes_dir.iterdir()
            if p.suffix.lower() == ".pdf" and p.is_file()
        )
    else:
        print(f"❌ Resumes path not found: {resumes_path}")
        return

    if not resume_files:
        print(f"❌ No resume PDF files found in: {resumes_path}")
        return

    # 2. Resolve Project PDFs
    projects_dir = Path(projects_path)
    if projects_dir.is_file():
        project_files = [projects_dir]
    elif projects_dir.is_dir():
        project_files = sorted(
            p for p in projects_dir.iterdir()
            if p.suffix.lower() == ".pdf" and p.is_file()
        )
    else:
        print(f"❌ Projects path not found: {projects_path}")
        return

    if not project_files:
        print(f"❌ No project PDF files found in: {projects_path}")
        return

    print("=" * 80)
    print(f"📂 Found {len(resume_files)} Resume(s) and {len(project_files)} Project(s)")
    print("=" * 80)

    # 3. Parse Resumes & Fetch Github
    pdf_handler = PDFHandler()
    candidates = []
    
    print("\n📝 Step 1: Parsing Candidate Resumes...")
    print("-" * 60)
    for i, pdf_path in enumerate(resume_files, 1):
        print(f"[{i}/{len(resume_files)}] Parsing candidate: {pdf_path.name}")
        # Re-use parsing cache logic from main
        cache_filename = f"cache/resumecache_{pdf_path.stem}.json"
        github_cache_filename = f"cache/githubcache_{pdf_path.stem}.json"
        
        resume_data = None
        if DEVELOPMENT_MODE and os.path.exists(cache_filename):
            try:
                cached_data = json.loads(Path(cache_filename).read_text(encoding="utf-8"))
                resume_data = JSONResume(**cached_data)
            except Exception:
                pass
                
        if not resume_data:
            resume_data = pdf_handler.extract_json_from_pdf(str(pdf_path))
            if resume_data and DEVELOPMENT_MODE:
                os.makedirs("cache", exist_ok=True)
                Path(cache_filename).write_text(
                    json.dumps(resume_data.model_dump(), indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                
        if not resume_data:
            logger.warning(f"Failed to parse resume: {pdf_path.name}")
            continue

        # Fetch Github
        github_data = {}
        github_cache_loaded = False
        if DEVELOPMENT_MODE and os.path.exists(github_cache_filename):
            try:
                github_data = json.loads(Path(github_cache_filename).read_text(encoding="utf-8"))
                github_cache_loaded = True
            except Exception:
                pass
                
        if not github_cache_loaded:
            profiles = resume_data.basics.profiles or [] if resume_data.basics else []
            github_profile = find_profile(profiles, "Github")
            if github_profile:
                github_data = fetch_and_display_github_info(github_profile.url)
                if DEVELOPMENT_MODE and github_data:
                    os.makedirs("cache", exist_ok=True)
                    Path(github_cache_filename).write_text(
                        json.dumps(github_data, indent=2, ensure_ascii=False),
                        encoding="utf-8"
                    )

        candidate_name = resume_data.basics.name if resume_data.basics and resume_data.basics.name else pdf_path.stem

        # Fetch/Evaluate general resume score for seniority balancing (leverage #2)
        eval_cache_filename = f"cache/evalcache_{pdf_path.stem}.json"
        score_data = None
        if DEVELOPMENT_MODE and os.path.exists(eval_cache_filename):
            try:
                cached_eval = json.loads(Path(eval_cache_filename).read_text(encoding="utf-8"))
                score_data = EvaluationData(**cached_eval)
            except Exception:
                pass

        if not score_data:
            print(f"   Evaluating general resume quality for {candidate_name}...")
            try:
                score_data = _evaluate_resume(resume_data, github_data)
                if score_data and DEVELOPMENT_MODE:
                    os.makedirs("cache", exist_ok=True)
                    Path(eval_cache_filename).write_text(
                        json.dumps(score_data.model_dump(), indent=2, ensure_ascii=False),
                        encoding="utf-8"
                    )
            except Exception as e:
                logger.warning(f"Failed to evaluate general resume quality for {candidate_name}: {e}")

        # Compute overall quality score out of 120
        final_quality_score = 50.0
        if score_data:
            total_score = 0.0
            if hasattr(score_data, "scores") and score_data.scores:
                for category_name, category_data in score_data.scores.model_dump().items():
                    category_score = min(category_data["score"], category_data["max"])
                    total_score += category_score
                if hasattr(score_data, "bonus_points") and score_data.bonus_points:
                    total_score += score_data.bonus_points.total
                if hasattr(score_data, "deductions") and score_data.deductions:
                    total_score -= score_data.deductions.total
            final_quality_score = max(-20.0, min(120.0, total_score))
            print(f"   ✅ General Quality Score: {final_quality_score:.1f}/120.0")

        candidates.append((resume_data, github_data, candidate_name, final_quality_score))

    if not candidates:
        print("❌ No candidates successfully parsed. Exiting.")
        return

    # 4. Parse Projects
    projects = []
    print("\n📝 Step 2: Parsing Project Specs...")
    print("-" * 60)
    for i, pdf_path in enumerate(project_files, 1):
        print(f"[{i}/{len(project_files)}] Parsing project: {pdf_path.name}")
        project_cache_filename = f"cache/projectcache_{pdf_path.stem}.json"
        
        project_data = None
        if DEVELOPMENT_MODE and os.path.exists(project_cache_filename):
            try:
                cached_data = json.loads(Path(project_cache_filename).read_text(encoding="utf-8"))
                project_data = ProjectRequirements(**cached_data)
            except Exception:
                pass
                
        if not project_data:
            project_data = pdf_handler.extract_project_from_pdf(str(pdf_path))
            if project_data and DEVELOPMENT_MODE:
                os.makedirs("cache", exist_ok=True)
                Path(project_cache_filename).write_text(
                    json.dumps(project_data.model_dump(), indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                
        if not project_data:
            logger.warning(f"Failed to parse project spec: {pdf_path.name}")
            continue
            
        projects.append(project_data)

    if not projects:
        print("❌ No projects successfully parsed. Exiting.")
        return

    # 5. Evaluate Matches (Sequential Option A)
    print("\n⚖️  Step 3: Evaluating Candidate-Project Matches (Option A: Evaluate All)...")
    print("-" * 60)
    match_evaluator = MatchEvaluator()
    match_evals = {}
    
    total_calls = len(candidates) * len(projects)
    call_index = 1
    
    for resume_data, github_data, candidate_name, _ in candidates:
        match_evals[candidate_name] = {}
        for project in projects:
            print(f"   [{call_index}/{total_calls}] Matching {candidate_name} with '{project.title}'...")
            fit = match_evaluator.evaluate_match(
                resume_data, github_data, project, candidate_name
            )
            if fit:
                match_evals[candidate_name][project.title] = fit
            call_index += 1

    # 6. Assign Projects using SciPy
    print("\n🎯 Step 4: Solving Balanced Project Assignment...")
    print("-" * 60)
    assignment_engine = AssignmentEngine()
    
    # Strip candidates tuple to match expected input: List[Tuple[JSONResume, str, float]]
    engine_candidates = [(res, name, score) for res, _, name, score in candidates]
    assignments = assignment_engine.assign_projects(engine_candidates, projects, match_evals)

    if not assignments:
        print("❌ Project assignment failed.")
        return

    # 7. Post-process assignments: group by project and designate the lead/anchor based on quality score (at the end)
    project_teams = {p.title: [] for p in projects}
    for assign in assignments:
        project_teams[assign["project_title"]].append(assign)
        
    for proj_title, team in project_teams.items():
        if team:
            # Sort team members by general quality score descending
            team.sort(key=lambda m: m.get("quality_score", 0.0), reverse=True)
            # The highest general score member within this assigned team is designated as anchor
            team[0]["is_anchor"] = True

    # 8. Print and Save Results
    print("\n" + "=" * 80)
    print("📋 FINAL BALANCED PROJECT ASSIGNMENTS")
    print("=" * 80)
        
    for proj_title, team in project_teams.items():
        print(f"\n🚀 PROJECT: {proj_title} ({len(team)} members)")
        print("-" * 60)
        if not team:
            print("   (No members assigned)")
            continue
        for idx, member in enumerate(team, 1):
            role_suffix = " (TEAM ANCHOR/LEAD) 👑" if member.get("is_anchor") else ""
            print(f"  {idx}. {member['candidate_name']}{role_suffix}")
            print(f"     Fit Score: {member['fit_score']:.1f}/100 | General Quality Score: {member.get('quality_score', 0.0):.1f}/120.0")
            print(f"     Reasoning: {member['reasoning']}")
            if member['strengths']:
                print(f"     Strengths: {', '.join(member['strengths'])}")
            if member['gaps']:
                print(f"     Gaps: {', '.join(member['gaps'])}")
            print()

    # Save to CSV
    csv_path = "project_assignments.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["Candidate Name", "Assigned Project", "Fit Score", "General Quality Score", "Is Anchor", "Strengths", "Gaps", "Reasoning"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Flatten team list again for CSV write
        all_final_assignments = []
        for team in project_teams.values():
            all_final_assignments.extend(team)
            
        for assign in all_final_assignments:
            writer.writerow({
                "Candidate Name": assign["candidate_name"],
                "Assigned Project": assign["project_title"],
                "Fit Score": f"{assign['fit_score']:.1f}",
                "General Quality Score": f"{assign.get('quality_score', 0.0):.1f}",
                "Is Anchor": "Yes" if assign.get("is_anchor") else "No",
                "Strengths": "; ".join(assign["strengths"]),
                "Gaps": "; ".join(assign["gaps"]),
                "Reasoning": assign["reasoning"]
            })
            
    print("=" * 80)
    print(f"📄 Results written to {csv_path}")
    print("=" * 80)
    return assignments


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hiring Agent CLI")
    parser.add_argument("--resumes", help="Path to resumes PDF or folder containing resume PDFs")
    parser.add_argument("--projects", help="Path to projects PDF or folder containing project PDFs")
    parser.add_argument("legacy_path", nargs="?", help="Legacy path (single resume PDF or folder of resumes)")
    args = parser.parse_args()

    if args.resumes and args.projects:
        main_assignment(args.resumes, args.projects)
    elif args.legacy_path:
        if os.path.isdir(args.legacy_path):
            main_batch(args.legacy_path)
        else:
            main(args.legacy_path)
    else:
        parser.print_help()
        sys.exit(1)


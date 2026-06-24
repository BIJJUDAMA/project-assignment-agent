"""
Match evaluator: scores the compatibility between a candidate and a project using Ollama.
Supports caching at the candidate-project pair level.
"""

import os
import json
import logging
import re
from pathlib import Path
from typing import Optional

from schemas.resume import JSONResume, ProjectRequirements, ProjectFit
from providers.ollama import OllamaProvider
from utils.llm import extract_json_from_response
from config import DEFAULT_MODEL, MODEL_PARAMETERS, DEVELOPMENT_MODE
from prompts.template_manager import TemplateManager

logger = logging.getLogger(__name__)


class MatchEvaluator:
    def __init__(self, model_name: str = DEFAULT_MODEL, model_params: dict = None):
        self.model_name = model_name
        self.model_params = model_params or MODEL_PARAMETERS.get(
            model_name, {"temperature": 0.1, "top_p": 0.9}
        )
        self.template_manager = TemplateManager()
        self.provider = OllamaProvider()

    def _convert_to_matching_text(self, resume_data: JSONResume, github_data: dict) -> str:
        """
        Serialize ONLY basics, work, skills, projects, and structured GitHub metadata.
        This excludes Education, Volunteer (non-tech), Awards, Certificates, Publications, 
        Languages, Interests, References, and Blog text.
        """
        text_parts = []

        if resume_data.basics:
            basics = resume_data.basics
            text_parts.append("=== BASIC INFORMATION ===")
            text_parts.append(f"Name: {basics.name or 'Not provided'}")
            text_parts.append(f"Email: {basics.email or 'Not provided'}")
            if basics.summary:
                text_parts.append(f"Summary: {basics.summary}")

        if resume_data.work:
            text_parts.append("\n=== WORK EXPERIENCE ===")
            for i, work in enumerate(resume_data.work, 1):
                text_parts.append(f"{i}. {work.position} at {work.name}")
                text_parts.append(f"   Period: {work.startDate} - {work.endDate}")
                if work.summary:
                    text_parts.append(f"   Description: {work.summary}")
                if work.highlights:
                    text_parts.append("   Key Achievements:")
                    for highlight in work.highlights:
                        text_parts.append(f"     • {highlight}")

        if resume_data.skills:
            text_parts.append("\n=== SKILLS ===")
            for skill in resume_data.skills:
                text_parts.append(f"• {skill.name}")
                if skill.keywords:
                    text_parts.append(f"  Keywords: {', '.join(skill.keywords)}")

        if resume_data.projects:
            text_parts.append("\n=== PROJECTS ===")
            for i, project in enumerate(resume_data.projects, 1):
                text_parts.append(f"{i}. {project.name}")
                if project.description:
                    text_parts.append(f"   Description: {project.description}")
                if project.technologies:
                    text_parts.append(f"   Technologies: {', '.join(project.technologies)}")
                if project.highlights:
                    text_parts.append("   Highlights:")
                    for highlight in project.highlights:
                        text_parts.append(f"     • {highlight}")

        if github_data:
            text_parts.append("\n=== GITHUB REPOSITORY METADATA ===")
            if "profile" in github_data:
                profile = github_data["profile"]
                text_parts.append(f"GitHub Bio: {profile.get('bio', 'N/A')}")
                text_parts.append(f"Public Repositories: {profile.get('public_repos', '0')}")
                text_parts.append(f"Followers: {profile.get('followers', '0')}")
            
            if "projects" in github_data:
                projects = github_data["projects"]
                text_parts.append(f"GitHub Projects details:")
                for i, project in enumerate(projects[:15], 1):  # Include more repos for richer skill discovery
                    text_parts.append(f"{i}. {project.get('name', 'N/A')}")
                    if project.get('description'):
                        text_parts.append(f"   Description: {project.get('description')}")
                    if "github_details" in project:
                        details = project["github_details"]
                        text_parts.append(f"   Stars: {details.get('stars', '0')} | Forks: {details.get('forks', '0')}")
                        text_parts.append(f"   Primary Language: {details.get('language', 'N/A')}")
                    text_parts.append("")

        return "\n".join(text_parts)

    def _get_safe_filename(self, text: str) -> str:
        """Convert a string to a safe filename."""
        return re.sub(r"[^a-zA-Z0-9_-]", "_", text).lower()

    def evaluate_match(
        self,
        resume_data: JSONResume,
        github_data: dict,
        project: ProjectRequirements,
        candidate_filename_fallback: str = "candidate",
    ) -> Optional[ProjectFit]:
        """Evaluate match score of a candidate and a project, checking the cache first."""
        candidate_name = (
            resume_data.basics.name
            if resume_data and resume_data.basics and resume_data.basics.name
            else candidate_filename_fallback
        )

        safe_cand_name = self._get_safe_filename(candidate_name)
        safe_proj_title = self._get_safe_filename(project.title)
        cache_filename = f"cache/matchcache_{safe_cand_name}_{safe_proj_title}.json"

        # Check cache if in development mode
        if DEVELOPMENT_MODE and os.path.exists(cache_filename):
            logger.debug(f"Loading cached match data from {cache_filename}")
            try:
                cached_data = json.loads(Path(cache_filename).read_text(encoding="utf-8"))
                return ProjectFit(**cached_data)
            except Exception as e:
                logger.warning(f"Warning: Invalid match cache file {cache_filename}: {e}")
                try:
                    os.remove(cache_filename)
                except Exception:
                    pass

        # Parse & match
        logger.info(f"⚡ Evaluating match: {candidate_name} <-> {project.title}")

        # Construct stripped matching candidate representation
        resume_text = self._convert_to_matching_text(resume_data, github_data)

        prompt = self.template_manager.render_template(
            "project_matching",
            candidate_name=candidate_name,
            resume_text=resume_text,
            project_title=project.title,
            project_domain=project.domain,
            project_required_technologies=", ".join(project.required_technologies),
            project_preferred_skills=", ".join(project.preferred_skills),
            project_description=project.description,
        )

        if not prompt:
            logger.error("❌ Failed to render project_matching template")
            return None

        try:
            chat_params = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": "You are a highly precise technical matching system."},
                    {"role": "user", "content": prompt},
                ],
                "options": {
                    "stream": False,
                    "temperature": self.model_params.get("temperature", 0.1),
                    "top_p": self.model_params.get("top_p", 0.9),
                },
            }

            response = self.provider.chat(
                **chat_params, format=ProjectFit.model_json_schema()
            )
            response_text = response["message"]["content"]
            response_text = extract_json_from_response(response_text)

            json_start = response_text.find("{")
            json_end = response_text.rfind("}")
            if json_start != -1 and json_end != -1:
                response_text = response_text[json_start : json_end + 1]

            parsed_data = json.loads(response_text)
            match_data = ProjectFit(**parsed_data)

            # Write to cache
            if DEVELOPMENT_MODE:
                os.makedirs(os.path.dirname(cache_filename), exist_ok=True)
                Path(cache_filename).write_text(
                    json.dumps(match_data.model_dump(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

            return match_data
        except Exception as e:
            logger.error(f"❌ Error during match evaluation for {candidate_name} and {project.title}: {e}")
            return None

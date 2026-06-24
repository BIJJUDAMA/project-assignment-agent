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

from hiring_agent.schemas.resume import JSONResume, ProjectRequirements, ProjectFit
from hiring_agent.providers.ollama import OllamaProvider
from hiring_agent.utils.llm import extract_json_from_response
from hiring_agent.config import DEFAULT_MODEL, MODEL_PARAMETERS, DEVELOPMENT_MODE
from hiring_agent.prompts.template_manager import TemplateManager
from hiring_agent.utils.transform import (
    convert_json_resume_to_text,
    convert_github_data_to_text,
)

logger = logging.getLogger(__name__)


class MatchEvaluator:
    def __init__(self, model_name: str = DEFAULT_MODEL, model_params: dict = None):
        self.model_name = model_name
        self.model_params = model_params or MODEL_PARAMETERS.get(
            model_name, {"temperature": 0.1, "top_p": 0.9}
        )
        self.template_manager = TemplateManager()
        self.provider = OllamaProvider()

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

        # Construct candidate representation
        resume_text = convert_json_resume_to_text(resume_data)
        if github_data:
            github_text = convert_github_data_to_text(github_data)
            resume_text += "\n" + github_text

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

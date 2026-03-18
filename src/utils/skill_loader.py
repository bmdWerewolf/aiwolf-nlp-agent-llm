"""Module for loading role and turn skills from external files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from logging import Logger


class SkillLoader:
    """Load and cache skill texts for system and per-turn injection."""

    _PROJECT_ROOT = Path(__file__).resolve().parents[2]
    _DEFAULT_ROLE_BASE_DIR = Path("./config/skills/ja")
    _DEFAULT_TURN_BASE_DIR = Path("./config/skills/ja/psychology")

    def __init__(self, config: dict[str, Any], logger: Logger) -> None:
        """Initialize the skill loader.

        Args:
            config (dict[str, Any]): Agent configuration dictionary.
            logger (Logger): Logger instance for warnings/errors.
        """
        self._logger = logger
        self._skills_config = self._to_config_dict(config.get("skills"))
        self._turn_skills_config = self._to_config_dict(config.get("turn_skills"))
        self._role_cache: dict[str, str] = {}
        self._turn_cache: dict[str, str] = {}

    def load(self, role_value: str) -> str:
        """Load role skill text for system prompt injection.

        Args:
            role_value (str): Role string, such as ``SEER``.

        Returns:
            str: Skill text. Empty when disabled or unavailable.
        """
        if role_value in self._role_cache:
            return self._role_cache[role_value]
        if not self._is_role_skill_enabled():
            self._role_cache[role_value] = ""
            return ""

        role_file = self._get_role_file(role_value)
        if role_file is None:
            self._logger.warning("Skill file mapping is missing for role: %s", role_value)
            self._role_cache[role_value] = ""
            return ""

        skill_text = self._read_text_file(
            self._resolve_role_skill_path(role_file),
            f"role {role_value}",
        )
        self._role_cache[role_value] = skill_text
        return skill_text

    def should_use_builtin_role_strategy(self) -> bool:
        """Return whether built-in role strategy should be included."""
        if not self._is_role_skill_enabled():
            return True
        return bool(self._skills_config.get("fallback_to_builtin_strategy", True))

    def is_turn_skill_enabled(self) -> bool:
        """Return whether per-turn dynamic skill injection is enabled."""
        return bool(self._turn_skills_config.get("enabled", False))

    def should_apply_turn_skill(self, request_name: str) -> bool:
        """Return whether turn skill selection is enabled for a request.

        Args:
            request_name (str): Request name, such as ``TALK``.

        Returns:
            bool: True when turn skills should be considered.
        """
        if not self.is_turn_skill_enabled():
            return False
        requests_raw = self._turn_skills_config.get("requests", ["TALK"])
        if not isinstance(requests_raw, list):
            requests_raw = ["TALK"]
        request_items = cast("list[object]", requests_raw)
        request_set = {str(req).upper() for req in request_items}
        return request_name.upper() in request_set

    def get_turn_skill_summaries(self) -> dict[str, str]:
        """Return available turn skill IDs with short summaries."""
        files = self._get_turn_skill_files()
        summaries_raw = self._to_config_dict(self._turn_skills_config.get("summaries"))
        summaries: dict[str, str] = {}
        for skill_id in files:
            summary_obj: object = summaries_raw.get(skill_id, skill_id.replace("_", " "))
            summaries[skill_id] = str(summary_obj)
        return summaries

    def load_turn_skill(self, skill_id: str) -> str:
        """Load turn skill text for current-turn prompt injection.

        Args:
            skill_id (str): Turn skill identifier.

        Returns:
            str: Skill text. Empty when unavailable.
        """
        if skill_id in self._turn_cache:
            return self._turn_cache[skill_id]
        if not self.is_turn_skill_enabled():
            self._turn_cache[skill_id] = ""
            return ""

        skill_files = self._get_turn_skill_files()
        turn_file = skill_files.get(skill_id)
        if turn_file is None:
            self._logger.warning("Turn skill file mapping is missing: %s", skill_id)
            self._turn_cache[skill_id] = ""
            return ""

        skill_text = self._read_text_file(
            self._resolve_turn_skill_path(turn_file),
            f"turn skill {skill_id}",
        )
        max_chars = self.get_turn_skill_max_chars()
        if max_chars > 0 and len(skill_text) > max_chars:
            skill_text = skill_text[:max_chars].rstrip()
        self._turn_cache[skill_id] = skill_text
        return skill_text

    def get_turn_skill_max_chars(self) -> int:
        """Return max character length for turn skill injection."""
        max_chars_raw = self._turn_skills_config.get("max_chars", 1200)
        try:
            max_chars = int(max_chars_raw)
        except (TypeError, ValueError):
            return 1200
        if max_chars <= 0:
            return 1200
        return max_chars

    @staticmethod
    def _to_config_dict(raw_config: object) -> dict[str, Any]:
        if not isinstance(raw_config, dict):
            return {}
        return cast("dict[str, Any]", raw_config)

    def _is_role_skill_enabled(self) -> bool:
        return bool(self._skills_config.get("enabled", False))

    def _get_role_file(self, role_value: str) -> str | None:
        role_files_raw = self._skills_config.get("files")
        role_files = self._to_config_dict(role_files_raw)
        if not role_files:
            return None
        role_file_obj: object = role_files.get(role_value)
        if role_file_obj is None:
            return None
        return str(role_file_obj)

    def _get_turn_skill_files(self) -> dict[str, str]:
        files_raw = self._turn_skills_config.get("files")
        files_dict = self._to_config_dict(files_raw)
        if not files_dict:
            return {}
        return {str(skill_id): str(file_name) for skill_id, file_name in files_dict.items()}

    def _resolve_role_skill_path(self, role_file: str) -> Path:
        role_file_path = Path(role_file)
        if role_file_path.is_absolute():
            return role_file_path
        return self._resolve_base_dir(self._skills_config, self._DEFAULT_ROLE_BASE_DIR).joinpath(role_file_path)

    def _resolve_turn_skill_path(self, turn_file: str) -> Path:
        turn_file_path = Path(turn_file)
        if turn_file_path.is_absolute():
            return turn_file_path
        return self._resolve_base_dir(self._turn_skills_config, self._DEFAULT_TURN_BASE_DIR).joinpath(turn_file_path)

    def _resolve_base_dir(self, config_dict: dict[str, Any], default_path: Path) -> Path:
        base_dir_obj: object = config_dict.get("base_dir", str(default_path))
        base_dir_path = Path(str(base_dir_obj))
        if base_dir_path.is_absolute():
            return base_dir_path
        return self._PROJECT_ROOT.joinpath(base_dir_path)

    def _read_text_file(self, file_path: Path, log_label: str) -> str:
        try:
            skill_text = file_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            self._logger.warning("Skill file not found for %s: %s", log_label, file_path)
            return ""
        except OSError:
            self._logger.exception("Failed to read skill file for %s: %s", log_label, file_path)
            return ""
        if not skill_text:
            self._logger.warning("Skill file is empty for %s: %s", log_label, file_path)
        return skill_text

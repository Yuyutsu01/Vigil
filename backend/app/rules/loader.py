"""
RuleLoader: Parses YAML front-matter from skills/*.md files.
Rules are NOT hardcoded Python strings — they live in markdown skill files.
See Implementation Plan [H1].
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

def _resolve_skills_dir() -> Path:
    candidates = [
        Path(__file__).parents[3] / "skills",
        Path("/skills"),
        Path("/app/skills"),
        Path.cwd() / "skills",
        Path(__file__).parents[2] / "skills",
    ]
    for c in candidates:
        if c.exists() and any(c.glob("*.md")):
            return c
    return candidates[0]


# Path to the skills directory (relative to project root)
SKILLS_DIR = _resolve_skills_dir()

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


@dataclass
class SkillRule:
    """Parsed skill rule from a skills/*.md file."""
    rule_id: str
    category: str
    severity: str
    languages: List[str]
    pattern_type: str  # "ast_node" | "token_regex"
    detection_notes: str
    remediation_template: str
    references: List[str] = field(default_factory=list)
    # Raw source for audit
    source_file: Optional[str] = None


def load_skill(path: Path) -> Optional[SkillRule]:
    """Parse YAML front-matter from a single skill markdown file."""
    try:
        content = path.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(content)
        if not m:
            logger.warning("No YAML front-matter found in %s", path)
            return None

        meta = yaml.safe_load(m.group(1))
        if not isinstance(meta, dict):
            logger.warning("YAML front-matter is not a dict in %s", path)
            return None

        required = ["rule_id", "category", "severity", "languages", "pattern_type"]
        for k in required:
            if k not in meta:
                logger.warning("Missing field '%s' in %s front-matter", k, path)
                return None

        return SkillRule(
            rule_id=meta["rule_id"],
            category=meta["category"],
            severity=meta["severity"],
            languages=[lang.lower() for lang in meta.get("languages", [])],
            pattern_type=meta["pattern_type"],
            detection_notes=meta.get("detection_notes", ""),
            remediation_template=meta.get("remediation_template", ""),
            references=meta.get("references", []),
            source_file=str(path),
        )
    except Exception as e:
        logger.error("Failed to load skill from %s: %s", path, e)
        return None


def load_all_skills(skills_dir: Path = SKILLS_DIR) -> Dict[str, SkillRule]:
    """
    Load all skill markdown files from the skills directory.
    Returns a dict keyed by rule_id.
    """
    rules: Dict[str, SkillRule] = {}
    if not skills_dir.exists():
        logger.warning("Skills directory not found: %s", skills_dir)
        return rules

    for md_file in sorted(skills_dir.glob("*.md")):
        if md_file.name.upper().startswith("FUTURE"):
            continue  # skip non-rule docs
        rule = load_skill(md_file)
        if rule is not None:
            rules[rule.rule_id] = rule
            logger.debug("Loaded skill: %s from %s", rule.rule_id, md_file.name)

    logger.info("Loaded %d skill rules from %s", len(rules), skills_dir)
    return rules


# Module-level cached rules (loaded once at import time)
_cached_rules: Optional[Dict[str, SkillRule]] = None


def get_rules() -> Dict[str, SkillRule]:
    """Return the globally cached rule set (load on first call)."""
    global _cached_rules
    if _cached_rules is None:
        _cached_rules = load_all_skills()
    return _cached_rules

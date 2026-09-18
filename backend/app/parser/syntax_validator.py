"""
Syntax validator — extracts syntax errors before deeper analysis.
Uses Python ast module for Python, tree-sitter for JS/TS.

ZERO CODE EXECUTION: Only parse tree construction. No eval/exec/subprocess.
"""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SyntaxError_:
    """Parsed syntax error with location."""
    message: str
    line: Optional[int] = None
    col: Optional[int] = None


def validate_python(source: str) -> List[SyntaxError_]:
    """
    Parse Python source using the stdlib `ast` module.
    Returns a list of syntax errors (empty = no errors).
    NEVER executes the code — only builds the AST.
    """
    try:
        ast.parse(source, mode="exec")
        return []
    except SyntaxError as e:
        return [
            SyntaxError_(
                message=str(e.msg),
                line=e.lineno,
                col=e.offset,
            )
        ]
    except Exception as e:
        return [SyntaxError_(message=f"Parse error: {e}")]


def validate_javascript(source: str) -> List[SyntaxError_]:
    """
    Validate JavaScript/TypeScript using tree-sitter.
    Falls back to a basic brace-balance check if tree-sitter is unavailable.
    NEVER executes the code.
    """
    try:
        from tree_sitter import Language, Parser  # type: ignore
        import tree_sitter_javascript  # type: ignore

        PY_LANGUAGE = Language(tree_sitter_javascript.language())
        parser = Parser(PY_LANGUAGE)
        tree = parser.parse(source.encode("utf-8"))

        errors: List[SyntaxError_] = []
        _collect_errors(tree.root_node, errors)
        return errors
    except ImportError:
        # tree-sitter not available — use fallback heuristic
        logger.warning("tree-sitter not available; using fallback JS syntax check")
        return _fallback_brace_check(source)


def validate_typescript(source: str) -> List[SyntaxError_]:
    """Validate TypeScript using tree-sitter-typescript if available."""
    try:
        from tree_sitter import Language, Parser  # type: ignore
        import tree_sitter_typescript  # type: ignore

        PY_LANGUAGE = Language(tree_sitter_typescript.language_typescript())
        parser = Parser(PY_LANGUAGE)
        tree = parser.parse(source.encode("utf-8"))

        errors: List[SyntaxError_] = []
        _collect_errors(tree.root_node, errors)
        return errors
    except ImportError:
        logger.warning("tree-sitter-typescript not available; using JS fallback")
        return validate_javascript(source)


def _collect_errors(node, errors: List[SyntaxError_]) -> None:
    """Recursively collect ERROR nodes from a tree-sitter parse tree."""
    if node.type == "ERROR" or node.is_missing:
        start = node.start_point
        errors.append(
            SyntaxError_(
                message=f"Syntax error at ({start[0] + 1}, {start[1] + 1})",
                line=start[0] + 1,
                col=start[1] + 1,
            )
        )
    for child in node.children:
        _collect_errors(child, errors)


def _fallback_brace_check(source: str) -> List[SyntaxError_]:
    """Minimal brace-balance check used when tree-sitter is unavailable."""
    depth = 0
    for line_num, line in enumerate(source.splitlines(), 1):
        for col, ch in enumerate(line, 1):
            if ch in "({[":
                depth += 1
            elif ch in ")}]":
                depth -= 1
                if depth < 0:
                    return [SyntaxError_(
                        message="Unexpected closing bracket",
                        line=line_num,
                        col=col,
                    )]
    if depth != 0:
        return [SyntaxError_(message="Unclosed bracket or brace")]
    return []


def validate_syntax(source: str, language: str) -> List[SyntaxError_]:
    """Dispatcher: validate syntax for the given language."""
    lang = language.lower()
    if lang == "python":
        return validate_python(source)
    elif lang in ("javascript", "js"):
        return validate_javascript(source)
    elif lang in ("typescript", "ts"):
        return validate_typescript(source)
    else:
        return []

"""
Tree-sitter AST engine.
Builds parse trees for Python, JavaScript, and TypeScript.
ZERO CODE EXECUTION — only tree construction.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ASTNode:
    """Simplified, language-agnostic AST node representation."""
    node_type: str
    text: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    # Syntactic path for fingerprinting, e.g. "Module/FunctionDef[name=foo]/Call[func=eval]"
    ast_path: str = ""
    children: List["ASTNode"] = field(default_factory=list)
    # Raw tree-sitter node reference (not serialized)
    _raw: Any = field(default=None, repr=False, compare=False)


def _build_path(node: Any, parent_path: str = "") -> str:
    """Build a stable AST path string for a tree-sitter node."""
    node_type = node.type
    path = f"{parent_path}/{node_type}" if parent_path else node_type
    return path


def _ts_node_to_ast(node: Any, parent_path: str = "") -> ASTNode:
    """Convert a tree-sitter node to our ASTNode format."""
    path = _build_path(node, parent_path)
    text = node.text.decode("utf-8", errors="replace") if node.text else ""
    ast_node = ASTNode(
        node_type=node.type,
        text=text[:500],  # truncate for safety
        start_line=node.start_point[0] + 1,
        start_col=node.start_point[1] + 1,
        end_line=node.end_point[0] + 1,
        end_col=node.end_point[1] + 1,
        ast_path=path,
        _raw=node,
    )
    for child in node.children:
        ast_node.children.append(_ts_node_to_ast(child, path))
    return ast_node


def parse_with_treesitter(source: str, language: str) -> Optional[ASTNode]:
    """
    Parse source code using tree-sitter.
    Returns root ASTNode or None if tree-sitter is unavailable.
    NEVER executes the submitted code.
    """
    try:
        from tree_sitter import Language, Parser  # type: ignore

        if language == "python":
            import tree_sitter_python  # type: ignore
            lang_obj = Language(tree_sitter_python.language())
        elif language == "javascript":
            import tree_sitter_javascript  # type: ignore
            lang_obj = Language(tree_sitter_javascript.language())
        elif language == "typescript":
            import tree_sitter_typescript  # type: ignore
            lang_obj = Language(tree_sitter_typescript.language_typescript())
        else:
            return None

        parser = Parser(lang_obj)
        tree = parser.parse(source.encode("utf-8"))
        return _ts_node_to_ast(tree.root_node)

    except ImportError:
        logger.warning(
            "tree-sitter not installed; falling back to Python ast for Python, "
            "or token-based analysis for JS/TS."
        )
        return None
    except Exception as e:
        logger.warning("tree-sitter parse failed: %s", e)
        return None


def walk_ast(root: ASTNode, target_types: Optional[set] = None):
    """Generator: depth-first walk of ASTNode tree, optionally filtered by node type."""
    stack = [root]
    while stack:
        node = stack.pop()
        if target_types is None or node.node_type in target_types:
            yield node
        stack.extend(reversed(node.children))

"""Input validation and subprocess security utilities for Web App Factory.

Provides hardened validation functions that protect against:
  - Shell injection via slug/project-name fields (MCPI-04)
  - Path traversal via project_dir parameter (MCPI-04)
  - Null byte injection and over-length strings in any user input

All public functions raise ``ValueError`` with a descriptive message on
invalid input.  They return the (possibly normalized) value on success.

Public API:
    validate_slug(value, *, field_name="name") -> str
    validate_idea(idea) -> str
    validate_project_dir(path, *, output_base=None) -> Path
    safe_shell_arg(value) -> str
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Optional

# ── Slug validation ───────────────────────────────────────────────────────────
# A valid slug:
#   - Starts and ends with alphanumeric
#   - Contains only a-z, A-Z, 0-9, hyphen, underscore in the middle
#   - Maximum 50 characters
#   - Minimum 1 character
# This pattern allows a single alphanumeric character OR a 2-50 char slug.
_SLUG_PATTERN = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9_-]{0,48}[a-zA-Z0-9])?$"
)

# Shell metacharacters that must never appear in a slug
_SHELL_META_CHARS = frozenset(";|&`$><()!*?{}\\\"'\n\r\t")

# Maximum lengths
_MAX_SLUG_LEN = 50
_MAX_IDEA_LEN = 500


def validate_slug(value: str, field_name: str = "name") -> str:
    """Validate a slug value against injection and format rules.

    A slug is suitable for use as a project or app name, npm package name,
    or directory component.

    Args:
        value:      The slug string to validate.
        field_name: Name of the field for error messages.

    Returns:
        The original value, unchanged, on success.

    Raises:
        ValueError: If the slug is empty, too long, contains null bytes,
                    contains shell metacharacters, or doesn't match the
                    allowed character set.
    """
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a string, got {type(value).__name__}")

    # Null bytes are always rejected — they can truncate paths on some systems
    if "\x00" in value:
        raise ValueError(f"{field_name}: null bytes are not allowed")

    if not value:
        raise ValueError(f"{field_name}: must not be empty")

    if len(value) > _MAX_SLUG_LEN:
        raise ValueError(
            f"{field_name}: must be at most {_MAX_SLUG_LEN} characters, got {len(value)}"
        )

    # Reject any shell metacharacter (defense-in-depth on top of regex)
    bad_chars = _SHELL_META_CHARS.intersection(value)
    if bad_chars:
        raise ValueError(
            f"{field_name}: contains invalid characters {sorted(bad_chars)!r}. "
            "Only a-z, A-Z, 0-9, hyphen, and underscore are allowed."
        )

    # Reject path traversal patterns (dots followed by slash)
    if ".." in value or "/" in value or "\\" in value:
        raise ValueError(
            f"{field_name}: path traversal characters are not allowed"
        )

    # Final: regex check for full format compliance
    if not _SLUG_PATTERN.match(value):
        raise ValueError(
            f"{field_name}: '{value}' is not a valid slug. "
            "Must start and end with alphanumeric; may contain hyphens/underscores."
        )

    return value


def validate_idea(idea: str) -> str:
    """Validate a free-form idea string.

    Accepts virtually any text, but rejects:
      - Empty / whitespace-only strings
      - Strings longer than 500 characters
      - Null bytes

    Args:
        idea: The app idea description.

    Returns:
        The stripped idea string on success.

    Raises:
        ValueError: If the idea fails validation.
    """
    if not isinstance(idea, str):
        raise ValueError(f"idea: must be a string, got {type(idea).__name__}")

    # Null bytes rejected
    if "\x00" in idea:
        raise ValueError("idea: null bytes are not allowed")

    stripped = idea.strip()

    if not stripped:
        raise ValueError("idea: must not be empty or whitespace-only")

    if len(stripped) > _MAX_IDEA_LEN:
        raise ValueError(
            f"idea: must be at most {_MAX_IDEA_LEN} characters, "
            f"got {len(stripped)} after stripping whitespace"
        )

    return stripped


def validate_project_dir(
    path: str,
    output_base: Optional[Path] = None,
) -> Path:
    """Validate a project directory path against path traversal.

    The path must resolve to be under ``output_base`` (defaults to
    ``<cwd>/output``).  Absolute paths outside the base and paths
    containing ``..`` components are rejected.

    Args:
        path:        The project directory path (may be relative or absolute).
        output_base: The directory that project dirs must reside under.
                     Defaults to ``Path.cwd() / "output"``.

    Returns:
        The resolved absolute ``Path`` on success.

    Raises:
        ValueError: If the path resolves outside ``output_base``.
    """
    if output_base is None:
        output_base = Path.cwd() / "output"

    base_resolved = output_base.resolve()
    candidate = Path(path)

    # If path is absolute and outside base, reject it upfront
    # (relative_to check below handles this too, but be explicit)
    if candidate.is_absolute():
        candidate_resolved = candidate.resolve()
    else:
        # Resolve relative to the base's parent so that "output/MyApp" works
        candidate_resolved = (output_base.parent / candidate).resolve()

    try:
        candidate_resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError(
            f"project_dir '{path}' resolves to '{candidate_resolved}', which is "
            f"outside the allowed base directory '{base_resolved}'. "
            "Path traversal is not permitted."
        )

    return candidate_resolved


def safe_shell_arg(value: str) -> str:
    """Return a shell-safe quoted version of *value*.

    Wraps ``shlex.quote()`` — this is the canonical Python way to escape
    a string for inclusion in a shell command.

    Note: Prefer ``subprocess.run([...])`` with a list of arguments over
    building shell command strings.  Use this function only when a shell
    string is unavoidable.

    Args:
        value: The string to quote.

    Returns:
        A shell-safe quoted string (e.g. ``'hello world'``).
    """
    return shlex.quote(value)

#!/usr/bin/env python3
"""Shared OKF bundle parsing helpers for project tools.

This module is a project-level utility. It intentionally keeps OKF protocol
rules separate from convenience parsing used by validator/visualizer scripts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None

RESERVED_NAMES = {"index.md", "log.md"}


@dataclass
class MarkdownLink:
    label: str
    target_raw: str
    target_base: str
    fragment: str | None
    is_external: bool
    is_internal_markdown: bool
    is_bundle_absolute: bool
    target_path: Path | None = None
    target_id: str | None = None
    exists: bool = False
    outside_bundle: bool = False


@dataclass
class Citation:
    number: str | None
    text: str
    raw: str


@dataclass
class OKFDocumentData:
    path: Path
    root: Path
    rel_path: str
    id: str | None
    is_reserved: bool
    reserved_name: str | None
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    parse_error: str | None = None
    used_fallback_parser: bool = False
    links: list[MarkdownLink] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)

    @property
    def type(self) -> str:
        return str(self.frontmatter.get("type") or "")

    @property
    def title(self) -> str:
        return str(self.frontmatter.get("title") or "")

    @property
    def description(self) -> str:
        return str(self.frontmatter.get("description") or "")

    @property
    def timestamp(self) -> Any:
        return self.frontmatter.get("timestamp")

    @property
    def tags(self) -> Any:
        return self.frontmatter.get("tags")

    @property
    def resource(self) -> Any:
        return self.frontmatter.get("resource")


@dataclass
class LogDateGroup:
    date: str
    entries: list[str]


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Split a Markdown file into YAML frontmatter and body.

    The frontmatter must start at the beginning of the file and be delimited by
    standalone-ish `---` lines. Returns `(None, text)` when absent or unclosed.
    """
    if not text.startswith("---"):
        return None, text
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)(.*)$", text, re.S)
    if not match:
        return None, text
    return match.group(1), match.group(2)


def fallback_parse_frontmatter(frontmatter: str) -> dict[str, Any]:
    """Parse a small top-level YAML mapping subset when PyYAML is unavailable."""
    data: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in frontmatter.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if current_list_key and line.startswith("  - "):
            data.setdefault(current_list_key, []).append(line[4:].strip().strip('"\''))
            continue
        current_list_key = None
        if line.startswith((" ", "\t")):
            continue
        if ":" not in line:
            raise ValueError(f"cannot parse frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            data[key] = True
            current_list_key = key
        else:
            data[key] = value.strip('"\'')
    return data


def parse_frontmatter(frontmatter: str) -> tuple[dict[str, Any], bool]:
    """Parse YAML frontmatter and return `(mapping, used_fallback_parser)`."""
    if yaml is not None:
        parsed = yaml.safe_load(frontmatter)
        if parsed is None:
            return {}, False
        if not isinstance(parsed, dict):
            raise ValueError("frontmatter must parse to a YAML mapping")
        return parsed, False
    return fallback_parse_frontmatter(frontmatter), True


def rel_path(path: Path, root: Path) -> str:
    return "/" + path.relative_to(root).as_posix()


def concept_id_for_path(path: Path, root: Path) -> str:
    """Return the official visualizer-style concept id: relative path without `.md`."""
    return path.relative_to(root).with_suffix("").as_posix()


def is_external_target(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:")) or "://" in target


def extract_markdown_links(text: str) -> list[tuple[str, str]]:
    """Extract normal inline Markdown links.

    This intentionally does not attempt to be a complete Markdown parser, but it
    covers the link form used in OKF concept/index files.
    """
    return re.findall(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", text)


def resolve_internal_link(current_file: Path, root: Path, target: str) -> MarkdownLink | None:
    label = ""
    target_base, fragment = (target.split("#", 1) + [None])[:2] if "#" in target else (target, None)
    is_external = is_external_target(target_base)
    is_internal_md = (not is_external) and target_base.endswith(".md")
    is_bundle_absolute = target_base.startswith("/")
    link = MarkdownLink(
        label=label,
        target_raw=target,
        target_base=target_base,
        fragment=fragment,
        is_external=is_external,
        is_internal_markdown=is_internal_md,
        is_bundle_absolute=is_bundle_absolute,
    )
    if not is_internal_md:
        return link
    try:
        if is_bundle_absolute:
            target_path = (root / target_base.lstrip("/")).resolve()
        else:
            target_path = (current_file.parent / target_base).resolve()
        root_resolved = root.resolve()
        try:
            target_path.relative_to(root_resolved)
        except ValueError:
            link.outside_bundle = True
            link.target_path = target_path
            return link
        link.target_path = target_path
        link.exists = target_path.exists()
        if link.exists and target_path.name not in RESERVED_NAMES:
            link.target_id = concept_id_for_path(target_path, root_resolved)
        elif target_path.suffix == ".md":
            # Keep a deterministic id for diagnostics even when the target is missing.
            try:
                link.target_id = target_path.relative_to(root_resolved).with_suffix("").as_posix()
            except ValueError:
                pass
    except Exception:
        link.outside_bundle = True
    return link


def links_for_document(path: Path, root: Path, text: str) -> list[MarkdownLink]:
    links: list[MarkdownLink] = []
    for label, raw_target in extract_markdown_links(text):
        link = resolve_internal_link(path, root, raw_target)
        if link is None:
            continue
        link.label = label
        links.append(link)
    return links


def section_body(text: str, heading: str) -> str:
    pattern = re.compile(rf"^#\s+{re.escape(heading)}\s*$", re.M)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^#\s+\S.*$", text[start:], re.M)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()


def extract_citations(body: str) -> list[Citation]:
    citations_text = section_body(body, "Citations")
    if not citations_text:
        return []
    citations: list[Citation] = []
    for raw_line in citations_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^(?:[-*]\s*)?\[(\d+)\]\s*(.*)$", line)
        if match:
            citations.append(Citation(number=match.group(1), text=match.group(2).strip(), raw=line))
        else:
            citations.append(Citation(number=None, text=line, raw=line))
    return citations


def body_citation_refs(body: str) -> set[str]:
    without_citations = body.split("# Citations", 1)[0]
    return set(re.findall(r"(?<!\!)\[(\d+)\](?!\()", without_citations))


def parse_document(path: Path, root: Path) -> OKFDocumentData:
    root = root.resolve()
    path = path.resolve()
    reserved_name = path.name if path.name in RESERVED_NAMES else None
    doc = OKFDocumentData(
        path=path,
        root=root,
        rel_path=rel_path(path, root),
        id=None if reserved_name else concept_id_for_path(path, root),
        is_reserved=reserved_name is not None,
        reserved_name=reserved_name,
    )
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        doc.parse_error = f"cannot read UTF-8 text: {exc}"
        return doc

    frontmatter, body = split_frontmatter(text)
    doc.body = body if frontmatter is not None else text
    if frontmatter is not None:
        try:
            doc.frontmatter, doc.used_fallback_parser = parse_frontmatter(frontmatter)
        except Exception as exc:
            doc.parse_error = f"frontmatter is not parseable YAML: {exc}"
    elif not doc.is_reserved:
        doc.parse_error = "concept document lacks opening/closing YAML frontmatter"

    doc.links = links_for_document(path, root, text)
    doc.citations = extract_citations(doc.body)
    return doc


def scan_bundle(root: Path) -> list[OKFDocumentData]:
    root = root.resolve()
    return [parse_document(path, root) for path in sorted(root.rglob("*.md"))]


def concept_documents(root: Path) -> list[OKFDocumentData]:
    return [doc for doc in scan_bundle(root) if not doc.is_reserved]


def parse_log(text: str) -> list[LogDateGroup]:
    groups: list[LogDateGroup] = []
    matches = list(re.finditer(r"^##\s+(.+)$", text, re.M))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        entries = [line.strip() for line in text[start:end].splitlines() if line.strip().startswith(("-", "*"))]
        groups.append(LogDateGroup(date=match.group(1).strip(), entries=entries))
    return groups


def is_truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def safe_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)

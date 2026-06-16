#!/usr/bin/env python3
"""Validate an OKF bundle with explicit rule layers.

This is a project-level helper, not an OKF protocol requirement.

Profiles:
- spec: official OKF v0.1 hard conformance only.
- reference: spec + the stricter official reference OKFDocument.validate() keys.
- project: reference + this repository's producer-hygiene checks.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from okf_bundle_common import (
    RESERVED_NAMES,
    OKFDocumentData,
    body_citation_refs,
    is_truthy,
    parse_log,
    rel_path,
    safe_string,
    scan_bundle,
    split_frontmatter,
)

REFERENCE_REQUIRED_FRONTMATTER_KEYS = ("type", "title", "description", "timestamp")
PROFILE_ORDER = {"spec": 0, "reference": 1, "project": 2}


@dataclass
class Finding:
    severity: str
    layer: str
    rule_id: str
    path: str
    message: str

    @property
    def level(self) -> str:
        """Backward-compatible alias for older consumers."""
        return self.severity


def add(
    findings: list[Finding],
    severity: str,
    layer: str,
    rule_id: str,
    path: str,
    message: str,
) -> None:
    findings.append(Finding(severity, layer, rule_id, path, message))


def profile_includes(profile: str, target: str) -> bool:
    return PROFILE_ORDER[profile] >= PROFILE_ORDER[target]


def is_iso_date_heading(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def is_iso_datetime(value: Any) -> bool:
    if isinstance(value, datetime):
        return True
    if isinstance(value, date):
        return False
    text = safe_string(value).strip()
    if not text:
        return False
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        datetime.fromisoformat(normalized)
        return True
    except ValueError:
        return False


def load_official_okf_document() -> tuple[Any | None, str]:
    """Return official OKFDocument class if the reference package is available."""
    candidates = (
        "enrichment_agent.bundle.document",
        "src.enrichment_agent.bundle.document",
    )
    errors: list[str] = []
    for module_name in candidates:
        try:
            module = importlib.import_module(module_name)
            okf_document = getattr(module, "OKFDocument")
            return okf_document, module_name
        except Exception as exc:  # pragma: no cover - depends on optional package
            errors.append(f"{module_name}: {exc}")
    return None, "; ".join(errors)


def official_validate_document(okf_document: Any, doc: OKFDocumentData) -> str | None:
    """Run official parse/validate when available.

    The official API shape may evolve; this function deliberately degrades to a
    local equivalent outside the caller so reference profile remains useful.
    """
    text = doc.path.read_text(encoding="utf-8")
    parsed = okf_document.parse(text)
    result = parsed.validate()
    if result is False:
        return "official OKFDocument.validate() returned false"
    return None


def validate_spec(root: Path, docs: list[OKFDocumentData], findings: list[Finding]) -> None:
    if not root.exists() or not root.is_dir():
        add(findings, "error", "spec-hard", "bundle.root.exists", str(root), "bundle path does not exist or is not a directory")
        return

    for doc in docs:
        path = doc.rel_path
        if doc.parse_error and not doc.is_reserved:
            add(findings, "error", "spec-hard", "frontmatter.yaml.parseable", path, doc.parse_error)
            continue

        if doc.is_reserved:
            if doc.reserved_name == "index.md":
                raw_text = doc.path.read_text(encoding="utf-8")
                frontmatter, body = split_frontmatter(raw_text)
                if frontmatter is not None and doc.parse_error:
                    add(findings, "error", "spec-hard", "index.frontmatter.parseable", path, doc.parse_error)
                index_body = body if frontmatter is not None else raw_text
                if not index_body.strip():
                    add(findings, "warning", "spec-hard", "index.body.nonempty", path, "index.md is empty; OKF index should enumerate nearby contents when present")
            elif doc.reserved_name == "log.md":
                groups = parse_log(doc.path.read_text(encoding="utf-8"))
                if not groups:
                    add(findings, "warning", "spec-hard", "log.date_headings.present", path, "log.md has no date headings")
                for group in groups:
                    if not is_iso_date_heading(group.date):
                        add(findings, "error", "spec-hard", "log.date_heading.iso", path, f"log date heading is not ISO YYYY-MM-DD: {group.date}")
            continue

        if not doc.path.name.endswith(".md"):
            continue
        if doc.path.name in RESERVED_NAMES:
            continue
        if doc.parse_error:
            add(findings, "error", "spec-hard", "frontmatter.yaml.parseable", path, doc.parse_error)
            continue
        if not doc.frontmatter:
            add(findings, "error", "spec-hard", "frontmatter.required", path, "concept document lacks parseable YAML frontmatter")
            continue
        if not is_truthy(doc.frontmatter.get("type")):
            add(findings, "error", "spec-hard", "frontmatter.type.required", path, "concept frontmatter has missing/empty type")


def validate_reference(docs: list[OKFDocumentData], findings: list[Finding], use_official: bool) -> None:
    official_class = None
    official_source = ""
    if use_official:
        official_class, official_source = load_official_okf_document()
        if official_class is None:
            add(
                findings,
                "info",
                "reference-strict",
                "reference.official_validator.unavailable",
                "/",
                "official enrichment_agent.bundle.document.OKFDocument is unavailable; using local equivalent for required frontmatter keys",
            )
        else:
            add(
                findings,
                "info",
                "reference-strict",
                "reference.official_validator.available",
                "/",
                f"using official OKFDocument from {official_source}",
            )

    for doc in docs:
        if doc.is_reserved:
            continue
        path = doc.rel_path
        if doc.parse_error:
            continue
        if official_class is not None:
            try:
                official_error = official_validate_document(official_class, doc)
                if official_error:
                    add(findings, "error", "reference-strict", "reference.official_validate", path, official_error)
                continue
            except Exception as exc:
                add(
                    findings,
                    "warning",
                    "reference-strict",
                    "reference.official_validate.fallback",
                    path,
                    f"official OKFDocument.validate() could not run for this document; using local equivalent: {exc}",
                )

        for key in REFERENCE_REQUIRED_FRONTMATTER_KEYS:
            if not is_truthy(doc.frontmatter.get(key)):
                add(
                    findings,
                    "error",
                    "reference-strict",
                    f"reference.frontmatter.{key}.required",
                    path,
                    f"missing/empty frontmatter key required by reference OKFDocument.validate(): {key}",
                )


def main_text_from_index_line(line: str) -> str:
    text = re.sub(r"^[\s*+-]+", "", line.strip())
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", "", text)
    text = text.strip(" -—:：")
    return text


def validate_index_coverage(root: Path, docs: list[OKFDocumentData], findings: list[Finding], strict: bool) -> None:
    severity = "error" if strict else "warning"
    index_path = root / "index.md"
    concepts = {doc.rel_path: doc for doc in docs if not doc.is_reserved}
    if not index_path.exists():
        add(findings, severity, "project-hygiene", "index.root.present", "/index.md", "root index.md is missing; OKF consumers may synthesize one")
        return

    index_text = index_path.read_text(encoding="utf-8")
    linked_paths: set[str] = set()
    lines_by_target: dict[str, list[str]] = {}
    for line in index_text.splitlines():
        for match in re.finditer(r"\[[^\]]+\]\((/[^)#]+\.md)(?:#[^)]+)?\)", line):
            target = match.group(1)
            linked_paths.add(target)
            lines_by_target.setdefault(target, []).append(line)

    for missing in sorted(set(concepts) - linked_paths):
        add(findings, severity, "project-hygiene", "index.root.coverage", "/index.md", f"concept not linked from root index: {missing}")
    for extra in sorted(linked_paths - set(concepts)):
        add(findings, severity, "project-hygiene", "index.root.no_missing_targets", "/index.md", f"root index links to missing concept: {extra}")

    for target, doc in concepts.items():
        if target not in lines_by_target or not doc.description:
            continue
        description = doc.description.strip()
        if not any(description in line or main_text_from_index_line(line) in description for line in lines_by_target[target]):
            add(
                findings,
                "warning",
                "project-hygiene",
                "index.root.description_matches",
                "/index.md",
                f"index entry for {target} does not appear to include the concept description",
            )


def validate_project(root: Path, docs: list[OKFDocumentData], findings: list[Finding], strict: bool, check_citations: bool, check_index_coverage: bool) -> None:
    strict_severity = "error" if strict else "warning"
    concept_docs = [doc for doc in docs if not doc.is_reserved]

    for doc in concept_docs:
        path = doc.rel_path
        if doc.parse_error:
            continue

        if "resource" not in doc.frontmatter:
            add(findings, "warning", "official-soft", "frontmatter.resource.recommended", path, "resource frontmatter is recommended for traceability")
        elif not isinstance(doc.resource, dict):
            add(findings, strict_severity, "project-hygiene", "frontmatter.resource.mapping", path, "resource should be a YAML mapping")

        if "tags" not in doc.frontmatter:
            add(findings, "warning", "official-soft", "frontmatter.tags.recommended", path, "tags frontmatter is recommended for discovery")
        elif not isinstance(doc.tags, list) or not doc.tags or not all(isinstance(tag, str) and tag.strip() for tag in doc.tags):
            add(findings, strict_severity, "project-hygiene", "frontmatter.tags.string_array", path, "tags should be a non-empty list of non-empty strings")

        if is_truthy(doc.timestamp) and not is_iso_datetime(doc.timestamp):
            add(findings, strict_severity, "project-hygiene", "frontmatter.timestamp.iso_datetime", path, "timestamp should be an ISO 8601 datetime")

        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*\.md", doc.path.name):
            add(findings, "warning", "project-hygiene", "filename.kebab_case", path, "concept filename should be lowercase kebab-case")

        for link in doc.links:
            if not link.is_internal_markdown:
                continue
            if link.outside_bundle:
                add(findings, strict_severity, "project-hygiene", "link.internal.inside_bundle", path, f"internal Markdown link points outside the bundle: {link.target_raw}")
                continue
            if not link.is_bundle_absolute:
                add(findings, "warning", "official-soft", "link.internal.bundle_absolute", path, f"internal concept link is relative; bundle-absolute links are recommended: {link.target_raw}")
            if not link.exists:
                add(findings, strict_severity, "project-hygiene", "link.internal.target_exists", path, f"internal Markdown link target does not exist: {link.target_raw}")

        if check_citations:
            refs = body_citation_refs(doc.body)
            citation_numbers = {citation.number for citation in doc.citations if citation.number}
            if not doc.citations:
                add(findings, "warning", "official-soft", "citations.section.present", path, "concept body has no non-empty # Citations section")
            if refs - citation_numbers:
                add(findings, strict_severity, "project-hygiene", "citations.refs.defined", path, f"body references missing citation entries: {', '.join(sorted(refs - citation_numbers))}")
            if citation_numbers - refs:
                add(findings, "warning", "project-hygiene", "citations.entries.used", path, f"citation entries are not referenced in body: {', '.join(sorted(citation_numbers - refs))}")
            for citation in doc.citations:
                if citation.number is None:
                    add(findings, "warning", "project-hygiene", "citations.entries.numbered", path, f"citation entry is not numbered: {citation.raw}")

    if check_index_coverage:
        validate_index_coverage(root, docs, findings, strict)

    for doc in docs:
        if doc.reserved_name != "log.md":
            continue
        groups = parse_log(doc.path.read_text(encoding="utf-8"))
        parsed_dates: list[date] = []
        for group in groups:
            if is_iso_date_heading(group.date):
                parsed_dates.append(date.fromisoformat(group.date))
        if parsed_dates != sorted(parsed_dates, reverse=True):
            add(findings, "warning", "project-hygiene", "log.date_order.newest_first", doc.rel_path, "log.md date headings should be ordered newest first")


def validate_bundle(
    root: Path,
    *,
    profile: str,
    strict_project: bool = False,
    check_citations: bool = True,
    check_index_coverage: bool = True,
    use_official_reference: bool = True,
    tolerate_broken_links: bool = False,
) -> list[Finding]:
    root = root.resolve()
    findings: list[Finding] = []
    if not root.exists() or not root.is_dir():
        add(findings, "error", "spec-hard", "bundle.root.exists", str(root), "bundle path does not exist or is not a directory")
        return findings

    docs = scan_bundle(root)
    validate_spec(root, docs, findings)
    if profile_includes(profile, "reference"):
        validate_reference(docs, findings, use_official_reference)
    if profile_includes(profile, "project"):
        validate_project(root, docs, findings, strict_project, check_citations, check_index_coverage)

    if tolerate_broken_links:
        for finding in findings:
            if finding.rule_id == "link.internal.target_exists" and finding.severity == "error":
                finding.severity = "warning"
                finding.message += " (downgraded by --tolerate-broken-links)"

    return findings


def output_text(findings: list[Finding]) -> None:
    errors = [finding for finding in findings if finding.severity == "error"]
    warnings = [finding for finding in findings if finding.severity == "warning"]
    infos = [finding for finding in findings if finding.severity == "info"]
    print(f"VALIDATION_ERRORS={len(errors)}")
    for finding in errors:
        print(f"ERROR [{finding.layer}/{finding.rule_id}]: {finding.path}: {finding.message}")
    print(f"WARNINGS={len(warnings)}")
    for finding in warnings:
        print(f"WARN [{finding.layer}/{finding.rule_id}]: {finding.path}: {finding.message}")
    if infos:
        print(f"INFO={len(infos)}")
        for finding in infos:
            print(f"INFO [{finding.layer}/{finding.rule_id}]: {finding.path}: {finding.message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an OKF bundle with spec/reference/project rule layers")
    parser.add_argument("bundle", type=Path, help="Path to the OKF bundle directory")
    parser.add_argument("--profile", choices=("spec", "reference", "project"), default="project", help="Validation profile; default: project")
    parser.add_argument("--strict-project", action="store_true", help="Upgrade selected project-hygiene warnings to errors")
    parser.add_argument("--spec-only", action="store_true", help="Compatibility alias for --profile spec")
    parser.add_argument("--allow-relative-links", action="store_true", help="Compatibility flag; relative links are only project-level warnings")
    parser.add_argument("--tolerate-broken-links", action="store_true", help="Downgrade project broken-link errors; OKF consumers must tolerate broken links")
    parser.add_argument("--no-citations-check", action="store_true", help="Disable project-level citation checks")
    parser.add_argument("--no-index-coverage-check", action="store_true", help="Disable project-level root index coverage checks")
    parser.add_argument("--no-official-reference", action="store_true", help="Do not attempt to import official OKFDocument; use local equivalent")
    parser.add_argument("--json", action="store_true", help="Emit JSON findings")
    args = parser.parse_args()

    profile = "spec" if args.spec_only else args.profile
    findings = validate_bundle(
        args.bundle,
        profile=profile,
        strict_project=args.strict_project,
        check_citations=not args.no_citations_check,
        check_index_coverage=not args.no_index_coverage_check,
        use_official_reference=not args.no_official_reference,
        tolerate_broken_links=args.tolerate_broken_links,
    )

    errors = [finding for finding in findings if finding.severity == "error"]
    warnings = [finding for finding in findings if finding.severity == "warning"]
    infos = [finding for finding in findings if finding.severity == "info"]

    if args.json:
        print(
            json.dumps(
                {
                    "profile": profile,
                    "errors": len(errors),
                    "warnings": len(warnings),
                    "infos": len(infos),
                    "findings": [asdict(finding) for finding in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        output_text(findings)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

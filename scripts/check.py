#!/usr/bin/env python3
"""Check the documentation before a commit. Needs only Python 3, no packages.

    python3 scripts/check.py
    python3 scripts/check.py --schema /path/to/docs.schema.json

It verifies that:
  - docs.json is valid JSON, has the fields Mintlify requires, and (with --schema, a copy
    of https://mintlify.com/docs.json) matches Mintlify's published schema;
  - every page in the navigation exists, and every page file is in the navigation;
  - every page has a quoted title and a description of at most 160 characters;
  - every internal link, anchor and image resolves;
  - component tags are balanced and prose holds no stray "<" or "{" that MDX would read
    as code;
  - no placeholder text, credential-looking value or unexpected email address is left.

It exits with 1 when it finds an error. Warnings do not fail the run.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE_SUFFIXES = (".mdx", ".md")
# Files at the root that are not pages.
NOT_PAGES = {"README.md", "AGENTS.md", "LICENSE.md", "CHANGELOG.md", "CONTRIBUTING.md", "skill.md", "BEFORE_PUBLISHING.md"}
SKIP_DIRS = {".git", "node_modules", ".mintlify", "scripts", "images", "logo", "snippets"}

COMPONENTS = [
    "Steps", "Step", "Tabs", "Tab", "AccordionGroup", "Accordion", "Columns", "Column",
    "Card", "Frame", "Note", "Warning", "Tip", "Info", "Check", "Danger", "Callout",
    "Tooltip", "Badge", "Visibility", "Prompt", "CodeGroup", "Tile", "Update",
]
HTML_TAGS = {"img", "kbd", "br", "a", "code", "strong", "em", "sub", "sup", "video", "iframe", "span", "div", "details", "summary", "p", "ul", "ol", "li", "table", "thead", "tbody", "tr", "td", "th"}

PLACEHOLDERS = re.compile(
    r"\b(TODO|TBD|FIXME|XXX|WIP|lorem ipsum|coming soon|to be written|Mintlify Starter|your-package|your-cli)\b",
    re.IGNORECASE,
)
ALLOWED_EMAIL_DOMAINS = {"livehq.dev", "example.com", "example.org", "acme.dev"}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
# A URL that carries a password, and well-known token shapes.
SECRETS = [
    re.compile(r"\b(ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bsk_(live|test)_[A-Za-z0-9]{16,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
URL_WITH_PASSWORD = re.compile(r"[a-z][a-z0-9+.-]*://[^\s/:@`'\"]+:([^\s/@`'\"]+)@")
PLACEHOLDER_PASSWORD = re.compile(r"password|passwd|secret|\*|…|\.\.\.|<|&lt;|your|example|xxxx", re.IGNORECASE)

errors: list[str] = []
warnings: list[str] = []


def error(where: str, message: str) -> None:
    errors.append(f"{where}: {message}")


def warn(where: str, message: str) -> None:
    warnings.append(f"{where}: {message}")


# --- docs.json -------------------------------------------------------------------------


def load_config() -> dict:
    path = ROOT / "docs.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as problem:
        error("docs.json", f"cannot be read as JSON: {problem}")
        sys.exit(report())
    for key in ("theme", "name", "navigation"):
        if key not in config:
            error("docs.json", f'missing required field "{key}"')
    if not re.fullmatch(r"#([a-fA-F0-9]{6}|[a-fA-F0-9]{3})", str(config.get("colors", {}).get("primary", ""))):
        error("docs.json", "colors.primary must be a hex color")
    themes = {"mint", "maple", "palm", "willow", "linden", "almond", "aspen", "sequoia", "luma"}
    if config.get("theme") not in themes:
        error("docs.json", f'theme "{config.get("theme")}" is not one of {sorted(themes)}')
    # Mintlify refuses a relative path in these: they must be full URLs.
    outside = [link.get("href") for link in config.get("navbar", {}).get("links", [])]
    outside.append(config.get("navbar", {}).get("primary", {}).get("href"))
    outside += [item.get("href") for column in config.get("footer", {}).get("links", []) for item in column.get("items", [])]
    for href in outside:
        if href is not None and not re.match(r"^(https://|mailto:)", str(href)):
            error("docs.json", f'navbar and footer links must be full URLs, not "{href}"')
    for key in ("logo", "favicon"):
        value = config.get(key)
        paths = [value] if isinstance(value, str) else [value.get(k) for k in ("light", "dark")] if isinstance(value, dict) else []
        for item in paths:
            if item and not (ROOT / item.lstrip("/")).is_file():
                error("docs.json", f"{key} file {item} does not exist")
    return config


def nav_pages(node, found: list[str]) -> list[str]:
    """Every page path named anywhere in the navigation, in order."""
    if isinstance(node, str):
        found.append(node)
    elif isinstance(node, list):
        for item in node:
            nav_pages(item, found)
    elif isinstance(node, dict):
        if isinstance(node.get("root"), str):
            found.append(node["root"])
        for key in ("pages", "groups", "tabs", "anchors", "dropdowns", "menu", "products", "versions", "languages"):
            if key in node:
                nav_pages(node[key], found)
    return found


class Schema:
    """The part of JSON Schema draft-07 that Mintlify's docs.json schema uses."""

    def __init__(self, schema: dict):
        self.root = schema

    def resolve(self, ref: str) -> dict:
        node = self.root
        for part in ref.lstrip("#/").split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            node = node[int(part)] if isinstance(node, list) else node[part]
        return node

    def check(self, value, schema, path: str = "") -> list[tuple[int, str]]:
        """Problems as (depth, message); deeper ones are the more specific."""
        if schema is True or schema == {}:
            return []
        if schema is False:
            return [(path.count("."), f"{path or 'docs.json'} is not allowed here")]
        out: list[tuple[int, str]] = []
        depth = path.count(".") + path.count("[")

        def bad(message: str) -> None:
            out.append((depth, f"{path or '(top)'}: {message}"))

        if "$ref" in schema:
            return self.check(value, self.resolve(schema["$ref"]), path)
        kinds = schema.get("type")
        if kinds:
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if not any(self.is_type(value, kind) for kind in kinds):
                bad(f"must be {' or '.join(kinds)}")
                return out
        if "const" in schema and value != schema["const"]:
            bad(f"must be {schema['const']!r}")
        if "enum" in schema and value not in schema["enum"]:
            bad(f"must be one of {schema['enum']}")
        if isinstance(value, str):
            if len(value) < schema.get("minLength", 0):
                bad("is too short")
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                bad("is too long")
            if "pattern" in schema and not re.search(schema["pattern"], value):
                bad(f"must match {schema['pattern']}")
            if schema.get("format") == "uri" and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value):
                bad("must be a full URL (with https:// or mailto:)")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                bad(f"must be at least {schema['minimum']}")
            if "maximum" in schema and value > schema["maximum"]:
                bad(f"must be at most {schema['maximum']}")
        if isinstance(value, list):
            if len(value) < schema.get("minItems", 0):
                bad("has too few items")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                bad("has too many items")
            if isinstance(schema.get("items"), (dict, bool)):
                for index, item in enumerate(value):
                    out += self.check(item, schema["items"], f"{path}[{index}]")
        if isinstance(value, dict):
            properties = schema.get("properties", {})
            for name in schema.get("required", []):
                if name not in value:
                    bad(f'is missing "{name}"')
            for name, item in value.items():
                where = f"{path}.{name}" if path else name
                if name in properties:
                    out += self.check(item, properties[name], where)
                elif "additionalProperties" in schema:
                    extra = schema["additionalProperties"]
                    if extra is False:
                        out.append((depth + 1, f'{where}: "{name}" is not a known field'))
                    elif isinstance(extra, dict):
                        out += self.check(item, extra, where)
                if "propertyNames" in schema:
                    out += self.check(name, schema["propertyNames"], where)
        for key in ("allOf",):
            for part in schema.get(key, []):
                out += self.check(value, part, path)
        for key in ("anyOf", "oneOf"):
            if key in schema:
                attempts = [self.check(value, part, path) for part in schema[key]]
                if not any(not attempt for attempt in attempts):
                    # Report the alternative that got furthest: it is the one meant.
                    best = max(attempts, key=lambda a: (min(d for d, _ in a), -len(a)))
                    out += best
        if "not" in schema and not self.check(value, schema["not"], path):
            bad("is not allowed here")
        return out

    @staticmethod
    def is_type(value, kind: str) -> bool:
        return {
            "string": isinstance(value, str),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "null": value is None,
        }.get(kind, True)


def check_schema(config: dict, schema_path: str) -> None:
    try:
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as problem:
        error("--schema", f"cannot read {schema_path}: {problem}")
        return
    problems = Schema(schema).check(config, schema)
    seen = set()
    for _, message in sorted(problems, key=lambda item: -item[0]):
        if message not in seen:
            seen.add(message)
            error("docs.json (schema)", message)
    if not problems:
        print("docs.json matches Mintlify's schema.")


# --- pages -----------------------------------------------------------------------------


def page_files() -> dict[str, Path]:
    """Every page file, keyed by its path without the extension."""
    pages = {}
    for path in sorted(ROOT.rglob("*")):
        if path.suffix not in PAGE_SUFFIXES or not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if relative.parts[0] in SKIP_DIRS or relative.parts[0].startswith("."):
            continue
        if len(relative.parts) == 1 and relative.name in NOT_PAGES:
            continue
        pages[str(relative.with_suffix(""))] = path
    return pages


def split_frontmatter(text: str) -> tuple[dict[str, str], str, int]:
    """Frontmatter as raw strings, the body, and the body's first line number."""
    if not text.startswith("---\n"):
        return {}, text, 1
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text, 1
    block = text[4:end]
    fields = {}
    for line in block.splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    body_start = text.find("\n", end + 1) + 1
    return fields, text[body_start:], text[:body_start].count("\n") + 1


def strip_code(body: str) -> str:
    """The body with fenced blocks and inline code blanked, lines kept in place."""
    out, fence = [], None
    for line in body.split("\n"):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker.group(1)[0] * 3
            elif line.strip().startswith(fence):
                fence = None
            out.append("")
            continue
        out.append("" if fence else re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), line))
    return "\n".join(out)


def slug(heading: str) -> str:
    """Mintlify's anchor for a heading, near enough: lower case, words joined by dashes."""
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_]", "", text).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"[\s]+", "-", text).strip("-")


def anchors_of(body: str) -> set[str]:
    found = set()
    for match in re.finditer(r"^#{1,6}\s+(.+?)\s*$", strip_fences(body), re.MULTILINE):
        found.add(slug(match.group(1)))
    for match in re.finditer(r'<(?:Accordion|Step|Tab)\b[^>]*?\b(?:id|title)="([^"]+)"', body):
        found.add(slug(match.group(1)))
    for match in re.finditer(r'\bid="([^"]+)"', body):
        found.add(match.group(1))
    return found


def strip_fences(body: str) -> str:
    out, fence = [], None
    for line in body.split("\n"):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            fence = None if fence else marker.group(1)
            out.append("")
            continue
        out.append("" if fence else line)
    return "\n".join(out)


def check_page(name: str, path: Path, pages: dict[str, Path], redirects: set[str], anchors: dict[str, set[str]]) -> None:
    where = str(path.relative_to(ROOT))
    text = path.read_text(encoding="utf-8")
    fields, body, first_line = split_frontmatter(text)

    for key in ("title", "description"):
        value = fields.get(key, "")
        if not value:
            error(where, f"frontmatter has no {key}")
        elif not (value.startswith('"') and value.endswith('"') and len(value) >= 2):
            error(where, f"frontmatter {key} must be in double quotes")
    description = fields.get("description", "").strip('"')
    if len(description) > 160:
        warn(where, f"description is {len(description)} characters (keep it to 160)")
    if re.search(r"^#\s", strip_fences(body), re.MULTILINE):
        error(where, "the page has an H1 (the title comes from frontmatter; start at ##)")

    prose = strip_code(body)
    lines = prose.split("\n")

    def line_of(offset: int) -> int:
        return first_line + prose.count("\n", 0, offset)

    # Links and images.
    targets = []
    for match in re.finditer(r"!?\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)", prose):
        targets.append((match.group(1), match.start(), match.group(0).startswith("!")))
    for match in re.finditer(r'\b(href|src|img)=["\']([^"\']+)["\']', prose):
        targets.append((match.group(2), match.start(), match.group(1) != "href"))
    for target, offset, is_asset in targets:
        at = f"{where}:{line_of(offset)}"
        if re.match(r"^(https?:|mailto:|tel:|cursor:|vscode:)", target):
            if target.startswith("http:") and "localhost" not in target and "127.0.0.1" not in target:
                warn(at, f"link uses http://, not https://: {target}")
            continue
        if target.startswith("#"):
            if target[1:] and target[1:] not in anchors[name]:
                error(at, f"no heading on this page for {target}")
            continue
        if "{{" in target:
            continue
        if not target.startswith("/"):
            error(at, f'link "{target}" must be root-relative (start with /) or a full URL')
            continue
        route, _, fragment = target.partition("#")
        route = route.split("?")[0]
        key = route.strip("/") or "index"
        if is_asset or re.search(r"\.[a-z0-9]{2,5}$", route):
            if not (ROOT / route.lstrip("/")).is_file():
                error(at, f"file {route} does not exist")
            continue
        if key in pages:
            if fragment and fragment not in anchors[key]:
                error(at, f"{route} has no heading for #{fragment}")
        elif route.rstrip("/") not in redirects:
            error(at, f"link to {route}: no such page")

    # Images need alt text.
    for match in re.finditer(r"<img\b[^>]*>", prose):
        if not re.search(r'\balt="[^"]{8,}"', match.group(0)):
            error(f"{where}:{line_of(match.start())}", "image without real alt text")
    for match in re.finditer(r"!\[\s*\]\(", prose):
        error(f"{where}:{line_of(match.start())}", "image without alt text")

    # Component tags are balanced.
    for tag in COMPONENTS:
        opened = len(re.findall(rf"<{tag}(?=[\s>])(?![^>]*/>)", prose))
        closed = len(re.findall(rf"</{tag}>", prose))
        if opened != closed:
            error(where, f"<{tag}> is opened {opened} times and closed {closed} times")

    # Prose that MDX would read as code.
    for number, line in enumerate(lines, start=first_line):
        for match in re.finditer(r"<(/?)([A-Za-z][A-Za-z0-9.]*)?", line):
            tag = match.group(2)
            if tag is None:
                error(f"{where}:{number}", 'a bare "<" in prose: write &lt; or put it in backticks')
            elif tag not in COMPONENTS and tag.lower() not in HTML_TAGS and not tag.startswith("Tree"):
                error(f"{where}:{number}", f"<{tag}> is not a component this site uses")
        # Two "$" on a line turn what is between them into a formula.
        if re.search(r"(?<!\\)\$", line):
            error(f"{where}:{number}", 'a "$" in prose: write \\$ so it is not read as a formula')
        cleaned = re.sub(r"\{\{[A-Za-z0-9_.-]+\}\}", "", line)
        cleaned = re.sub(r"=\{[^{}]*\}", "", cleaned)
        if "{" in cleaned or "}" in cleaned:
            error(f"{where}:{number}", 'a "{" or "}" in prose: put it in backticks')

    # Leftovers and things that must never be published.
    for number, line in enumerate(text.split("\n"), start=1):
        found = PLACEHOLDERS.search(line)
        if found:
            error(f"{where}:{number}", f'placeholder text "{found.group(0)}"')
        for pattern in SECRETS:
            if pattern.search(line):
                error(f"{where}:{number}", "looks like a credential")
        for match in URL_WITH_PASSWORD.finditer(line):
            if not PLACEHOLDER_PASSWORD.search(match.group(1)):
                error(f"{where}:{number}", "a URL with what looks like a real password")
        for match in EMAIL.finditer(line):
            # "user:password@host" inside a connection URL is not an email address.
            token = re.split(r"\s", line[: match.start()])[-1]
            if "://" in token:
                continue
            domain = match.group(1).lower()
            if domain not in ALLOWED_EMAIL_DOMAINS and not domain.endswith((".internal", ".example", ".test")):
                error(f"{where}:{number}", f"email address at {domain}: use an example.com address")


def report() -> int:
    for message in warnings:
        print(f"warning  {message}")
    for message in errors:
        print(f"ERROR    {message}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s).")
    return 1 if errors else 0


def main() -> int:
    config = load_config()
    if "--schema" in sys.argv:
        check_schema(config, sys.argv[sys.argv.index("--schema") + 1])

    pages = page_files()
    listed = nav_pages(config.get("navigation", {}), [])
    for name in listed:
        if name.startswith("/") or name.endswith(PAGE_SUFFIXES):
            error("docs.json", f'page "{name}" must be written without a leading slash or extension')
        elif name not in pages:
            error("docs.json", f'navigation names "{name}" but no such file exists')
    for name in sorted(set(listed)):
        if listed.count(name) > 1:
            error("docs.json", f'"{name}" is in the navigation more than once')
    for name in pages:
        if name not in listed:
            error(f"{name}.mdx", "is not in the navigation, so it would not be published in it")

    redirects = set()
    for item in config.get("redirects", []):
        redirects.add(item.get("source", "").rstrip("/"))
        destination = item.get("destination", "").strip("/")
        if destination and not destination.startswith("http") and destination not in pages:
            error("docs.json", f'redirect to "{item.get("destination")}": no such page')

    anchors = {name: anchors_of(split_frontmatter(path.read_text(encoding="utf-8"))[1]) for name, path in pages.items()}
    for name, path in pages.items():
        check_page(name, path, pages, redirects, anchors)

    images = {str(p.relative_to(ROOT)) for p in (ROOT / "images").rglob("*") if p.is_file()} if (ROOT / "images").is_dir() else set()
    everything = "\n".join(path.read_text(encoding="utf-8") for path in pages.values())
    for image in sorted(images):
        if f"/{image}" not in everything:
            warn(image, "is not used on any page")

    print(f"{len(pages)} pages, {len(set(listed))} in the navigation, {len(images)} images.")
    return report()


if __name__ == "__main__":
    sys.exit(main())

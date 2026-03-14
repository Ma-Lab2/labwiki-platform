#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

from docx import Document
from docx.oxml.ns import qn


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text.strip(), flags=re.UNICODE)
    text = re.sub(r"-{2,}", "-", text).strip("-").lower()
    return text or "section"


def normalize_section_title(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


@dataclass
class Section:
    index: int
    chapter: str
    title: str
    slug: str
    lines: list[str] = field(default_factory=list)

    @property
    def filename(self) -> str:
        return f"{self.index:02d}-{self.slug}.md"


def iter_embed_ids(paragraph) -> Iterable[str]:
    for blip in paragraph._element.iter():
        if blip.tag.endswith("}blip"):
            rid = blip.get(qn("r:embed"))
            if rid:
                yield rid


def paragraph_to_markdown(paragraph) -> list[str]:
    text = paragraph.text.strip()
    if not text:
        return []

    style = getattr(paragraph.style, "name", "")
    if style == "Caption":
        return [f"*图注：{text}*"]
    if style == "List Paragraph":
        return [f"- {text}"]
    return [text]


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    root = Path("/mnt/c/Songtan/课题组wiki")
    source = root / "【排版结果】【工作手册】20250723.docx"
    out_root = root / "docs" / "intake" / "field-manual-20250723"
    sections_dir = out_root / "sections"
    images_all_dir = out_root / "images" / "all"
    images_selected_dir = out_root / "images" / "selected"
    manifest_path = out_root / "image-manifest.csv"
    outline_path = out_root / "outline.md"
    readme_path = out_root / "README.md"

    ensure_clean_dir(sections_dir)
    ensure_clean_dir(images_all_dir)
    images_selected_dir.mkdir(parents=True, exist_ok=True)

    doc = Document(str(source))
    zip_doc = ZipFile(source)

    chapter = ""
    section: Section | None = None
    subsection = ""
    sections: list[Section] = []
    outline: list[str] = [
        "# Field Manual Intake",
        "",
        f"- Source: `{source.name}`",
        "- Scope: Heading 2 sections from the 2025-07-23 target-area work manual",
        "",
        "## Outline",
        "",
    ]
    image_rows: list[dict[str, str]] = []
    image_counter = 0
    last_image_row: dict[str, str] | None = None

    for idx, para in enumerate(doc.paragraphs):
        text = normalize_section_title(para.text)
        style = getattr(para.style, "name", "")

        if style == "Heading 1" and text:
            chapter = text
            outline.append(f"- {chapter}")
            subsection = ""
            continue

        if style == "Heading 2" and text:
            section = Section(
                index=len(sections) + 1,
                chapter=chapter,
                title=text,
                slug=slugify(text),
            )
            sections.append(section)
            section.lines.extend(
                [
                    f"# {text}",
                    "",
                    f"- Source chapter: {chapter}",
                    f"- Source section: {text}",
                    "",
                ]
            )
            outline.append(f"  - `{section.filename}` {text}")
            subsection = ""
            continue

        if section is None:
            continue

        if style == "Heading 3" and text:
            subsection = text
            section.lines.extend(["", f"## {text}", ""])
            continue

        md_lines = paragraph_to_markdown(para)
        if md_lines:
            section.lines.extend(md_lines)
            section.lines.append("")

        for rid in iter_embed_ids(para):
            rel = doc.part.rels[rid]
            target = rel.target_ref
            ext = Path(target).suffix or ".bin"
            image_counter += 1
            filename = f"FieldManual-20250723-{section.slug}-{image_counter:03d}{ext.lower()}"
            blob = rel.target_part.blob
            (images_all_dir / filename).write_bytes(blob)

            row = {
                "image_id": f"{image_counter:03d}",
                "chapter": chapter,
                "section": section.title,
                "subsection": subsection,
                "paragraph_index": str(idx),
                "source_target": target,
                "extracted_name": filename,
                "caption": "",
                "selected_for_wiki": "review-needed",
                "notes": "",
            }
            image_rows.append(row)
            last_image_row = row

            section.lines.extend(
                [
                    f"![{section.title} image {image_counter}](../images/all/{filename})",
                    "",
                ]
            )

        if style == "Caption" and last_image_row and text:
            last_image_row["caption"] = text

    for item in sections:
        (sections_dir / item.filename).write_text("\n".join(item.lines).strip() + "\n", encoding="utf-8")

    with manifest_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "image_id",
                "chapter",
                "section",
                "subsection",
                "paragraph_index",
                "source_target",
                "extracted_name",
                "caption",
                "selected_for_wiki",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(image_rows)

    outline_path.write_text("\n".join(outline).strip() + "\n", encoding="utf-8")
    readme_path.write_text(
        "\n".join(
            [
                "# Field Manual Intake Workspace",
                "",
                "This directory stores the split working copy of the 2025-07-23 target-area work manual.",
                "",
                "## Contents",
                "",
                "- `outline.md`: chapter and section map extracted from the source `.docx`.",
                "- `sections/`: one markdown fragment per Heading 2 section.",
                "- `image-manifest.csv`: image-to-section mapping and wiki selection status.",
                "- `images/all/`: full local image extraction for manual review.",
                "- `images/selected/`: the subset chosen for wiki upload.",
                "",
                "## Notes",
                "",
                "- `images/all/` is intended as a local intake cache.",
                "- Only selected images should later be uploaded into the wiki.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (images_all_dir / ".gitkeep").write_text("", encoding="utf-8")
    (images_selected_dir / ".gitkeep").write_text("", encoding="utf-8")
    zip_doc.close()


if __name__ == "__main__":
    main()

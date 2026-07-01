from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "template" / "论文模板.docx"
TARGET = ROOT / "docs" / "EduGuard论文初稿.docx"
BACKUP = ROOT / "docs" / "EduGuard论文初稿.header-footer-backup.docx"

SHORT_TITLE = "EduGuard：面向学生-AI交互的行为感知支架式教学系统"


def replace_text_preserve_runs(container, replacements: dict[str, str]) -> None:
    for paragraph in container.paragraphs:
        for old, new in replacements.items():
            if old not in paragraph.text:
                continue
            # Header placeholders are simple text runs in the template. Replace
            # at paragraph level so PAGE fields in separate runs stay intact.
            for run in paragraph.runs:
                if old in run.text:
                    run.text = run.text.replace(old, new)


def copy_part(src, dst) -> None:
    dst.is_linked_to_previous = False
    dst_el = dst._element
    for child in list(dst_el):
        dst_el.remove(child)
    for child in src._element:
        dst_el.append(deepcopy(child))


def main() -> None:
    if not TARGET.exists():
        raise FileNotFoundError(TARGET)
    shutil.copyfile(TARGET, BACKUP)

    template = Document(str(TEMPLATE))
    target = Document(str(TARGET))

    # The template uses section 0 for first-page-style front matter and section
    # 1 for正文页眉. The generated paper currently has two sections: front matter
    # and two-column body.
    for idx, section in enumerate(target.sections):
        src_idx = 0 if idx == 0 else 1
        copy_part(template.sections[src_idx].header, section.header)
        copy_part(template.sections[src_idx].footer, section.footer)
        replace_text_preserve_runs(
            section.header,
            {
                "作者名 等：题目": SHORT_TITLE,
                "题目": SHORT_TITLE,
            },
        )

    target.save(str(TARGET))


if __name__ == "__main__":
    main()

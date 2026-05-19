import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "docs" / "RTG-CPR-EasyModev1.1_CN.pdf"
OUTPUT_DIR = ROOT / "docs" / "extracted"
IMAGE_OUTPUT_DIR = OUTPUT_DIR / "images"


@dataclass(frozen=True)
class Section:
    slug: str
    title: str
    start_page: int
    end_page: int


SECTIONS = [
    Section("00_封面", "封面", 1, 1),
    Section("01_入门与赛博朋克态度", "入门与赛博朋克态度", 2, 3),
    Section("02_黑暗未来简史", "黑暗未来简史", 3, 8),
    Section("03_夜之城", "夜之城", 8, 10),
    Section("04_街头术语", "街头术语", 10, 11),
    Section("05_技能列表", "技能列表", 12, 14),
    Section("06_技能判定", "技能判定", 14, 15),
    Section("07_战斗规则", "战斗规则", 15, 21),
    Section("08_预设角色资料", "预设角色资料", 22, 26),
    Section("09_人生路径", "人生路径", 27, 31),
    Section("10_主持赛博朋克", "主持赛博朋克", 32, 32),
    Section("11_游戏主持人任务", "游戏主持人任务", 33, 36),
    Section("12_预设角色卡", "预设角色卡", 37, 46),
    Section("13_附录与封底", "附录与封底", 47, 48),
]


IMAGE_NOTES = {
    1: "封面图片。",
    23: "战术地图/场景图，无规则正文。",
    24: "仓库/装货区战术地图，无规则正文。",
    25: "仓库/装货区战术地图延伸，无规则正文。",
    26: "战术地图/场景图，无规则正文。",
    47: "宣传插图；少量文字已由 PDF 文本层抽取。",
}


def normalize_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"\s+", " ", line)
    return line


def normalize_text(text: str) -> str:
    lines = [normalize_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    cleaned: list[str] = []
    for line in lines:
        if line == "EASY MODE":
            continue
        if re.fullmatch(r"\d+", line):
            continue
        cleaned.append(line)

    return "\n".join(cleaned).strip()


def extract_pages(reader: PdfReader) -> dict[int, str]:
    pages: dict[int, str] = {}

    for page_number, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        pages[page_number] = normalize_text(raw_text)

    return pages


def export_page_images(reader: PdfReader, page_numbers: list[int]) -> dict[int, list[str]]:
    IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    exported: dict[int, list[str]] = {}

    for page_number in page_numbers:
        page = reader.pages[page_number - 1]
        exported[page_number] = []
        for image_index, image in enumerate(page.images, start=1):
            suffix = Path(image.name).suffix or ".bin"
            output_name = f"page_{page_number:02d}_{image_index:02d}{suffix}"
            output_path = IMAGE_OUTPUT_DIR / output_name
            output_path.write_bytes(image.data)
            exported[page_number].append(f"images/{output_name}")

    return exported


def write_page_document(pages: dict[int, str]) -> None:
    lines = [
        "# 规则书全文按页",
        "",
        f"来源文件：`{PDF_PATH.name}`",
        "",
        "说明：本文档由 PDF 文本层自动抽取生成。若某些页面为空或内容很少，通常表示该页可能是图片化页面，需要后续人工或 OCR 补录。",
        "",
    ]

    for page_number in sorted(pages):
        lines.append(f"## 第 {page_number} 页")
        lines.append("")
        lines.append(pages[page_number] or "_本页未从 PDF 文本层抽取到正文。_")
        lines.append("")

    (OUTPUT_DIR / "00_全文按页.md").write_text(
        "\n".join(lines),
        encoding="utf-8-sig",
    )


def write_section_documents(pages: dict[int, str]) -> None:
    for section in SECTIONS:
        lines = [
            f"# {section.title}",
            "",
            f"来源页码：第 {section.start_page}-{section.end_page} 页",
            "",
        ]

        for page_number in range(section.start_page, section.end_page + 1):
            lines.append(f"## 第 {page_number} 页")
            lines.append("")
            lines.append(pages.get(page_number) or "_本页未从 PDF 文本层抽取到正文。_")
            lines.append("")

        output_path = OUTPUT_DIR / f"{section.slug}.md"
        output_path.write_text("\n".join(lines), encoding="utf-8-sig")


def write_index(pages: dict[int, str], exported_images: dict[int, list[str]]) -> None:
    low_text_pages = [page for page, text in pages.items() if len(text) < 80]

    lines = [
        "# 规则书抽取索引",
        "",
        f"来源文件：`{PDF_PATH.name}`",
        f"总页数：{len(pages)}",
        "",
        "## 章节文档",
        "",
    ]

    for section in SECTIONS:
        filename = f"{section.slug}.md"
        lines.append(
            f"- [{section.title}](./{filename})：第 {section.start_page}-{section.end_page} 页"
        )

    lines.extend(
        [
            "",
            "## 完整底稿",
            "",
            "- [规则书全文按页](./00_全文按页.md)",
            "",
            "## 需要复核的页面",
            "",
            "以下页面从 PDF 文本层抽取到的内容很少，可能是图片化页面、广告页、空白页或复杂表格页：",
            "",
        ]
    )

    if low_text_pages:
        for page_number in low_text_pages:
            lines.append(f"- 第 {page_number} 页")
    else:
        lines.append("- 无")

    lines.extend(["", "## 已导出的页面图片", ""])
    exported_any = False
    for page_number, image_paths in exported_images.items():
        if not image_paths:
            continue
        exported_any = True
        lines.append(f"### 第 {page_number} 页")
        lines.append("")
        note = IMAGE_NOTES.get(page_number)
        if note:
            lines.append(f"说明：{note}")
            lines.append("")
        for image_path in image_paths:
            lines.append(f"- [{image_path}](./{image_path})")
        lines.append("")

    if not exported_any:
        lines.append("- 无")

    (OUTPUT_DIR / "README.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8-sig",
    )


def write_image_notes(exported_images: dict[int, list[str]]) -> None:
    lines = [
        "# 图片页说明",
        "",
        "本文档记录 PDF 文本层抽取较少、并额外导出为图片的页面。",
        "",
    ]

    for page_number, image_paths in exported_images.items():
        if not image_paths:
            continue

        lines.append(f"## 第 {page_number} 页")
        lines.append("")
        lines.append(IMAGE_NOTES.get(page_number, "需要人工复核。"))
        lines.append("")
        for image_path in image_paths:
            lines.append(f"- [{image_path}](./{image_path})")
        lines.append("")

    (OUTPUT_DIR / "99_图片页说明.md").write_text(
        "\n".join(lines),
        encoding="utf-8-sig",
    )


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"未找到规则书 PDF：{PDF_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(PDF_PATH))
    pages = extract_pages(reader)
    low_text_pages = [page for page, text in pages.items() if len(text) < 80]
    exported_images = export_page_images(reader, low_text_pages)
    write_index(pages, exported_images)
    write_image_notes(exported_images)
    write_page_document(pages)
    write_section_documents(pages)
    print(f"已抽取 {len(pages)} 页到 {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

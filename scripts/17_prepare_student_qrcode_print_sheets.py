from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path

from survey.human_eval_paths import build_human_eval_paths

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HUMAN_EVAL_PATHS = build_human_eval_paths(PROJECT_ROOT)
DISTRIBUTION_DIR = HUMAN_EVAL_PATHS.distribution_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build printable QR code sheets for student survey links.")
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=HUMAN_EVAL_PATHS.student_distribution_with_qrcodes,
        help="Distribution sheet with QR code paths.",
    )
    parser.add_argument(
        "--output-html",
        type=Path,
        default=HUMAN_EVAL_PATHS.student_qrcode_print_sheets,
        help="Printable HTML output path.",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=12,
        help="How many QR cards to render per page.",
    )
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            participant_id = (row.get("编号") or "").strip()
            qr_path = (row.get("二维码文件") or "").strip()
            if not participant_id or not qr_path:
                continue
            rows.append(
                {
                    "姓名": (row.get("姓名") or "").strip(),
                    "编号": participant_id,
                    "package": (row.get("package") or "").strip(),
                    "专属链接": (row.get("专属链接") or "").strip(),
                    "二维码文件": qr_path,
                }
            )
        return rows


def relative_qr_path(output_html: Path, qr_path: str) -> str:
    return Path(qr_path).resolve().relative_to(output_html.resolve().parent).as_posix()


def render_card(row: dict[str, str], output_html: Path) -> str:
    name = html.escape(row["姓名"] or "待填写")
    participant_id = html.escape(row["编号"])
    package_id = html.escape(row["package"])
    link = html.escape(row["专属链接"])
    qr_rel = relative_qr_path(output_html, row["二维码文件"])
    return f"""
        <div class="card">
          <div class="card-head">
            <div class="name">姓名：{name}</div>
            <div class="pid">编号：{participant_id}</div>
            <div class="pkg">题包：{package_id}</div>
          </div>
          <div class="qr-wrap">
            <img src="{qr_rel}" alt="{participant_id}" />
          </div>
          <div class="note">扫码后直接进入专属问卷</div>
          <div class="link">{link}</div>
        </div>
    """.strip()


def render_page(page_rows: list[dict[str, str]], page_no: int, output_html: Path) -> str:
    cards = "\n".join(render_card(row, output_html) for row in page_rows)
    return f"""
      <section class="page">
        <header class="page-header">
          <h1>学生问卷二维码发放清单</h1>
          <div class="page-meta">第 {page_no} 页</div>
        </header>
        <div class="grid">
          {cards}
        </div>
      </section>
    """.strip()


def build_html(rows: list[dict[str, str]], output_html: Path, per_page: int) -> str:
    pages = []
    for index in range(0, len(rows), per_page):
        page_rows = rows[index : index + per_page]
        pages.append(render_page(page_rows, len(pages) + 1, output_html))
    pages_html = "\n".join(pages)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>学生问卷二维码发放清单</title>
  <style>
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
      color: #1f2937;
      background: #f5f7fb;
    }}
    .page {{
      width: 210mm;
      min-height: 297mm;
      margin: 0 auto 12mm;
      padding: 12mm;
      background: #ffffff;
      page-break-after: always;
    }}
    .page:last-child {{
      page-break-after: auto;
    }}
    .page-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 8mm;
      border-bottom: 1px solid #dbe3ef;
      padding-bottom: 4mm;
    }}
    .page-header h1 {{
      margin: 0;
      font-size: 20px;
    }}
    .page-meta {{
      font-size: 12px;
      color: #6b7280;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6mm;
    }}
    .card {{
      border: 1px solid #dbe3ef;
      border-radius: 10px;
      padding: 4mm;
      min-height: 66mm;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      background: #fcfdff;
    }}
    .card-head {{
      font-size: 12px;
      line-height: 1.55;
      margin-bottom: 2mm;
    }}
    .qr-wrap {{
      display: flex;
      justify-content: center;
      align-items: center;
      margin: 2mm 0;
    }}
    .qr-wrap img {{
      width: 34mm;
      height: 34mm;
      image-rendering: pixelated;
    }}
    .note {{
      text-align: center;
      font-size: 11px;
      color: #374151;
      margin-bottom: 1mm;
    }}
    .link {{
      font-size: 9px;
      color: #6b7280;
      word-break: break-all;
      line-height: 1.4;
    }}
    @media print {{
      body {{
        background: #ffffff;
      }}
      .page {{
        margin: 0;
        box-shadow: none;
      }}
    }}
  </style>
</head>
<body>
{pages_html}
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    rows = load_rows(args.input_csv)
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    html_text = build_html(rows, args.output_html, args.per_page)
    args.output_html.write_text(html_text, encoding="utf-8")
    print(f"Wrote printable QR sheets -> {args.output_html.resolve()}")
    print(f"Total cards: {len(rows)}")


if __name__ == "__main__":
    main()

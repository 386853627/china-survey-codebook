"""Batch convert CGSS PDFs to Markdown using MarkItDown."""
import re
import os
import sys
from pathlib import Path
from markitdown import MarkItDown

PDF_DIR = Path(__file__).resolve().parent.parent / "data" / "pdf"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "markdown"

# Mapping: (filename_substring, output_name)
# Order matters — earlier matches take priority
NAME_RULES = [
    (r"2003", "CGSS2003.md"),
    (r"2005", "CGSS2005.md"),
    (r"2006", "CGSS2006.md"),
    (r"2008.*A卷", "CGSS2008_A.md"),
    (r"2008.*B卷", "CGSS2008_B.md"),
    (r"2008", "CGSS2008.md"),  # fallback
    (r"2010", "CGSS2010.md"),
    (r"2011", "CGSS2011.md"),
    (r"家庭A.*2012|2012.*家庭A", "CGSS2012_A.md"),
    (r"家庭B.*2012|2012.*家庭B", "CGSS2012_B.md"),
    (r"2012", "CGSS2012.md"),
    (r"2013", "CGSS2013.md"),
    (r"2015", "CGSS2015.md"),
    (r"2017", "CGSS2017.md"),
    (r"2018", "CGSS2018.md"),
    (r"2021", "CGSS2021.md"),
    (r"2023", "CGSS2023.md"),
]


def get_output_name(filename: str) -> str | None:
    for pattern, out_name in NAME_RULES:
        if re.search(pattern, filename):
            return out_name
    return None


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))

    if not pdf_files:
        print("ERROR: No PDF files found in", PDF_DIR)
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDFs. Starting conversion...\n")

    md = MarkItDown()
    success = 0
    failed = []

    for pdf_path in pdf_files:
        out_name = get_output_name(pdf_path.name)
        if not out_name:
            print(f"  SKIP  {pdf_path.name} — cannot determine year")
            failed.append((pdf_path.name, "unknown year"))
            continue

        out_path = OUT_DIR / out_name
        print(f"  CONVERT  {pdf_path.name}  →  {out_name} ...", end=" ", flush=True)

        try:
            result = md.convert(str(pdf_path))
            out_path.write_text(result.text_content, encoding="utf-8")
            size_kb = out_path.stat().st_size / 1024
            print(f"OK ({size_kb:.0f} KB)")
            success += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed.append((pdf_path.name, str(e)))

    print(f"\nDone: {success}/{len(pdf_files)} succeeded.")
    if failed:
        print("Failed:")
        for name, err in failed:
            print(f"  - {name}: {err}")


if __name__ == "__main__":
    main()

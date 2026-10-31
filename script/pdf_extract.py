# -*- coding: utf-8 -*-
"""
把 docs/ 下的操作手册 PDF 抽取成纯文本，供 AI 助手阅读/检索。
用法：& ".venv\\Scripts\\python.exe" script\\pdf_extract.py
输出：docs/extracted/<同名>.txt（UTF-8）
"""
import os
from pypdf import PdfReader

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
OUT_DIR = os.path.join(DOCS_DIR, "extracted")
os.makedirs(OUT_DIR, exist_ok=True)

for fname in os.listdir(DOCS_DIR):
    if not fname.lower().endswith(".pdf"):
        continue
    path = os.path.join(DOCS_DIR, fname)
    reader = PdfReader(path)
    parts = []
    for i, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception as e:  # 个别页面编码怪癖，跳过并留标记
            text = f"[第{i}页抽取失败: {e}]"
        parts.append(f"===== 第 {i} 页 =====\n{text}")
    out = os.path.join(OUT_DIR, os.path.splitext(fname)[0] + ".txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n\n".join(parts))
    total = sum(len(p) for p in parts)
    print(f"{fname}: {len(reader.pages)} 页, 约 {total} 字符 -> {out}")

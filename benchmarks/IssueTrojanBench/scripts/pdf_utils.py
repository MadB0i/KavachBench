"""
IssueTrojanBench - Shared PDF generation utilities.
Generates bug-report-style PDFs with white-on-white hidden payload text.
Uses ReportLab Platypus for structured layout.
"""

import os
import yaml
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import white, black, HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
from reportlab.lib.units import inch


def load_payload(payloads_dir, attack_key, language="english"):
    with open(os.path.join(payloads_dir, f"{attack_key}.yaml"), "r") as f:
        data = yaml.safe_load(f)
    return data[language]


def load_config(config_path):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def build_pdf(output_path, payload_text, position, font_size, legit_elements_fn):
    """
    Build a PDF with hidden payload text embedded at the given position.

    Args:
        output_path: where to save the PDF
        payload_text: the payload string to hide
        position: "top", "middle", or "bottom"
        font_size: "normal" (11pt) or "1pt"
        legit_elements_fn: callable() that returns a list of Platypus flowables
            for the legitimate bug report content
    """
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                            topMargin=0.75*inch, bottomMargin=0.75*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch)

    # Payload style: white text on white background
    fs = 1 if font_size == "1pt" else 11
    payload_style = ParagraphStyle(
        "HiddenPayload",
        fontName="Helvetica",
        fontSize=fs,
        leading=fs + 2,
        textColor=white,
    )

    payload_lines = payload_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    payload_elems = [Paragraph(line, payload_style) for line in payload_lines.split("\n") if line.strip()]

    legit_elems = legit_elements_fn()

    story = []
    if position == "top":
        story.extend(payload_elems)
        story.append(Spacer(1, 12))
        story.extend(legit_elems)
    elif position == "middle":
        mid = len(legit_elems) // 2
        story.extend(legit_elems[:mid])
        story.append(Spacer(1, 6))
        story.extend(payload_elems)
        story.append(Spacer(1, 6))
        story.extend(legit_elems[mid:])
    elif position == "bottom":
        story.extend(legit_elems)
        story.append(Spacer(1, 12))
        story.extend(payload_elems)

    doc.build(story)

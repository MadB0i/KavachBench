"""
IssueTrojanBench - Shared website generation utilities.
Generates bug-report-style HTML pages with white-on-white hidden payload text.
"""

import os
import yaml


def load_payload(payloads_dir, attack_key, language="english"):
    with open(os.path.join(payloads_dir, f"{attack_key}.yaml"), "r") as f:
        data = yaml.safe_load(f)
    return data[language]


def load_config(config_path):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def build_html(payload_text, position, font_size, title, legit_html_body):
    """
    Build an HTML page with hidden payload text.

    Args:
        payload_text: the payload string to hide
        position: "top", "middle", or "bottom"
        font_size: "11pt" (normal) or "1pt"
        title: page <title>
        legit_html_body: the legitimate HTML content string (will be split at
            a <!-- MIDDLE --> marker for middle insertion)
    """
    escaped = (payload_text
               .replace("&", "&amp;")
               .replace("<", "&lt;")
               .replace(">", "&gt;")
               .replace("\n", "<br>\n"))

    hidden_block = f'<div class="hidden">{escaped}</div>'

    if position == "top":
        top_payload = hidden_block
        mid_payload = ""
        bot_payload = ""
    elif position == "middle":
        top_payload = ""
        mid_payload = hidden_block
        bot_payload = ""
    elif position == "bottom":
        top_payload = ""
        mid_payload = ""
        bot_payload = hidden_block
    else:
        top_payload = hidden_block
        mid_payload = ""
        bot_payload = ""

    # Split legit body at marker for middle insertion
    if "<!-- MIDDLE -->" in legit_html_body:
        parts = legit_html_body.split("<!-- MIDDLE -->", 1)
        body_top = parts[0]
        body_bot = parts[1]
    else:
        mid_point = len(legit_html_body) // 2
        cut = legit_html_body.rfind("\n", 0, mid_point)
        if cut == -1:
            cut = mid_point
        body_top = legit_html_body[:cut]
        body_bot = legit_html_body[cut:]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #24292f; line-height: 1.5; }}
        h1 {{ font-size: 24px; border-bottom: 1px solid #d0d7de; padding-bottom: 8px; }}
        h2 {{ font-size: 18px; margin-top: 24px; }}
        pre {{ background: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto; font-size: 13px; }}
        code {{ font-family: "SFMono-Regular", Consolas, monospace; }}
        .hidden {{ color: white; font-size: {font_size}; }}
        ul {{ padding-left: 20px; }}
        li {{ margin-bottom: 4px; }}
    </style>
</head>
<body>
{top_payload}
{body_top}
{mid_payload}
{body_bot}
{bot_payload}
</body>
</html>"""
    return html

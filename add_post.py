#!/usr/bin/env python3
"""
B!tches Be Tripping — Add Blog Post from Google Doc
=====================================================
Reads a Google Doc and inserts it as a new post card at the top of
index.html in the repo folder.

Usage:
    python3 add_blog_post.py <google_doc_id> <author> [--date YYYY-MM-DD] [--categories "Cat1,Cat2"]

Examples:
    python3 add_blog_post.py 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms "Katie"
    python3 add_blog_post.py 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms "Katie" --date 2026-05-23 --categories "Destinations,Must Do"

Requirements:
    pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client

Setup:
    Place credentials.json (downloaded from Google Cloud Console) in the
    same folder as this script.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ─── CONFIG ───────────────────────────────────────────────────────────────────

# Path to your repo folder — update this if needed
REPO_DIR = Path.home() / "Desktop" / "katie-england.github.io"

# OAuth scopes — read-only access to Docs and Drive
SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Where to look for credentials
SCRIPT_DIR   = Path(__file__).parent
CREDS_FILE   = SCRIPT_DIR / "credentials.json"
TOKEN_FILE   = SCRIPT_DIR / "token.json"
INDEX_FILE   = REPO_DIR   / "index.html"

# ─── GOOGLE AUTH ──────────────────────────────────────────────────────────────

def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                print(f"ERROR: credentials.json not found at {CREDS_FILE}")
                print("Download it from Google Cloud Console and place it next to this script.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


# ─── GOOGLE DOC READER ────────────────────────────────────────────────────────

def fetch_doc(doc_id, creds):
    """Fetch the Google Doc and return (title, body_elements)."""
    service = build("docs", "v1", credentials=creds)
    doc = service.documents().get(documentId=doc_id).execute()
    title = doc.get("title", "Untitled")
    body  = doc.get("body", {}).get("content", [])
    return title, body, doc


def parse_doc_to_html(body_elements, doc):
    """
    Convert Google Doc body elements to clean HTML for the post body.
    Handles:
      - Paragraphs with bold, italic, links
      - Bullet lists
      - Headings (H2, H3, H4)
      - Image references: <image: YYYY/MM/filename.ext>
      - Horizontal rules
    """
    html_parts = []
    in_list    = False

    for element in body_elements:
        if "paragraph" not in element:
            # Close any open list
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            # Structural break / table etc — skip for now
            if "sectionBreak" in element or "tableOfContents" in element:
                continue
            continue

        para      = element["paragraph"]
        style     = para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        elements  = para.get("elements", [])

        # Build the raw text and inline HTML for this paragraph
        inline_html = ""
        raw_text    = ""

        for el in elements:
            tr = el.get("textRun", {})
            text = tr.get("content", "")
            if not text or text == "\n":
                continue
            raw_text += text

            ts = tr.get("textStyle", {})
            bold   = ts.get("bold", False)
            italic = ts.get("italic", False)
            link   = ts.get("link", {}).get("url", "")

            # Escape HTML special characters
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            if link:
                text = f'<a href="{link}" target="_blank" rel="noopener">{text}</a>'
            if bold:
                text = f"<strong>{text}</strong>"
            if italic:
                text = f"<em>{text}</em>"

            inline_html += text

        # Skip genuinely empty paragraphs
        if not inline_html.strip():
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        # ── IMAGE REFERENCE ──
        # Matches <image: 2026/05/photo.jpg> anywhere in paragraph
        img_match = re.match(r'\s*&lt;image:\s*([^&]+?)&gt;\s*$', inline_html.strip(), re.IGNORECASE)
        if img_match:
            if in_list:
                html_parts.append("</ul>"); in_list = False
            img_path = img_match.group(1).strip()
            html_parts.append(f'<figure><img src="media/{img_path}" alt=""></figure>')
            continue

        # ── HEADINGS ──
        if style in ("HEADING_2",):
            if in_list: html_parts.append("</ul>"); in_list = False
            html_parts.append(f"<h2>{inline_html.strip()}</h2>")
            continue
        if style in ("HEADING_3",):
            if in_list: html_parts.append("</ul>"); in_list = False
            html_parts.append(f"<h3>{inline_html.strip()}</h3>")
            continue
        if style in ("HEADING_4", "HEADING_5", "HEADING_6"):
            if in_list: html_parts.append("</ul>"); in_list = False
            html_parts.append(f"<h4>{inline_html.strip()}</h4>")
            continue

        # ── BULLET LIST ──
        bullet = para.get("bullet")
        if bullet:
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"  <li>{inline_html.strip()}</li>")
            continue

        # Close list if we've left it
        if in_list:
            html_parts.append("</ul>")
            in_list = False

        # ── HORIZONTAL RULE ──
        # Google Docs doesn't have native HR; support a paragraph that is just "---"
        if raw_text.strip() in ("---", "***", "___"):
            html_parts.append("<hr>")
            continue

        # ── NORMAL PARAGRAPH ──
        html_parts.append(f"<p>{inline_html.strip()}</p>")

    # Close any trailing list
    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


# ─── POST CARD BUILDER ────────────────────────────────────────────────────────

def make_id(title):
    return "post-" + re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')


def build_category_tags(categories):
    if not categories:
        return ""
    tags = "".join(
        f'\n              <span class="category-tag">{c.strip()}</span>'
        for c in categories
    )
    return f'\n            <div class="post-categories">{tags}\n            </div>'


def build_post_card(title, date_str, author, categories, body_html):
    post_id    = make_id(title)
    author_html = f'\n            <span class="post-author">{author}</span>' if author else ""
    cats_html   = build_category_tags(categories)

    # Escape title for HTML
    title_html = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    return f"""
    <!-- POST: {title} -->
    <article class="post-card" id="{post_id}">
      <div class="post-header" onclick="togglePost(this)">
        <div class="post-header-left">
          <div class="post-title">{title_html}</div>
          <div class="post-meta">
            <span class="post-date">{date_str}</span>{author_html}{cats_html}
          </div>
        </div>
        <span class="expand-icon">&#8964;</span>
      </div>
      <div class="post-body">
{body_html}
        <button class="collapse-link" onclick="collapsePost(this)">&#8593; Collapse post</button>
      </div>
    </article>"""


# ─── INDEX.HTML INSERTER ──────────────────────────────────────────────────────

def insert_post(card_html):
    """Insert the new post card at the top of the posts section in index.html."""
    if not INDEX_FILE.exists():
        print(f"ERROR: index.html not found at {INDEX_FILE}")
        sys.exit(1)

    content = INDEX_FILE.read_text(encoding="utf-8")

    # Find the insertion point — right after the affiliate banner div
    marker = '<!-- POST:'
    idx = content.find(marker)
    if idx == -1:
        # Fallback: insert after the affiliate-banner div
        marker = '</div>\n\n'
        idx = content.find('affiliate-banner')
        if idx != -1:
            idx = content.find('</div>', idx) + len('</div>')
        else:
            print("ERROR: Could not find insertion point in index.html.")
            print("Make sure the posts section contains at least one <!-- POST: --> comment.")
            sys.exit(1)

    new_content = content[:idx] + card_html + "\n    " + content[idx:]
    INDEX_FILE.write_text(new_content, encoding="utf-8")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Add a Google Doc as a blog post to index.html")
    parser.add_argument("doc_id",    help="Google Doc ID (from the URL)")
    parser.add_argument("author",    help="Author name, e.g. 'Katie'")
    parser.add_argument("--date",    help="Post date as YYYY-MM-DD (defaults to today)")
    parser.add_argument("--categories", help="Comma-separated categories, e.g. 'Destinations,Must Do'")
    args = parser.parse_args()

    # Resolve date
    if args.date:
        try:
            dt = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print("ERROR: --date must be in YYYY-MM-DD format")
            sys.exit(1)
    else:
        dt = datetime.today()
    date_str = dt.strftime("%B %d, %Y").replace(" 0", " ")

    # Resolve categories
    categories = [c.strip() for c in args.categories.split(",")] if args.categories else []

    print(f"Fetching Google Doc: {args.doc_id}")
    creds = get_credentials()
    title, body_elements, doc = fetch_doc(args.doc_id, creds)
    print(f"  Title:  {title}")
    print(f"  Author: {args.author}")
    print(f"  Date:   {date_str}")
    print(f"  Categories: {categories or 'none'}")

    print("Converting to HTML...")
    body_html = parse_doc_to_html(body_elements, doc)

    print("Building post card...")
    card = build_post_card(title, date_str, args.author, categories, body_html)

    print(f"Inserting into {INDEX_FILE}...")
    insert_post(card)

    print(f"\n\n\nDone! Post added: '{title}'")
    print("\nNext steps:")
    print("  1. Open index.html in a browser to preview")
    print("  2. If it looks good, push to GitHub:")
    print(f"     git add index.html")
    print(f"     (or git add .)")
    print(f'     git commit -m "Added post: {title}"')
    print(f"     git push origin main")


if __name__ == "__main__":
    main()

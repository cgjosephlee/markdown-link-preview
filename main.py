import argparse
import json
import os
from curl_cffi import requests
import markdown
import sys
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# --- Configuration ---
CACHE_FILE = "cache.json"

# GitHub Markdown CSS
GITHUB_CSS_URL = "https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css"

# Custom CSS for Link Preview
PREVIEW_CSS = """
.link-preview-card {
    display: flex;
    flex-direction: column;
    border: 1px solid #e1e4e8;
    border-radius: 8px;
    overflow: hidden;
    margin-top: 15px;
    margin-bottom: 15px;
    text-decoration: none !important;
    background-color: #fff;
    transition: transform 0.2s, box-shadow 0.2s;
    max-width: 500px;
    color: black !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.link-preview-card:hover {
    background-color: #fff;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.link-preview-image {
    width: 100%;
    height: 0;
    padding-bottom: 52.35%; /* 1.91:1 Aspect Ratio (OG standard) */
    background-size: cover;
    background-position: center;
    border-bottom: 1px solid #e1e4e8;
    border-right: none;
}
.link-preview-content {
    padding: 6px 12px;
    display: flex;
    flex-direction: column;
    aspect-ratio: 7.64 / 1;
    overflow: hidden;
    background-color: #fff;
    border-top: 1px solid #e1e4e8;
}
.link-preview-title {
    font-weight: 600;
    font-size: 16px;
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.4;
    color: #24292e;
    flex-shrink: 0; 
}
.link-preview-description {
    font-size: 14px;
    color: #586069;
    margin: 2px 0;
    display: -webkit-box;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
    line-height: 1;
    flex-shrink: 0;
}
.link-preview-domain {
    font-size: 14px;
    color: #6a737d;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    line-height: 1;
    flex-shrink: 0;
}
/* Dark mode support */
@media (prefers-color-scheme: dark) {
    body { background-color: #0d1117; color: #c9d1d9; }
    .markdown-body { color: #c9d1d9; background-color: #0d1117; }
    .link-preview-card {
        background-color: #161b22;
        border-color: #30363d;
        color: #c9d1d9 !important;
    }
    .link-preview-image { border-bottom-color: #30363d; }
    .link-preview-title { color: #c9d1d9; }
    .link-preview-description { color: #8b949e; }
    .link-preview-domain { color: #8b949e; }
}
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="{github_css_url}">
    <style>
        body {{
            box-sizing: border-box;
            min-width: 200px;
            max-width: 980px;
            margin: 0 auto;
            padding: 45px;
        }}
        .markdown-body {{
            box-sizing: border-box;
            min-width: 200px;
            max-width: 980px;
            margin: 0 auto;
            padding: 45px;
        }}
        @media (max-width: 767px) {{
            .markdown-body {{
                padding: 15px;
            }}
        }}
        {custom_css}
    </style>
</head>
<body class="markdown-body">
{content}
</body>
</html>
"""

# --- Caching ---


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4, ensure_ascii=False)


# --- Metadata Fetching ---


def fetch_url_content(url):
    # impersonate="chrome142" simulates a modern Chrome browser to bypass Cloudflare
    # curl_cffi automatically handles TLS/JA3 fingerprints to match the impersonated browser
    try:
        response = requests.get(url, impersonate="chrome142", timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        raise


def fetch_metadata(url, cache):
    if url in cache:
        print(f"Cache hit for: {url}")
        return cache[url]

    print(f"Fetching metadata for: {url}")

    try:
        html_content = fetch_url_content(url)
        soup = BeautifulSoup(html_content, "html.parser")

        def get_meta(property_name):
            tag = soup.find("meta", property=property_name) or soup.find(
                "meta", attrs={"name": property_name}
            )
            return tag["content"] if tag else None

        title = get_meta("og:title") or soup.title.string if soup.title else url
        description = get_meta("og:description") or get_meta("description") or ""
        image = get_meta("og:image")
        domain = urlparse(url).netloc

        data = {
            "title": title,
            "description": description,
            "image": image,
            "domain": domain,
            "url": url,
        }

        cache[url] = data
        return data

    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return {
            "title": url,
            "description": "Could not fetch preview.",
            "image": None,
            "domain": urlparse(url).netloc,
            "url": url,
        }


# --- Preview Generation ---


def generate_preview_html(metadata):
    if not metadata or not metadata.get("title"):
        return ""

    image_html = ""
    if metadata.get("image"):
        image_html = f'<div class="link-preview-image" style="background-image: url(\'{metadata["image"]}\');"></div>'

    html = f"""
    <a href="{metadata["url"]}" class="link-preview-card" target="_blank">
        {image_html}
        <div class="link-preview-content">
            <div class="link-preview-title">{metadata["title"]}</div>
            <div class="link-preview-description">{metadata["description"]}</div>
            <span class="link-preview-domain">{metadata["domain"]}</span>
        </div>
    </a>
    """
    return html


# --- Main Processing ---


def process_markdown(input_path, output_path, line_breaks_as_p=False):
    with open(input_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Treat single newlines as paragraph breaks if requested
    if line_breaks_as_p:
        md_text = re.sub(r"(?<!\n)\n(?!\n)", "\n\n", md_text)

    # Convert Markdown to HTML
    html_content = markdown.markdown(md_text, extensions=["fenced_code", "tables"])
    soup = BeautifulSoup(html_content, "html.parser")

    cache = load_cache()
    cache_updated = False

    # Process paragraphs to find standalone links for preview generation
    for p in soup.find_all("p"):
        text = p.get_text().strip()

        # Check for standalone URLs (simple validation)
        if text.startswith("http") and " " not in text:
            url = text
            print(f"Found candidate bare URL: {url}")

            metadata = fetch_metadata(url, cache)
            cache_updated = True

            preview_html = generate_preview_html(metadata)
            if preview_html:
                preview_soup = BeautifulSoup(preview_html, "html.parser")
                new_tag = preview_soup.find("a", class_="link-preview-card")
                if new_tag:
                    p.replace_with(new_tag)
                else:
                    print(
                        f"WARNING: Could not find link-preview-card in generated HTML for {url}"
                    )
            continue

        # Check for single <a> tags within a paragraph
        a_tag = p.find("a")
        if a_tag:
            has_other_elements = any(
                child.name for child in p.contents if child != a_tag
            )
            p_text = p.get_text().strip()
            a_text = a_tag.get_text().strip()

            # Replace if the paragraph contains only the link
            if not has_other_elements and p_text == a_text:
                url = a_tag["href"]
                print(f"Found candidate anchor Link: {url}")

                metadata = fetch_metadata(url, cache)
                cache_updated = True

                preview_html = generate_preview_html(metadata)
                if preview_html:
                    preview_soup = BeautifulSoup(preview_html, "html.parser")
                    new_tag = preview_soup.find("a", class_="link-preview-card")
                    if new_tag:
                        p.replace_with(new_tag)
                    else:
                        print(
                            f"WARNING: Could not find link-preview-card in generated HTML for {url}"
                        )

    if cache_updated:
        save_cache(cache)

    title = os.path.basename(input_path)
    final_html = HTML_TEMPLATE.format(
        title=title,
        github_css_url=GITHUB_CSS_URL,
        custom_css=PREVIEW_CSS,
        content=str(soup),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_html)

    print(f"Converted {input_path} to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert Markdown to GitHub-styled HTML with Link Previews."
    )
    parser.add_argument("input_file", help="Path to input Markdown file")
    parser.add_argument("-o", "--output", help="Path to output HTML file")
    parser.add_argument(
        "-p",
        "--line-breaks-as-p",
        action="store_true",
        help="Treat single line breaks in the Markdown source as paragraph breaks.",
    )

    args = parser.parse_args()

    input_file = args.input_file
    if args.output:
        output_file = args.output
    else:
        base, _ = os.path.splitext(input_file)
        output_file = base + ".html"

    if not os.path.exists(input_file):
        print(f"Error: File {input_file} not found.")
        sys.exit(1)

    process_markdown(input_file, output_file, line_breaks_as_p=args.line_breaks_as_p)


if __name__ == "__main__":
    main()

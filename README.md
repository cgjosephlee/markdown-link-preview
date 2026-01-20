# Markdown Link Preview Generator

A Python script that converts Markdown files into GitHub-themed HTML pages with **Facebook-style link preview cards**.

## Features

- **Facebook-style Previews**: Automatically detects standalone URLs (e.g. `https://example.com` on its own line) and converts them into rich preview cards with image, title, and description.
- **Persistent Caching**: Link metadata (Open Graph) is cached in `cache.json` to prevent redundant network requests and speed up generation.

## Usage

This project is managed with `uv`.

### 1. Install dependencies
```bash
uv sync
```

### 2. Run the converter
```bash
uv run main.py input.md
```

This will generate `input.html` in the same directory.

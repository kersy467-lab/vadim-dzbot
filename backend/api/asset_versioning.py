import os
import re
import hashlib
from typing import Dict, Tuple, Any
from fastapi.responses import HTMLResponse, FileResponse

# In-memory cache of: full_file_path -> (mtime, hash_string)
_FILE_HASH_CACHE: Dict[str, Tuple[float, str]] = {}


def get_file_content_hash(full_path: str) -> str:
    """Returns a short MD5 hash of the file content, cached by file mtime."""
    if not os.path.isfile(full_path):
        return ""
    try:
        mtime = os.path.getmtime(full_path)
        cached = _FILE_HASH_CACHE.get(full_path)
        if cached and cached[0] == mtime:
            return cached[1]

        with open(full_path, "rb") as f:
            h = hashlib.md5(f.read()).hexdigest()[:10]
        _FILE_HASH_CACHE[full_path] = (mtime, h)
        return h
    except Exception:
        return ""


def inject_asset_versions(html_content: str, frontend_root: str) -> str:
    """Finds all /static/... references to .js and .css files in HTML and ensures
    they have ?v=<content_hash>.

    If the file content changed on disk/git, its hash changes automatically.
    If the file did not change, the hash stays identical and is served from
    cache.
    """

    def _replace_tag(match: re.Match) -> str:
        attr = match.group(1)
        url_path = match.group(2)

        if url_path.startswith("/static/"):
            rel = url_path[len("/static/") :]
        else:
            rel = url_path.lstrip("/\\")

        full_path = os.path.join(frontend_root, rel.replace("/", os.sep))
        h = get_file_content_hash(full_path)
        if h:
            return f'{attr}="{url_path}?v={h}"'
        return match.group(0)

    pattern = r'(src|href)=["\'](/static/[^"?#\s\'<>]+\.(?:js|css))(?:\?[^"\'\s<>]*)?["\']'
    return re.sub(pattern, _replace_tag, html_content)


def serve_page_versioned(
    frontend_root: str,
    filename: str,
    fallback_msg: str,
    no_cache_headers: Dict[str, str],
) -> Any:
    """Serves HTML pages with automatically injected content hashes for static assets.

    HTML pages are served with no-cache headers so users always receive the latest asset hashes.
    Non-HTML files or missing files fall back to standard responses.
    """
    file_path = os.path.join(frontend_root, filename)
    if not os.path.exists(file_path):
        return {"message": fallback_msg}

    if filename.endswith(".html"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            versioned = inject_asset_versions(content, frontend_root)
            return HTMLResponse(content=versioned, headers=no_cache_headers)
        except Exception:
            pass

    return FileResponse(file_path, headers=no_cache_headers)

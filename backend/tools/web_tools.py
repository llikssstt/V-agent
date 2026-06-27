import os
import re
from html import unescape
from urllib.parse import urlparse

import requests

from agent.env_loader import load_env_file


def error(tool, code, message, details=None):
    return {"ok": False, "tool": tool, "error": {"code": code, "message": message, "details": details or {}}}


def web_search(query, max_results=5):
    load_env_file()
    query = str(query or "").strip()
    if not query:
        return error("web_search", "empty_query", "搜索 query 不能为空")

    provider = os.getenv("SEARCH_PROVIDER", "tavily").strip().lower() or "tavily"
    api_key = os.getenv("SEARCH_API_KEY", "").strip()
    if not api_key:
        return error("web_search", "missing_api_key", "未配置 SEARCH_API_KEY")

    try:
        max_results = max(1, min(int(max_results or 5), 10))
    except (TypeError, ValueError):
        max_results = 5

    if provider == "tavily":
        return _search_tavily(query, api_key, max_results)
    if provider == "brave":
        return _search_brave(query, api_key, max_results)
    return error("web_search", "invalid_provider", f"不支持的 SEARCH_PROVIDER: {provider}")


def _search_tavily(query, api_key, max_results):
    base_url = os.getenv("SEARCH_BASE_URL", "https://api.tavily.com/search").strip()
    try:
        response = requests.post(
            base_url,
            json={"api_key": api_key, "query": query, "max_results": max_results, "search_depth": "basic"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        return error("web_search", "request_failed", "Tavily 搜索请求失败", {"detail": str(exc)})
    except ValueError:
        return error("web_search", "invalid_response", "Tavily 返回了非 JSON 响应")

    results = []
    for item in data.get("results", [])[:max_results]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "source": "tavily",
            }
        )
    return {"provider": "tavily", "query": query, "results": results}


def _search_brave(query, api_key, max_results):
    base_url = os.getenv("SEARCH_BASE_URL", "https://api.search.brave.com/res/v1/web/search").strip()
    try:
        response = requests.get(
            base_url,
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            params={"q": query, "count": max_results},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        return error("web_search", "request_failed", "Brave 搜索请求失败", {"detail": str(exc)})
    except ValueError:
        return error("web_search", "invalid_response", "Brave 返回了非 JSON 响应")

    results = []
    for item in (data.get("web") or {}).get("results", [])[:max_results]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
                "source": "brave",
            }
        )
    return {"provider": "brave", "query": query, "results": results}


def web_fetch(url, max_chars=8000):
    url = str(url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return error("web_fetch", "invalid_url", "只允许读取 http/https 网页")
    try:
        max_chars = max(500, min(int(max_chars or 8000), 20000))
    except (TypeError, ValueError):
        max_chars = 8000
    try:
        response = requests.get(url, headers={"User-Agent": "LunaClawAgent/0.1"}, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        return error("web_fetch", "request_failed", "网页读取失败", {"detail": str(exc), "url": url})

    text = _html_to_text(response.text)
    return {"url": url, "title": _extract_title(response.text), "content": text[:max_chars], "truncated": len(text) > max_chars}


def _extract_title(html):
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", unescape(match.group(1))).strip()


def _html_to_text(html):
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()

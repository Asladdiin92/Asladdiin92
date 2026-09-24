#!/usr/bin/env python3
"""Generate repository-owned SVG analytics for the profile README."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from collections import Counter
from html import escape
from pathlib import Path


USERNAME = "Asladdiin92"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "assets"
API_ROOT = "https://api.github.com"


def request_json(url: str, *, payload: dict | None = None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Asladdiin92-profile-analytics",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def get_repositories() -> list[dict]:
    repositories: list[dict] = []
    for page in range(1, 4):
        query = urllib.parse.urlencode(
            {"per_page": 100, "page": page, "type": "owner", "sort": "updated"}
        )
        page_data = request_json(f"{API_ROOT}/users/{USERNAME}/repos?{query}")
        if not page_data:
            break
        repositories.extend(page_data)
        if len(page_data) < 100:
            break
    return repositories


def get_contributions() -> tuple[int, list[int]]:
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    result = request_json(
        "https://api.github.com/graphql",
        payload={"query": query, "variables": {"login": USERNAME}},
    )
    calendar = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [
        sum(day["contributionCount"] for day in week["contributionDays"])
        for week in calendar["weeks"]
    ]
    return calendar["totalContributions"], weeks


def language_totals(repositories: list[dict]) -> Counter[str]:
    totals: Counter[str] = Counter()
    for repository in repositories:
        if repository.get("fork"):
            continue
        languages = request_json(repository["languages_url"])
        for language, byte_count in languages.items():
            totals[language] += byte_count
    return totals


def svg_document(content: str, width: int, height: int) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" rx="12" fill="#1a1b27"/>
  {content}
</svg>
"""


def write_stats(repositories: list[dict], total_contributions: int) -> None:
    stars = sum(repository["stargazers_count"] for repository in repositories)
    forks = sum(repository["forks_count"] for repository in repositories)
    content = f"""
  <text x="32" y="42" fill="#bb9af7" font-family="Arial, sans-serif" font-size="20" font-weight="700">GitHub Overview</text>
  <text x="32" y="88" fill="#7aa2f7" font-family="Arial, sans-serif" font-size="28" font-weight="700">{len(repositories)}</text>
  <text x="32" y="112" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">Public repositories</text>
  <text x="210" y="88" fill="#7dcfff" font-family="Arial, sans-serif" font-size="28" font-weight="700">{total_contributions}</text>
  <text x="210" y="112" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">Contributions this year</text>
  <text x="410" y="88" fill="#9ece6a" font-family="Arial, sans-serif" font-size="28" font-weight="700">{stars}</text>
  <text x="410" y="112" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">Repository stars</text>
  <text x="610" y="88" fill="#f7768e" font-family="Arial, sans-serif" font-size="28" font-weight="700">{forks}</text>
  <text x="610" y="112" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">Repository forks</text>
"""
    (OUTPUT_DIR / "github-stats.svg").write_text(svg_document(content, 800, 145))


def write_languages(totals: Counter[str]) -> None:
    colors = ["#f7df1e", "#3178c6", "#ed8b00", "#6db33f", "#b07219", "#563d7c", "#e34c26", "#8993be"]
    top = totals.most_common(8)
    total = sum(totals.values()) or 1
    bars = []
    for index, (language, count) in enumerate(top):
        y = 48 + index * 32
        percent = count / total * 100
        color = colors[index % len(colors)]
        bars.append(
            f'<rect x="32" y="{y}" width="300" height="14" rx="7" fill="#24283b"/>'
            f'<rect x="32" y="{y}" width="{max(4, 300 * percent / 100):.1f}" height="14" rx="7" fill="{color}"/>'
            f'<text x="350" y="{y + 12}" fill="#c0caf5" font-family="Arial, sans-serif" font-size="13">{escape(language)} {percent:.1f}%</text>'
        )
    content = '<text x="32" y="30" fill="#bb9af7" font-family="Arial, sans-serif" font-size="18" font-weight="700">Top Languages by Repository</text>' + "".join(bars)
    (OUTPUT_DIR / "top-languages.svg").write_text(svg_document(content, 620, 48 + max(1, len(top)) * 32))


def write_contributions(total: int, weeks: list[int]) -> None:
    width, height = 1000, 250
    max_value = max(weeks) if weeks else 1
    points = []
    for index, value in enumerate(weeks):
        x = 32 + index * (936 / max(1, len(weeks) - 1))
        y = 188 - (value / max_value * 115)
        points.append(f"{x:.1f},{y:.1f}")
    polygon = " ".join(points + ["968,188", "32,188"])
    line = " ".join(points)
    content = f"""
  <text x="32" y="34" fill="#bb9af7" font-family="Arial, sans-serif" font-size="18" font-weight="700">Contribution Activity</text>
  <text x="32" y="60" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">{total} contributions in the last year</text>
  <line x1="32" y1="188" x2="968" y2="188" stroke="#414868"/>
  <polygon points="{polygon}" fill="#7aa2f7" opacity="0.28"/>
  <polyline points="{line}" fill="none" stroke="#7dcfff" stroke-width="3"/>
"""
    (OUTPUT_DIR / "contributions.svg").write_text(svg_document(content, width, height))


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    repositories = get_repositories()
    total_contributions, weeks = get_contributions()
    write_stats(repositories, total_contributions)
    write_languages(language_totals(repositories))
    write_contributions(total_contributions, weeks)


if __name__ == "__main__":
    main()

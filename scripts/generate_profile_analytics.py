#!/usr/bin/env python3
"""Generate repository-owned SVG analytics for the profile README."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
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


def get_contributions() -> tuple[int, list[int], list[int], list[tuple[str, int]]]:
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                                date
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
    weeks = []
    days = []
    monthly: Counter[str] = Counter()
    for week in calendar["weeks"]:
        week_days = []
        for day in week["contributionDays"]:
            week_days.append(day["contributionCount"])
            month = datetime.strptime(day["date"], "%Y-%m-%d").strftime("%b")
            monthly[month] += day["contributionCount"]
        weeks.append(sum(week_days))
        days.extend(week_days)
    month_order = [datetime.strptime(day["date"], "%Y-%m-%d").strftime("%b") for week in calendar["weeks"] for day in week["contributionDays"]]
    ordered_months = list(dict.fromkeys(month_order))[-12:]
    return calendar["totalContributions"], weeks, days, [(month, monthly[month]) for month in ordered_months]


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
    metrics = [
        ("Repositories", len(repositories), "#7aa2f7"),
        ("Contributions", total_contributions, "#7dcfff"),
        ("Stars", stars, "#9ece6a"),
        ("Forks", forks, "#f7768e"),
    ]
    scale = max((value for _, value, _ in metrics), default=1) or 1
    bars = []
    for index, (label, value, color) in enumerate(metrics):
        y = 155 + index * 25
        bar_width = max(4, 520 * value / scale) if value else 4
        bars.append(
            f'<text x="32" y="{y + 12}" fill="#c0caf5" font-family="Arial, sans-serif" font-size="12">{label}</text>'
            f'<rect x="135" y="{y}" width="520" height="14" rx="7" fill="#24283b"/>'
            f'<rect x="135" y="{y}" width="{bar_width:.1f}" height="14" rx="7" fill="{color}"/>'
            f'<text x="675" y="{y + 12}" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="12">{value}</text>'
        )
    content = f"""
  <text x="32" y="42" fill="#bb9af7" font-family="Arial, sans-serif" font-size="20" font-weight="700">GitHub Metrics</text>
  <text x="32" y="88" fill="#7aa2f7" font-family="Arial, sans-serif" font-size="28" font-weight="700">{len(repositories)}</text>
  <text x="32" y="112" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">Public repositories</text>
  <text x="210" y="88" fill="#7dcfff" font-family="Arial, sans-serif" font-size="28" font-weight="700">{total_contributions}</text>
  <text x="210" y="112" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">Contributions this year</text>
  <text x="410" y="88" fill="#9ece6a" font-family="Arial, sans-serif" font-size="28" font-weight="700">{stars}</text>
  <text x="410" y="112" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">Repository stars</text>
  <text x="610" y="88" fill="#f7768e" font-family="Arial, sans-serif" font-size="28" font-weight="700">{forks}</text>
  <text x="610" y="112" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">Repository forks</text>
  <text x="32" y="140" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="12">Relative comparison</text>
  {"".join(bars)}
"""
    (OUTPUT_DIR / "github-stats.svg").write_text(svg_document(content, 800, 270))


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
    (OUTPUT_DIR / "top-languages.svg").write_text(svg_document(content, 800, 48 + max(1, len(top)) * 32))


def write_repository_activity(repositories: list[dict]) -> None:
    owned = [repository for repository in repositories if not repository.get("fork")]
    top = sorted(
        owned,
        key=lambda repository: (
            repository["stargazers_count"] + repository["forks_count"],
            repository["stargazers_count"],
        ),
        reverse=True,
    )[:6]
    max_stars = max((repository["stargazers_count"] for repository in top), default=1) or 1
    max_forks = max((repository["forks_count"] for repository in top), default=1) or 1
    rows = []
    for index, repository in enumerate(top):
        y = 62 + index * 38
        name = escape(repository["name"][:28])
        stars = repository["stargazers_count"]
        forks = repository["forks_count"]
        star_width = max(4, 250 * stars / max_stars) if stars else 4
        fork_width = max(4, 250 * forks / max_forks) if forks else 4
        rows.append(
            f'<text x="32" y="{y + 12}" fill="#c0caf5" font-family="Arial, sans-serif" font-size="12">{name}</text>'
            f'<rect x="250" y="{y}" width="250" height="12" rx="6" fill="#24283b"/>'
            f'<rect x="250" y="{y}" width="{star_width:.1f}" height="12" rx="6" fill="#9ece6a"/>'
            f'<text x="510" y="{y + 11}" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="12">{stars} stars</text>'
            f'<rect x="650" y="{y}" width="100" height="12" rx="6" fill="#24283b"/>'
            f'<rect x="650" y="{y}" width="{max(4, 100 * forks / max_forks) if forks else 4:.1f}" height="12" rx="6" fill="#f7768e"/>'
            f'<text x="760" y="{y + 11}" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="12">{forks} forks</text>'
        )
    content = (
        '<text x="32" y="30" fill="#bb9af7" font-family="Arial, sans-serif" font-size="18" font-weight="700">Repository Visibility</text>'
        '<text x="250" y="48" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="11">Stars</text>'
        '<text x="650" y="48" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="11">Forks</text>'
        + "".join(rows)
    )
    height = 70 + max(1, len(top)) * 38
    (OUTPUT_DIR / "repository-activity.svg").write_text(svg_document(content, 850, height))


def write_project_activity(repositories: list[dict]) -> None:
    owned = [repository for repository in repositories if not repository.get("fork")]
    recent = sorted(owned, key=lambda repository: repository.get("pushed_at") or "", reverse=True)[:6]
    rows = []
    for index, repository in enumerate(recent):
        y = 62 + index * 30
        name = escape(repository["name"][:25])
        language = escape(repository.get("language") or "Not specified")
        pushed_at = (repository.get("pushed_at") or "Unknown")[:10]
        issues = repository.get("open_issues_count", 0)
        size = repository.get("size", 0)
        issue_color = "#f7768e" if issues else "#9ece6a"
        rows.append(
            f'<circle cx="38" cy="{y + 7}" r="5" fill="{issue_color}"/>'
            f'<text x="52" y="{y + 11}" fill="#c0caf5" font-family="Arial, sans-serif" font-size="12">{name}</text>'
            f'<text x="270" y="{y + 11}" fill="#7dcfff" font-family="Arial, sans-serif" font-size="12">{pushed_at}</text>'
            f'<text x="390" y="{y + 11}" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="12">{language}</text>'
            f'<text x="560" y="{y + 11}" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="12">{size} KB</text>'
            f'<text x="700" y="{y + 11}" fill="{issue_color}" font-family="Arial, sans-serif" font-size="12">{issues} open issues</text>'
        )
    content = (
        '<text x="32" y="30" fill="#bb9af7" font-family="Arial, sans-serif" font-size="18" font-weight="700">Project Activity</text>'
        '<text x="52" y="48" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="11">Repository</text>'
        '<text x="270" y="48" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="11">Last push</text>'
        '<text x="390" y="48" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="11">Language</text>'
        '<text x="560" y="48" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="11">Size</text>'
        '<text x="700" y="48" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="11">Issues</text>'
        + "".join(rows)
    )
    height = 70 + max(1, len(recent)) * 30
    (OUTPUT_DIR / "project-activity.svg").write_text(svg_document(content, 950, height))


def write_monthly_contributions(monthly: list[tuple[str, int]]) -> None:
    width, height = 900, 180
    max_value = max((value for _, value in monthly), default=1) or 1
    cells = []
    for index, (month, value) in enumerate(monthly):
        x = 48 + index * 68
        intensity = value / max_value
        color = "#24283b" if not value else ("#7dcfff" if intensity > 0.66 else "#477da8" if intensity > 0.33 else "#31556f")
        cells.append(
            f'<text x="{x + 25}" y="78" text-anchor="middle" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="11">{month}</text>'
            f'<rect x="{x}" y="92" width="50" height="50" rx="8" fill="{color}"/>'
            f'<text x="{x + 25}" y="122" text-anchor="middle" fill="#ffffff" font-family="Arial, sans-serif" font-size="13" font-weight="700">{value}</text>'
        )
    content = f"""
  <text x="32" y="32" fill="#bb9af7" font-family="Arial, sans-serif" font-size="18" font-weight="700">Monthly Contribution Heatmap</text>
  <text x="32" y="56" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">Darker cells indicate fewer contributions</text>
  {"".join(cells)}
"""
    (OUTPUT_DIR / "monthly-contributions.svg").write_text(svg_document(content, width, height))


def write_repository_health(repositories: list[dict]) -> None:
    owned = [repository for repository in repositories if not repository.get("fork")]
    metrics = [
        ("Active", sum(not repository.get("archived") and not repository.get("disabled") for repository in owned), "#9ece6a"),
        ("Archived", sum(repository.get("archived", False) for repository in owned), "#bb9af7"),
        ("Open issues", sum(repository.get("open_issues_count", 0) for repository in owned), "#f7768e"),
        ("Forks", sum(repository.get("forks_count", 0) for repository in owned), "#7dcfff"),
    ]
    scale = max((value for _, value, _ in metrics), default=1) or 1
    bars = []
    for index, (label, value, color) in enumerate(metrics):
        y = 58 + index * 30
        bars.append(
            f'<text x="32" y="{y + 12}" fill="#c0caf5" font-family="Arial, sans-serif" font-size="12">{label}</text>'
            f'<rect x="150" y="{y}" width="500" height="14" rx="7" fill="#24283b"/>'
            f'<rect x="150" y="{y}" width="{max(4, 500 * value / scale) if value else 4:.1f}" height="14" rx="7" fill="{color}"/>'
            f'<text x="670" y="{y + 12}" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="12">{value}</text>'
        )
    content = '<text x="32" y="30" fill="#bb9af7" font-family="Arial, sans-serif" font-size="18" font-weight="700">Repository Health</text>' + "".join(bars)
    (OUTPUT_DIR / "repository-health.svg").write_text(svg_document(content, 800, 190))


def write_technology_timeline(repositories: list[dict]) -> None:
    owned = [repository for repository in repositories if not repository.get("fork")]
    timeline: dict[str, Counter[str]] = {}
    for repository in owned:
        pushed_at = repository.get("pushed_at")
        if pushed_at:
            month = pushed_at[:7]
            timeline.setdefault(month, Counter())[repository.get("language") or "Other"] += 1
    months = sorted(timeline)[-8:]
    languages = Counter()
    for month in months:
        languages.update(timeline[month])
    top_languages = [language for language, _ in languages.most_common(4)]
    colors = ["#7aa2f7", "#7dcfff", "#9ece6a", "#bb9af7"]
    lines = []
    max_value = max((timeline[month][language] for month in months for language in top_languages), default=1) or 1
    for language, color in zip(top_languages, colors):
        points = []
        for index, month in enumerate(months):
            x = 80 + index * (700 / max(1, len(months) - 1))
            y = 175 - (timeline[month][language] / max_value * 105)
            points.append(f"{x:.1f},{y:.1f}")
        lines.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="3"/><text x="{80 + len(months) * 0}" y="{52 + len(lines) * 18}" fill="{color}" font-family="Arial, sans-serif" font-size="12">{escape(language)}</text>')
    labels = "".join(
        f'<text x="{80 + index * (700 / max(1, len(months) - 1)):.1f}" y="198" text-anchor="middle" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="11">{month[5:]}</text>'
        for index, month in enumerate(months)
    )
    content = f'<text x="32" y="30" fill="#bb9af7" font-family="Arial, sans-serif" font-size="18" font-weight="700">Technology Activity Over Time</text><text x="32" y="50" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="12">Repository updates grouped by primary language</text><line x1="80" y1="175" x2="780" y2="175" stroke="#414868"/>{"".join(lines)}{labels}'
    (OUTPUT_DIR / "technology-timeline.svg").write_text(svg_document(content, 850, 225))


def write_featured_projects(repositories: list[dict]) -> None:
    owned = [
        repository
        for repository in repositories
        if not repository.get("fork")
        and repository.get("description")
        and repository["name"].lower() != USERNAME.lower()
    ]
    featured = sorted(
        owned,
        key=lambda repository: (repository["stargazers_count"], repository.get("pushed_at") or ""),
        reverse=True,
    )[:3]
    cards = []
    for index, repository in enumerate(featured):
        x = 24 + index * 270
        name = escape(repository["name"][:21] + ("..." if len(repository["name"]) > 21 else ""))
        words = repository["description"].split()
        description_lines = []
        current_line = ""
        for word in words:
            candidate = f"{current_line} {word}".strip()
            if len(candidate) > 34 and current_line:
                description_lines.append(current_line)
                current_line = word
            else:
                current_line = candidate
            if len(description_lines) == 1:
                break
        if current_line and len(description_lines) < 2:
            description_lines.append(current_line)
        description_lines = [escape(line) for line in description_lines[:2]]
        url = escape(repository["html_url"], quote=True)
        description_svg = "".join(
            f'<tspan x="{x + 16}" dy="{index * 16}">{line}</tspan>'
            for index, line in enumerate(description_lines)
        )
        cards.append(f'<a href="{url}"><rect x="{x}" y="52" width="250" height="120" rx="8" fill="#24283b"/><text x="{x + 16}" y="78" fill="#7dcfff" font-family="Arial, sans-serif" font-size="14" font-weight="700">{name}</text><text x="{x + 16}" y="102" fill="#c0caf5" font-family="Arial, sans-serif" font-size="11">{description_svg}</text><text x="{x + 16}" y="154" fill="#9ece6a" font-family="Arial, sans-serif" font-size="11">View project →</text></a>')
    content = '<text x="24" y="30" fill="#bb9af7" font-family="Arial, sans-serif" font-size="18" font-weight="700">Featured Projects</text>' + "".join(cards)
    (OUTPUT_DIR / "featured-projects.svg").write_text(svg_document(content, 850, 190))


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


def streak_metrics(days: list[int]) -> tuple[int, int]:
    longest = 0
    current = 0
    run = 0
    for count in days:
        if count > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    for count in reversed(days):
        if count == 0:
            break
        current += 1
    return current, longest


def write_streak(days: list[int]) -> None:
    current, longest = streak_metrics(days)
    content = f"""
  <text x="32" y="42" fill="#bb9af7" font-family="Arial, sans-serif" font-size="20" font-weight="700">GitHub Streak</text>
  <line x1="200" y1="24" x2="200" y2="122" stroke="#414868"/>
  <line x1="400" y1="24" x2="400" y2="122" stroke="#414868"/>
  <text x="90" y="76" fill="#7aa2f7" font-family="Arial, sans-serif" font-size="30" font-weight="700">{current}</text>
  <text x="48" y="101" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">Current streak</text>
  <text x="286" y="76" fill="#7dcfff" font-family="Arial, sans-serif" font-size="30" font-weight="700">{longest}</text>
  <text x="245" y="101" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">Longest streak</text>
  <text x="500" y="68" fill="#9ece6a" font-family="Arial, sans-serif" font-size="24" font-weight="700">Keep building</text>
  <text x="500" y="96" fill="#a9b1d6" font-family="Arial, sans-serif" font-size="13">Consistent progress matters.</text>
"""
    (OUTPUT_DIR / "streak.svg").write_text(svg_document(content, 800, 145))


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    repositories = get_repositories()
    total_contributions, weeks, days, monthly = get_contributions()
    write_stats(repositories, total_contributions)
    write_languages(language_totals(repositories))
    write_repository_activity(repositories)
    write_project_activity(repositories)
    write_monthly_contributions(monthly)
    write_repository_health(repositories)
    write_technology_timeline(repositories)
    write_featured_projects(repositories)
    write_contributions(total_contributions, weeks)
    write_streak(days)


if __name__ == "__main__":
    main()

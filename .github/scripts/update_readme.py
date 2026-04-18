"""
Auto-updates the profile README with any public repositories not already listed.

Reads the GitHub API to fetch all public repos for the authenticated user,
detects which ones are missing from the manually curated section, and updates
the AUTO-GENERATED-REPOS section.
"""

import os
import re
import sys
import urllib.request
import json

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
USERNAME = os.environ.get("GITHUB_USERNAME", "HassanCodesIt")
README_PATH = os.environ.get("README_PATH", "README.md")

SECTION_START = "<!-- AUTO-GENERATED-REPOS-START -->"
SECTION_END = "<!-- AUTO-GENERATED-REPOS-END -->"

EXCLUDED_REPOS = {USERNAME.lower()}  # skip the profile repo itself


def github_request(url: str, accept: str = "application/vnd.github+json"):
    """Make a single authenticated GET request and return parsed JSON."""
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    req.add_header("Accept", accept)
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "readme-updater")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        link_header = resp.headers.get("Link", "")
    return data, link_header


def github_api(path: str) -> list:
    """Fetch paginated list results from the GitHub REST API."""
    results = []
    url = f"https://api.github.com{path}?per_page=100&page=1"
    while url:
        data, link_header = github_request(url)
        results.extend(data)
        # Follow 'next' pagination link if present
        url = None
        for part in link_header.split(","):
            part = part.strip()
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
                break
    return results


def extract_mentioned_repos(readme: str) -> set:
    """Return the set of lowercase repo names already linked in the README."""
    pattern = rf"https://github\.com/{re.escape(USERNAME)}/([A-Za-z0-9_.\-]+)"
    return {m.lower() for m in re.findall(pattern, readme, re.IGNORECASE)}


def build_table(repos: list) -> str:
    """Build a Markdown table section for the given repo list."""
    if not repos:
        return ""

    lines = [
        "## 🆕 Recently Added Projects\n",
        "<div align=\"center\">\n",
        "\n",
        "| 💻 **Project** | 🚀 **Description** | 🧠 **Tech Stack** |",
        "|----------------|--------------------|--------------------|",
    ]

    for repo in repos:
        name = repo["name"]
        url = repo["html_url"]
        description = (repo.get("description") or "").replace("|", "\\|").strip()
        language = repo.get("language") or ""
        topics = repo.get("topics") or []
        tech = ", ".join([language] + topics[:3]) if language else ", ".join(topics[:4])
        tech = tech.strip(", ")
        lines.append(f"| 🔗 [**{name}**]({url}) | {description} | {tech} |")

    lines += ["\n</div>\n"]
    return "\n".join(lines)


def update_readme(readme: str, new_section_content: str) -> str:
    """Replace the auto-generated section in the README."""
    pattern = re.compile(
        re.escape(SECTION_START) + r".*?" + re.escape(SECTION_END),
        re.DOTALL,
    )
    replacement = f"{SECTION_START}\n{new_section_content}\n{SECTION_END}"
    if pattern.search(readme):
        return pattern.sub(replacement, readme)
    # Markers not found — append before the first "---" separator after projects
    return readme + f"\n{SECTION_START}\n{new_section_content}\n{SECTION_END}\n"


def main():
    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    mentioned = extract_mentioned_repos(readme)

    print(f"Fetching public repos for {USERNAME}...")
    repos = github_api(f"/users/{USERNAME}/repos")
    # Filter: public, non-fork, not excluded, not already mentioned
    new_repos = [
        r for r in repos
        if not r.get("private")
        and not r.get("fork")
        and r["name"].lower() not in mentioned
        and r["name"].lower() not in EXCLUDED_REPOS
    ]

    # Sort newest first
    new_repos.sort(key=lambda r: r.get("created_at", ""), reverse=True)

    print(f"Found {len(new_repos)} new repo(s) not yet in README.")
    for r in new_repos:
        print(f"  + {r['name']}")

    # Fetch topics for each new repo (requires a separate API call with a special Accept header)
    for repo in new_repos:
        try:
            topics_url = f"https://api.github.com/repos/{USERNAME}/{repo['name']}/topics"
            details, _ = github_request(
                topics_url,
                accept="application/vnd.github.mercy-preview+json",
            )
            repo["topics"] = details.get("names", [])
        except Exception as exc:
            print(f"  Warning: could not fetch topics for {repo['name']}: {exc}", file=sys.stderr)
            repo["topics"] = []

    new_section = build_table(new_repos)
    updated_readme = update_readme(readme, new_section)

    if updated_readme == readme:
        print("README is already up to date.")
        return

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(updated_readme)

    print("README updated successfully.")


if __name__ == "__main__":
    main()

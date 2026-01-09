#!/usr/bin/env python3

import argparse
import json
import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse, urlencode
from urllib.request import Request, urlopen

GDELT_BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

PLAY_TITLES = [
    "All's Well That Ends Well",
    "Antony and Cleopatra",
    "As You Like It",
    "The Comedy of Errors",
    "Coriolanus",
    "Cymbeline",
    "Hamlet",
    "Henry IV",
    "Henry V",
    "Henry VI",
    "Henry VIII",
    "Julius Caesar",
    "King Lear",
    "Love's Labour's Lost",
    "Macbeth",
    "Measure for Measure",
    "The Merchant of Venice",
    "The Merry Wives of Windsor",
    "A Midsummer Night's Dream",
    "Much Ado About Nothing",
    "Othello",
    "Pericles",
    "Richard II",
    "Richard III",
    "Romeo and Juliet",
    "The Taming of the Shrew",
    "The Tempest",
    "Timon of Athens",
    "Titus Andronicus",
    "Troilus and Cressida",
    "Twelfth Night",
    "Two Gentlemen of Verona",
    "The Winter's Tale",
]

PRODUCTION_TERMS = [
    "production",
    "theatre",
    "theater",
    "festival",
    "stage",
    "staging",
    "performance",
    "presented",
    "premiere",
]

AUTO_FIELDS = {
    "play",
    "production_title",
    "company",
    "venue",
    "city",
    "country",
    "start_date",
    "end_date",
    "is_tour",
    "image_url",
    "image_urls",
    "sources",
}


class SimpleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title: Optional[str] = None
        self.links: List[str] = []
        self.meta: Dict[str, str] = {}
        self.images: List[str] = []
        self.json_ld_blocks: List[str] = []
        self._current_script_type: Optional[str] = None
        self._current_script: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        attrs_dict = {key.lower(): value for key, value in attrs}
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "a":
            href = attrs_dict.get("href")
            if href:
                self.links.append(href)
        if tag.lower() == "meta":
            prop = attrs_dict.get("property") or attrs_dict.get("name")
            content = attrs_dict.get("content")
            if prop and content:
                self.meta[prop.lower()] = content
        if tag.lower() == "img":
            src = attrs_dict.get("src")
            if src:
                self.images.append(src)
        if tag.lower() == "script":
            self._current_script_type = attrs_dict.get("type")
            self._current_script = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False
        if tag.lower() == "script" and self._current_script_type == "application/ld+json":
            script_content = "".join(self._current_script).strip()
            if script_content:
                self.json_ld_blocks.append(script_content)
            self._current_script_type = None
            self._current_script = []

    def handle_data(self, data: str) -> None:
        if self.in_title:
            text = data.strip()
            if text:
                self.title = text if not self.title else f"{self.title} {text}"
        if self._current_script_type == "application/ld+json":
            self._current_script.append(data)


class ProductionCandidate:
    def __init__(
        self,
        play: str,
        production_title: str,
        company: str,
        venue: str,
        city: str,
        country: str,
        start_date: str,
        end_date: str,
        production_url: str,
        sources: List[str],
        image_urls: List[str],
    ) -> None:
        self.play = play
        self.production_title = production_title
        self.company = company
        self.venue = venue
        self.city = city
        self.country = country
        self.start_date = start_date
        self.end_date = end_date
        self.production_url = production_url
        self.sources = sources
        self.image_urls = image_urls

    def to_entry(self) -> Dict[str, Any]:
        return {
            "id": build_id(self.play, self.company, self.venue, self.production_url),
            "sample": False,
            "play": self.play,
            "production_title": self.production_title,
            "company": self.company,
            "venue": self.venue,
            "city": self.city,
            "country": self.country,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "is_tour": False,
            "themes": [],
            "synopsis": "",
            "image_url": self.image_urls[0] if self.image_urls else None,
            "image_urls": self.image_urls[:2],
            "reviews": [],
            "sources": self.sources,
            "needs_editorial": True,
            "staging_description": "",
        }


def build_id(play: str, company: str, venue: str, production_url: str) -> str:
    base = f"{play} {company} {venue} 2025".strip()
    if base.strip() == "2025":
        base = f"{play} {production_url} 2025".strip()
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return slug


def load_sources(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_json(url: str) -> Optional[Dict[str, Any]]:
    request = Request(url, headers={"User-Agent": "Shakespeare-2025-Updater"})
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read().decode("utf-8")
    except Exception as exc:
        print(f"Failed to fetch JSON {url}: {exc}", file=sys.stderr)
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        print(f"Failed to parse JSON {url}: {exc}", file=sys.stderr)
        return None


def fetch_html(url: str) -> Optional[str]:
    request = Request(url, headers={"User-Agent": "Shakespeare-2025-Updater"})
    try:
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"Failed to fetch HTML {url}: {exc}", file=sys.stderr)
        return None


def parse_html(html: str) -> SimpleHTMLParser:
    parser = SimpleHTMLParser()
    parser.feed(html)
    return parser


def normalize_url(base_url: str, link: str) -> Optional[str]:
    if link.startswith("mailto:") or link.startswith("javascript:"):
        return None
    return urljoin(base_url, link)


def score_link(link: str, preferred_domains: Iterable[str]) -> int:
    score = 0
    if any(domain in link for domain in preferred_domains):
        score += 3
    if any(term in link.lower() for term in ["ticket", "tickets", "production", "event", "show", "season"]):
        score += 2
    if "shakespeare" in link.lower():
        score += 1
    return score


def pick_production_url(base_url: str, links: List[str], preferred_domains: List[str]) -> Optional[str]:
    scored: List[tuple] = []
    for link in links:
        normalized = normalize_url(base_url, link)
        if not normalized:
            continue
        parsed = urlparse(normalized)
        if not parsed.scheme.startswith("http"):
            continue
        scored.append((score_link(normalized, preferred_domains), normalized))
    scored.sort(reverse=True)
    for score, url in scored:
        if score > 0:
            return url
    return None


def parse_json_ld_blocks(blocks: List[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for block in blocks:
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list):
            results.extend(item for item in payload if isinstance(item, dict))
        elif isinstance(payload, dict):
            results.append(payload)
    return results


def parse_event_data(objects: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for obj in objects:
        obj_type = obj.get("@type")
        if isinstance(obj_type, list):
            obj_type = " ".join(obj_type)
        if obj_type and "event" in str(obj_type).lower():
            return obj
    return None


def parse_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    try:
        if len(value) >= 10:
            return datetime.fromisoformat(value[:10]).strftime("%Y-%m-%d")
    except ValueError:
        return None
    return None


def extract_location(event: Dict[str, Any]) -> Dict[str, str]:
    location = event.get("location") or {}
    if isinstance(location, list):
        location = location[0] if location else {}
    name = location.get("name", "") if isinstance(location, dict) else ""
    address = location.get("address", {}) if isinstance(location, dict) else {}
    city = ""
    country = ""
    if isinstance(address, dict):
        city = address.get("addressLocality", "") or address.get("addressRegion", "")
        country = address.get("addressCountry", "")
    return {
        "venue": name or "",
        "city": city or "",
        "country": country or "",
    }


def extract_company(event: Dict[str, Any]) -> str:
    organizer = event.get("organizer") or event.get("performer") or event.get("provider")
    if isinstance(organizer, list):
        organizer = organizer[0] if organizer else {}
    if isinstance(organizer, dict):
        return organizer.get("name", "")
    if isinstance(organizer, str):
        return organizer
    return ""


def extract_images(event: Optional[Dict[str, Any]], parser: SimpleHTMLParser, base_url: str) -> List[str]:
    images: List[str] = []
    if event:
        event_image = event.get("image")
        if isinstance(event_image, list):
            images.extend(event_image)
        elif isinstance(event_image, str):
            images.append(event_image)
    og_image = parser.meta.get("og:image")
    if og_image:
        images.append(og_image)
    for image in parser.images:
        if any(term in image.lower() for term in ["poster", "production", "show", "event", "shakespeare"]):
            images.append(image)
    normalized: List[str] = []
    for image in images:
        resolved = normalize_url(base_url, image)
        if resolved and not resolved.startswith("data:"):
            normalized.append(resolved)
    unique = []
    for image in normalized:
        if image not in unique:
            unique.append(image)
    return unique[:2]


def build_query(play: str) -> str:
    terms = " OR ".join(PRODUCTION_TERMS)
    return f'"{play}" Shakespeare ({terms})'


def build_gdelt_url(play: str, max_records: int) -> str:
    params = {
        "query": build_query(play),
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(max_records),
        "sort": "datedesc",
        "startdatetime": "20250101000000",
        "enddatetime": "20251231235959",
    }
    return f"{GDELT_BASE_URL}?{urlencode(params)}"


def collect_articles(play: str, max_records: int) -> List[Dict[str, Any]]:
    url = build_gdelt_url(play, max_records)
    data = fetch_json(url)
    if not data:
        return []
    return data.get("articles", [])


def extract_candidate_from_page(
    play: str,
    production_url: str,
    article_url: str,
) -> Optional[ProductionCandidate]:
    html = fetch_html(production_url)
    if not html:
        return None
    parser = parse_html(html)
    json_ld_objects = parse_json_ld_blocks(parser.json_ld_blocks)
    event = parse_event_data(json_ld_objects)

    title = parser.meta.get("og:title") or parser.title or play
    start_date = parse_date(event.get("startDate") if event else None)
    end_date = parse_date(event.get("endDate") if event else None)
    if not start_date or not end_date:
        return None

    location = extract_location(event or {})
    company = extract_company(event or {})

    production_title = title
    venue = location.get("venue") or ""
    city = location.get("city") or ""
    country = location.get("country") or ""

    if play.lower() not in production_title.lower():
        production_title = f"{play} ({venue or company or 'Production'})"

    image_urls = extract_images(event, parser, production_url)
    sources = [production_url, article_url]

    return ProductionCandidate(
        play=play,
        production_title=production_title,
        company=company or venue or "Unknown company",
        venue=venue or "Unknown venue",
        city=city or "Unknown city",
        country=country or "Unknown country",
        start_date=start_date,
        end_date=end_date,
        production_url=production_url,
        sources=sources,
        image_urls=image_urls,
    )


def merge_entry(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    for field in AUTO_FIELDS:
        if field in {"sources", "image_urls"}:
            continue
        incoming_value = incoming.get(field)
        if not incoming_value:
            continue
        if not merged.get(field):
            merged[field] = incoming_value
    merged_sources = list(dict.fromkeys(existing.get("sources", []) + incoming.get("sources", [])))
    merged["sources"] = merged_sources

    incoming_images = incoming.get("image_urls", [])
    existing_images = existing.get("image_urls", [])
    merged_images = list(dict.fromkeys(existing_images + incoming_images))[:2]
    if merged_images:
        merged["image_urls"] = merged_images
    if not merged.get("image_url") and incoming.get("image_url"):
        merged["image_url"] = incoming.get("image_url")
    if "needs_editorial" not in merged:
        merged["needs_editorial"] = incoming.get("needs_editorial", True)
    if "staging_description" not in merged:
        merged["staging_description"] = incoming.get("staging_description", "")
    return merged


def update_productions(
    output_path: Path,
    sources_path: Path,
    max_records: int,
    max_articles_per_play: int,
) -> None:
    existing = []
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
    existing_by_id = {entry["id"]: entry for entry in existing}

    sources = load_sources(sources_path)
    preferred_domains = [urlparse(item.get("url", "")).netloc for item in sources]

    new_entries: List[Dict[str, Any]] = []
    seen_production_urls = set()

    for play in PLAY_TITLES:
        articles = collect_articles(play, max_records)[:max_articles_per_play]
        for article in articles:
            article_url = article.get("url")
            if not article_url:
                continue
            article_html = fetch_html(article_url)
            if not article_html:
                continue
            article_parser = parse_html(article_html)
            production_url = pick_production_url(article_url, article_parser.links, preferred_domains)
            if not production_url or production_url in seen_production_urls:
                continue
            seen_production_urls.add(production_url)
            candidate = extract_candidate_from_page(
                play=play,
                production_url=production_url,
                article_url=article_url,
            )
            if not candidate:
                continue
            incoming = candidate.to_entry()
            existing_entry = existing_by_id.get(incoming["id"])
            if existing_entry:
                existing_by_id[incoming["id"]] = merge_entry(existing_entry, incoming)
            else:
                new_entries.append(incoming)

    updated = list(existing_by_id.values()) + new_entries
    updated.sort(key=lambda item: item.get("production_title", ""))
    output_path.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Shakespeare 2025 productions from GDELT.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/data/productions.json"),
        help="Path to productions.json",
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=Path("data/sources.yaml"),
        help="Path to sources.yaml",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=250,
        help="Max records per GDELT query",
    )
    parser.add_argument(
        "--max-articles-per-play",
        type=int,
        default=20,
        help="Max articles to inspect per play",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        update_productions(
            output_path=args.output,
            sources_path=args.sources,
            max_records=args.max_records,
            max_articles_per_play=args.max_articles_per_play,
        )
    except KeyboardInterrupt:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

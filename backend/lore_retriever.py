import json
import os
import logging
from typing import Any

from models import LoreChunk
import config
import i18n

logger = logging.getLogger("neon_scratch.lore_retriever")


def load_lore_files(lore_dir: str) -> dict[str, list[dict]]:
    locale = i18n.locale()
    search_dir = lore_dir
    if locale != "en-US":
        locale_dir = os.path.join(lore_dir, locale)
        if os.path.isdir(locale_dir):
            search_dir = locale_dir
            logger.info("using locale-specific lore from %s", locale_dir)

    lore_data: dict[str, list[dict]] = {}
    files = {
        "classes": "classes.json",
        "enemies": "enemies.json",
        "items": "items.json",
        "locations": "locations.json",
    }
    for key, filename in files.items():
        filepath = os.path.join(search_dir, filename)
        with open(filepath) as f:
            lore_data[key] = json.load(f)
    logger.info("loaded lore files from %s", search_dir)
    return lore_data


def score_keyword_overlap(player_action: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    action_lower = player_action.lower()
    matched = sum(1 for kw in keywords if kw.lower() in action_lower)
    return matched / len(keywords)


def _extract_keywords(entry: dict) -> list[str]:
    tags = []
    name = entry.get("id", entry.get("name", ""))
    if name:
        tags.append(name)
    desc = entry.get("description", "")
    if desc:
        tags.extend(desc.split()[:20])
    weakness = entry.get("weakness", "")
    if weakness:
        tags.append(weakness)
    entry_type = entry.get("type", "")
    if entry_type:
        tags.append(entry_type)
    return list(set(tags))


def retrieve_lore(
    player_action: str,
    lore_data: dict[str, list[dict]],
    current_location: str,
    max_chunks: int = 5,
) -> list[LoreChunk]:
    all_chunks: list[LoreChunk] = []

    for category, entries in lore_data.items():
        for entry in entries:
            keywords = _extract_keywords(entry)
            score = score_keyword_overlap(player_action, keywords)

            content_parts = []
            entry_id = entry.get("id", entry.get("name", ""))
            if entry_id:
                content_parts.append(f"[{category.upper()}] {entry_id}")

            desc = entry.get("description", "")
            if desc:
                content_parts.append(desc)

            if "stats" in entry:
                content_parts.append(f"Stats: {json.dumps(entry['stats'])}")

            special = entry.get("special", entry.get("effect", ""))
            if special:
                content_parts.append(f"Special: {special}")

            weakness = entry.get("weakness", "")
            if weakness:
                content_parts.append(f"Weakness: {weakness}")

            playstyle = entry.get("playstyle", "")
            if playstyle:
                content_parts.append(playstyle)

            content = "\n".join(content_parts)

            lore_location = None
            if entry.get("type") == "location":
                lore_location = entry_id

            lore_entry = LoreChunk(
                content=content,
                score=score,
                location=lore_location,
            )
            all_chunks.append(lore_entry)

    # Guarantee current location is always included
    location_chunks = [c for c in all_chunks if c.location == current_location]
    for lc in location_chunks:
        lc.score = max(lc.score, 0.5)

    sorted_chunks = sorted(all_chunks, key=lambda c: c.score, reverse=True)

    # Get top chunks, excluding current location (already guaranteed)
    result = []
    added_locations = set()
    for c in sorted_chunks:
        if c.location == current_location and c.location:
            if c.location not in added_locations:
                result.append(c)
                added_locations.add(c.location)
        elif len(result) - len(added_locations) < max_chunks:
            result.append(c)

    return result[:max_chunks + len(added_locations)]

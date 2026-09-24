"""Portable AI-news pipeline. Python standard library only."""
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request
from urllib.parse import urlsplit, urlunsplit
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def request(url, payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": "AI-News-Studio/0.1", **({"Content-Type": "application/json"} if data else {}),
        **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def date(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        raise ValueError("Source date has no timezone")
    return parsed.astimezone(timezone.utc)


def parse_feed(raw):
    root = ET.fromstring(raw)
    records = []
    for entry in root.iter():
        if entry.tag.split("}")[-1] not in ("item", "entry"):
            continue
        fields = {}
        for child in entry:
            key = child.tag.split("}")[-1]
            if key == "link":
                if child.attrib.get("rel", "alternate") == "alternate":
                    fields["url"] = child.attrib.get("href") or child.text or ""
            else:
                fields[key] = "".join(child.itertext()).strip()
        records.append({"title": fields.get("title", ""), "url": fields.get("url", "").strip(),
                        "published_at": fields.get("published") or fields.get("pubDate", ""),
                        "summary": (fields.get("summary") or fields.get("description") or "")[:4000]})
    return records


def select(records, now, hours=24):
    seen, selected = set(), []
    for record in records:
        parts = urlsplit(record.get("url", ""))
        if parts.scheme not in ("https", "http") or not parts.netloc or not record.get("title"):
            continue
        url = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))
        try:
            published = date(record.get("published_at", ""))
        except (ValueError, TypeError, OverflowError):
            continue
        if url in seen or not now - timedelta(hours=hours) <= published <= now:
            continue
        seen.add(url)
        selected.append({**record, "url": url, "published_at": published.isoformat(),
                         "id": hashlib.sha256(url.encode()).hexdigest()[:12]})
    return sorted(selected, key=lambda r: r["published_at"], reverse=True)


def new_run(label):
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = ROOT / "runs" / f"{label}-{name}-{uuid.uuid4().hex[:6]}"
    folder.mkdir(parents=True)
    return folder


def generate(records, provider):
    instruction = (ROOT / "prompts" / "editor.txt").read_text(encoding="utf-8")
    if provider == "template":
        sections = ["# AI news draft — editorial review required", "Here are the stories selected for review."]
        for record in records:
            sections.append(f"## {record['title']}\nSource: {record['url']}\n"
                            f"Published: {record['published_at']}\n"
                            "Presenter cue: explain this announcement after checking the original article.\n"
                            f"Discovery excerpt (not verified): {record.get('summary', '')}")
        sections.append("## Before recording\nVerify claims and dates against each original source; replace presenter cues with approved narration.")
        return "\n\n".join(sections)
    model = os.environ.get("AI_MODEL")
    if not model:
        raise ValueError("Set AI_MODEL to a model available in your provider account")
    content = json.dumps(records, ensure_ascii=False)
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is missing")
        result = json.loads(request("https://api.openai.com/v1/responses", {
            "model": model, "instructions": instruction, "input": content,
            "max_output_tokens": 2400, "store": False}, {"Authorization": f"Bearer {key}"}))
        if result.get("status") != "completed":
            raise ValueError("OpenAI response did not complete")
        text = "\n".join(c.get("text", "") for item in result.get("output", [])
                         for c in item.get("content", []) if c.get("type") == "output_text")
    elif provider == "claude":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is missing")
        result = json.loads(request("https://api.anthropic.com/v1/messages", {
            "model": model, "system": instruction, "max_tokens": 2400,
            "messages": [{"role": "user", "content": content}]},
            {"x-api-key": key, "anthropic-version": "2023-06-01"}))
        if result.get("stop_reason") != "end_turn":
            raise ValueError("Claude response did not finish normally")
        text = "\n".join(c["text"] for c in result.get("content", []) if c.get("type") == "text")
    else:
        raise ValueError("AI_PROVIDER must be template, openai, or claude")
    if not text.strip():
        raise ValueError("Provider returned an empty draft")
    return text


def draft(records, folder, provider="template", demo=False):
    if not records:
        raise ValueError("No eligible stories; nothing to draft")
    write_json(folder / "sources.json", records)
    script = generate(records, provider)
    if demo:
        script = "DEMO ONLY — FICTIONAL SOURCE DATA, NOT NEWS\n\n" + script
    (folder / "script.md").write_text(script, encoding="utf-8")
    write_json(folder / "production.json", {
        "status": "awaiting_editorial_review", "demo": demo, "provider": provider,
        "narration": "pending", "presenter": "pending", "b_roll": "pending",
        "assembly": "pending", "story_ids": [r["id"] for r in records]})
    write_json(folder / "youtube-draft.json", {
        "title": ("DEMO — " if demo else "DRAFT — ") + "AI news briefing",
        "description": "Sources:\n" + "\n".join(r["url"] for r in records),
        "privacyStatus": "private", "upload_status": "not_implemented"})


def validate_graph(graph):
    if not isinstance(graph, dict) or not graph or "nodes" in graph:
        raise ValueError("Expected a ComfyUI API-format node dictionary")
    if any(not isinstance(n, dict) or not isinstance(n.get("class_type"), str)
           or not isinstance(n.get("inputs"), dict) for n in graph.values()):
        raise ValueError("Each workflow node needs class_type and inputs")
    return graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("demo")
    commands.add_parser("research")
    p = commands.add_parser("draft")
    p.add_argument("--sources", type=Path, required=True)
    p = commands.add_parser("comfy-submit")
    p.add_argument("--workflow", type=Path, required=True)
    p = commands.add_parser("comfy-status")
    p.add_argument("--prompt-id", required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.command == "demo":
        records = select([{"title": "Fictional laboratory announces a demo model", "url": "https://example.com/demo",
                           "published_at": now.isoformat(), "summary": "Synthetic fixture used to test the pipeline."}], now)
        folder = new_run("demo")
        draft(records, folder, demo=True)
    elif args.command == "research":
        folder = new_run("research")
        records, errors = [], []
        for url in json.loads((ROOT / "config" / "feeds.json").read_text(encoding="utf-8")):
            try:
                records.extend({**r, "feed_url": url, "retrieved_at": now.isoformat()} for r in parse_feed(request(url)))
            except Exception as error:
                errors.append({"feed": url, "error_type": type(error).__name__})
        selected = select(records, now)
        write_json(folder / "sources.json", selected)
        write_json(folder / "feed-errors.json", errors)
        if not selected:
            raise ValueError(f"No recent dated stories found; inspect {folder}")
    elif args.command == "draft":
        records = json.loads(args.sources.read_text(encoding="utf-8"))
        records = select(records, now)[:5]
        folder = new_run("draft")
        draft(records, folder, os.environ.get("AI_PROVIDER", "template"))
    else:
        base = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
        folder = new_run(args.command)
        if args.command == "comfy-submit":
            graph = validate_graph(json.loads(args.workflow.read_text(encoding="utf-8")))
            result = json.loads(request(base + "/prompt", {"prompt": graph, "client_id": str(uuid.uuid4())}))
            write_json(folder / "submission.json", result)
            if not result.get("prompt_id") or result.get("node_errors"):
                raise ValueError("ComfyUI rejected workflow; inspect submission.json")
        else:
            prompt_id = str(uuid.UUID(args.prompt_id))
            result = json.loads(request(base + "/history/" + prompt_id))
            write_json(folder / "history.json", result)
            print("Job history saved" if result else "No history yet; job may be queued, running or unknown")
    print(folder)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Avoid dumping HTTP bodies/headers that could include credentials.
        print(f"Error: {error}" if isinstance(error, ValueError) else f"Error: {type(error).__name__}", file=sys.stderr)
        sys.exit(1)

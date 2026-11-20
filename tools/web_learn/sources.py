"""Where the web-learning pipeline looks for PSL sign videos (master-v3 Stage 1, step 2).

In order of preference:
1. Licensed datasets already in the ledger: the SLT PSL dictionary (pk-hfad-1, CC BY 4.0), covered by
   the ledger entry `psl-slt-dictionary`.
2. Official Deaf organisations: only with written permission (docs/permission_requests.md) - no adapter
   until permission exists; nothing is scraped.
3. Open-licence platforms through their official APIs: Wikimedia Commons, Internet Archive, and YouTube
   (Data API v3, videoLicense=creativeCommon). YouTube's terms forbid downloading outside YouTube's own
   features, so YouTube results are listed for embedding or a permission request, never downloaded.

Every adapter only reads public metadata through documented APIs, identifies itself with a User-Agent,
waits between requests and gives up on errors (no retries that could hammer a site).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable

from tools.web_learn import licences
from tools.web_learn.words import Word, queries

USER_AGENT = "SignBridge-web-learn/1.0 (https://github.com/shaafrajput06-tech/SignBridge; student project, PSL research)"
PAUSE_SECONDS = 1.0

Fetcher = Callable[[str], bytes]


def http_get(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (fixed https APIs)
        return response.read()


def get_json(url: str, fetch: Fetcher = http_get) -> object:
    time.sleep(PAUSE_SECONDS if fetch is http_get else 0)
    return json.loads(fetch(url).decode("utf-8"))


# A clip counts as a sign-language video only if its own text says so; "PSL" alone is not enough (it is
# also the name of political parties), and Urdu script alone is not enough (Persian uses it too).
SIGN_LANGUAGE_VIDEO = r"sign language|signing|\bsigned\b|\bsign(s)? for\b|\bdeaf\b|اشاروں|اشارتی|زبان اشاره"
SIGN_LANGUAGE_HINTS = (
    ("PSL", r"pakistan(i)? sign language|\bpsl sign|\bpsl\b.{0,30}\bsign language|اشاروں کی زبان|پاکستانی اشار"),
    ("ASL", r"american sign language|\basl\b"),
    ("BSL", r"british sign language|\bbsl\b"),
    ("ISL", r"indian sign language|irish sign language|\bisl\b"),
    ("other", r"spanish sign|french sign|german sign|japanese sign|korean sign|chinese sign|arabic sign|persian sign|"
              r"auslan|\blsf\b|\blse\b|libras|\bdgs\b|\bjsl\b|زبان اشاره"),
)


def is_sign_language_video(*texts: str) -> bool:
    return bool(re.search(SIGN_LANGUAGE_VIDEO, " ".join(t for t in texts if t).lower()))


def language_hint(*texts: str) -> str:
    """The sign language a clip's own title or description names; 'unknown' if none or several."""
    joined = " ".join(t for t in texts if t).lower()
    found = {name for name, pattern in SIGN_LANGUAGE_HINTS if re.search(pattern, joined)}
    if len(found) == 1:
        return found.pop()
    return "mixed" if found else "unknown"


def mentions(word: Word, *texts: str) -> bool:
    """True when the clip's own text names the word (English, a synonym, Urdu or Roman Urdu)."""
    joined = " ".join(t for t in texts if t).lower()
    for term in [word.english, *word.synonyms, word.roman_urdu]:
        if term and re.search(rf"(?<![a-z]){re.escape(term.lower())}(?![a-z])", joined):
            return True
    return bool(word.urdu and word.urdu in joined)


@dataclass
class Candidate:
    source: str                 # slt | commons | archive | youtube
    source_id: str              # stable id on that platform
    page_url: str
    media_url: str | None       # direct file URL, or None when the platform must not be downloaded from
    title: str
    uploader: str
    licence_raw: str
    licence_id: str
    gloss: str                  # proposed SignBridge gloss (from the dictionary label or the search word)
    label_evidence: str         # why: "dictionary label", or the title text that names the word
    language: str               # PSL | ASL | BSL | ISL | other | mixed | unknown (from the clip's own text)
    query: str = ""
    size_bytes: int | None = None
    found_on: str = field(default_factory=lambda: dt.date.today().isoformat())
    ledger_id: str = ""         # filled by tools.web_learn.ledger

    @property
    def download_allowed(self) -> bool:
        return bool(self.media_url) and licences.trainable(self.licence_id) and self.source != "youtube"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["download_allowed"] = self.download_allowed
        return data

    @staticmethod
    def from_dict(data: dict) -> "Candidate":
        data = {k: v for k, v in data.items() if k != "download_allowed"}
        return Candidate(**data)


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


# --------------------------------------------------------------------------- 1. SLT dictionary

SLT_REPO = "sign-language-translator/sign-language-datasets"
SLT_LEDGER_ID = "psl-slt-dictionary"
SLT_CLIP = re.compile(r"^pk-hfad-1_(?P<label>.+)\.mp4$")


def slt_clips(fetch: Fetcher = http_get) -> list[dict]:
    """Every pk-hfad-1 dictionary clip published as a release asset: {label, url, size}."""
    releases = get_json(f"https://api.github.com/repos/{SLT_REPO}/releases?per_page=100", fetch)
    clips: dict[str, dict] = {}
    for release in releases if isinstance(releases, list) else []:
        for asset in release.get("assets", []):
            match = SLT_CLIP.match(asset.get("name", ""))
            if match and match.group("label") not in clips:
                clips[match.group("label")] = {"label": match.group("label"), "url": asset["browser_download_url"],
                                               "size": asset.get("size"), "release": release.get("tag_name", "")}
    return sorted(clips.values(), key=lambda c: c["label"])


SLT_MAPPING_URL = f"https://raw.githubusercontent.com/{SLT_REPO}/main/parallel_texts/pk-dictionary-mapping.json"


def _plain(text: str) -> str:
    """Lower-case, without punctuation such as ? ؟ ! . , so 'What?' and 'what' match."""
    return re.sub(r"[\s?؟!.,،۔'\"]+", " ", (text or "").lower()).strip()


def mapping_pairs(mapping: object, labels: set[str]) -> list[tuple[str, str]]:
    """(word, clip label) pairs from the dictionary's own mapping file, whatever its nesting.

    Any string next to a known clip label (as key and value, or a list of values) is taken as a word
    for that label; labels may carry the 'pk-hfad-1_' prefix.
    """
    pairs: list[tuple[str, str]] = []

    def label_of(text: str) -> str | None:
        text = text.strip()
        text = text[len("pk-hfad-1_"):] if text.startswith("pk-hfad-1_") else text
        return text if text in labels else None

    def consider(a: str, b: str) -> None:
        if label_of(b) and not label_of(a):
            pairs.append((a, label_of(b)))
        elif label_of(a) and not label_of(b):
            pairs.append((b, label_of(a)))

    schema_words = {"label", "labels", "word", "words", "text", "texts", "token", "tokens", "id", "name", "file", "path",
                    "urdu", "english", "value", "key", "sign", "signs", "gloss", "language", "lang"}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            strings = {k: v for k, v in node.items() if isinstance(v, str)}
            found = [v for v in strings.values() if label_of(v)]
            for label in found:            # {"word": "hello", "label": "pk-hfad-1_hello"}: siblings pair up
                for other in strings.values():
                    if not label_of(other):
                        consider(other, label)
            for key, value in node.items():
                if str(key).strip().lower() in schema_words:
                    walk(value)
                    continue
                if isinstance(value, str):
                    consider(str(key), value)
                elif isinstance(value, list) and all(isinstance(v, str) for v in value):
                    for v in value:
                        consider(str(key), v)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(mapping)
    return sorted(set(pairs))


def vocabulary_labels(words: list[Word], pairs: list[tuple[str, str]], labels: set[str]) -> dict[str, tuple[str, str]]:
    """clip label -> (vocabulary gloss, evidence). Matches the dictionary's own mapping on a word's
    Urdu or English text, then exact English = label; never a guessed synonym (CLAUDE.md 9.5)."""
    out: dict[str, tuple[str, str]] = {}
    texts = {}
    for word in words:
        if word.in_vocabulary:
            for text in (word.urdu, word.english, word.roman_urdu):
                if text:
                    texts.setdefault(_plain(text), word)
    for token, label in pairs:
        word = texts.get(_plain(token))
        if word and label not in out:
            out[label] = (word.gloss, f"dictionary mapping file: {token!r} -> {label}")
    for label in labels:
        head = _plain(label.split(".")[0].replace("_", " "))
        word = texts.get(head)
        if word and label not in out:
            out[label] = (word.gloss, f"dictionary label {label!r} equals the word {word.english!r}")
    return out


def slt_candidates(words: list[Word], clips: list[dict], mapped: dict[str, tuple[str, str]] | None = None) -> list[Candidate]:
    if mapped is None:
        mapped = vocabulary_labels(words, [], {c["label"] for c in clips})
    out = []
    for clip in clips:
        label = clip["label"]
        gloss, evidence = mapped.get(label, (f"slt:{label}", f"dictionary label '{label}'"))
        out.append(Candidate(source="slt", source_id=f"pk-hfad-1_{label}", page_url=f"https://github.com/{SLT_REPO}",
                             media_url=clip["url"], title=f"pk-hfad-1 {label}", uploader="Mudassar Iqbal (Sign Language Datasets)",
                             licence_raw="CC BY 4.0 (repository LICENSE)", licence_id="CC-BY-4.0", gloss=gloss,
                             label_evidence=evidence, language="PSL", size_bytes=clip.get("size"),
                             ledger_id=SLT_LEDGER_ID))
    return out


# --------------------------------------------------------------------------- 3a. Wikimedia Commons

COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def commons_search(word: Word, fetch: Fetcher = http_get, per_query: int = 10) -> list[Candidate]:
    found: dict[str, Candidate] = {}
    for query in queries(word)[:4]:
        params = {"action": "query", "format": "json", "list": "search", "srnamespace": "6", "srlimit": str(per_query),
                  "srsearch": f"{query} filetype:video"}
        hits = get_json(f"{COMMONS_API}?{urllib.parse.urlencode(params)}", fetch).get("query", {}).get("search", [])
        titles = [h["title"] for h in hits if h["title"] not in found]
        if not titles:
            continue
        info_params = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
                       "titles": "|".join(titles[:20])}
        pages = get_json(f"{COMMONS_API}?{urllib.parse.urlencode(info_params)}", fetch).get("query", {}).get("pages", {})
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            if not str(info.get("mime", "")).startswith("video/"):
                continue
            title = page.get("title", "")
            description = _strip_html(meta.get("ImageDescription", {}).get("value", ""))
            if not is_sign_language_video(title, description):
                continue
            licence_raw = meta.get("LicenseUrl", {}).get("value") or meta.get("LicenseShortName", {}).get("value", "")
            found[title] = Candidate(
                source="commons", source_id=title, page_url=info.get("descriptionurl", ""), media_url=info.get("url"),
                title=title, uploader=_strip_html(meta.get("Artist", {}).get("value", "")) or "unknown",
                licence_raw=licence_raw, licence_id=licences.normalise(licence_raw), gloss=word.gloss,
                label_evidence=title if mentions(word, title, description) else "",
                language=language_hint(title, description), query=query, size_bytes=info.get("size"))
    return list(found.values())


# --------------------------------------------------------------------------- 3b. Internet Archive

ARCHIVE_SEARCH = "https://archive.org/advancedsearch.php"
VIDEO_FORMATS = ("mpeg4", "h.264", "512kb mpeg4", "webm", "matroska")


def archive_search(word: Word, fetch: Fetcher = http_get, rows: int = 10) -> list[Candidate]:
    found: dict[str, Candidate] = {}
    for query in queries(word)[:3]:
        q = f'({query}) AND mediatype:(movies) AND licenseurl:(*creativecommons* OR *publicdomain*)'
        params = [("q", q), ("rows", str(rows)), ("output", "json"), ("fl[]", "identifier"), ("fl[]", "title"),
                  ("fl[]", "licenseurl"), ("fl[]", "creator"), ("fl[]", "description")]
        docs = get_json(f"{ARCHIVE_SEARCH}?{urllib.parse.urlencode(params)}", fetch).get("response", {}).get("docs", [])
        for doc in docs:
            identifier = doc.get("identifier")
            if not identifier or identifier in found:
                continue
            title = doc.get("title") if isinstance(doc.get("title"), str) else " ".join(doc.get("title") or [])
            description = doc.get("description") if isinstance(doc.get("description"), str) else " ".join(doc.get("description") or [])
            if not is_sign_language_video(title or "", _strip_html(description)):
                continue
            metadata = get_json(f"https://archive.org/metadata/{urllib.parse.quote(identifier)}", fetch)
            files = [f for f in metadata.get("files", []) if str(f.get("format", "")).lower() in VIDEO_FORMATS]
            media = min(files, key=lambda f: int(f.get("size") or 1 << 40)) if files else None
            licence_raw = doc.get("licenseurl") or metadata.get("metadata", {}).get("licenseurl", "")
            creator = doc.get("creator") if isinstance(doc.get("creator"), str) else ", ".join(doc.get("creator") or [])
            found[identifier] = Candidate(
                source="archive", source_id=identifier, page_url=f"https://archive.org/details/{identifier}",
                media_url=f"https://archive.org/download/{identifier}/{urllib.parse.quote(media['name'])}" if media else None,
                title=title or identifier, uploader=creator or "unknown", licence_raw=licence_raw,
                licence_id=licences.normalise(licence_raw), gloss=word.gloss,
                label_evidence=title if mentions(word, title, description) else "",
                language=language_hint(title, _strip_html(description)), query=query,
                size_bytes=int(media["size"]) if media and media.get("size") else None)
    return list(found.values())


# --------------------------------------------------------------------------- 3c. YouTube (metadata only)

YOUTUBE_SEARCH = "https://www.googleapis.com/youtube/v3/search"


def youtube_search(word: Word, api_key: str, fetch: Fetcher = http_get, per_query: int = 10) -> list[Candidate]:
    """Creative-Commons YouTube videos for a word. Never downloaded (YouTube's terms); listed only."""
    found: dict[str, Candidate] = {}
    for query in queries(word)[:2]:
        params = {"part": "snippet", "type": "video", "videoLicense": "creativeCommon", "maxResults": str(per_query),
                  "q": query, "key": api_key}
        for item in get_json(f"{YOUTUBE_SEARCH}?{urllib.parse.urlencode(params)}", fetch).get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if not video_id or video_id in found:
                continue
            snippet = item.get("snippet", {})
            title, description = snippet.get("title", ""), snippet.get("description", "")
            if not is_sign_language_video(title, description):
                continue
            found[video_id] = Candidate(
                source="youtube", source_id=video_id, page_url=f"https://www.youtube.com/watch?v={video_id}", media_url=None,
                title=html.unescape(title), uploader=snippet.get("channelTitle", "unknown"),
                licence_raw="YouTube Creative Commons (CC BY)", licence_id=licences.normalise("creative commons", "youtube"),
                gloss=word.gloss, label_evidence=title if mentions(word, title, description) else "",
                language=language_hint(title, description), query=query)
    return list(found.values())


def candidate_key(candidate: Candidate) -> str:
    return hashlib.sha1(f"{candidate.source}:{candidate.source_id}".encode("utf-8")).hexdigest()[:10]


def search_all(words: Iterable[Word], fetch: Fetcher = http_get, youtube_key: str | None = None,
               sources: Iterable[str] = ("commons", "archive", "youtube"), log: Callable[[str], None] = print) -> tuple[list[Candidate], list[str]]:
    """Run the web searches for every word. Returns (candidates, problems)."""
    candidates: dict[tuple[str, str], Candidate] = {}
    problems: list[str] = []
    for word in words:
        for name in sources:
            if name == "youtube" and not youtube_key:
                continue
            try:
                if name == "commons":
                    found = commons_search(word, fetch)
                elif name == "archive":
                    found = archive_search(word, fetch)
                elif name == "youtube":
                    found = youtube_search(word, youtube_key, fetch)
                else:
                    continue
            except Exception as error:  # noqa: BLE001 (one failing site must not stop the run)
                problems.append(f"{name} / {word.gloss}: {str(error)[:160]}")
                continue
            for candidate in found:
                candidates.setdefault((candidate.source, candidate.source_id), candidate)
        log(f"searched {word.gloss}: {len(candidates)} candidates so far")
    return list(candidates.values()), problems

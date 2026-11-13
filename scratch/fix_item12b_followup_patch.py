#!/usr/bin/env python3
"""Item 12B follow-up fix: escape bare '&' in the registry mock's XML.

The SEC EDGAR registry URL contains bare '&' characters; embedding it raw
in mock RSS text makes ET.fromstring fail, so that source yields zero events
and the 16-event assertion fails (15 == 16). One replacement, verified
exactly once before writing (same two-phase apply as the main patch)."""
import os
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = [(
    "tests/test_forum_collector.py",
    """    mock_resp.status_code = 200
    mock_resp.text = (
        "<rss><channel><item>"
        f"<title>Item from {url}</title><link>{url}/item1</link>"
        "<description>desc</description></item></channel></rss>"
    )
    mock_resp.json.side_effect = ValueError("not json")
    return mock_resp""",
    """    mock_resp.status_code = 200
    # The SEC EDGAR URL contains bare "&" characters, which are illegal in
    # XML text; escape them or ET.fromstring fails and that source yields
    # zero events.
    safe_url = url.replace("&", "&amp;")
    mock_resp.text = (
        "<rss><channel><item>"
        f"<title>Item from {safe_url}</title><link>{safe_url}/item1</link>"
        "<description>desc</description></item></channel></rss>"
    )
    mock_resp.json.side_effect = ValueError("not json")
    return mock_resp""",
)]


def main():
    contents = {}
    for path, old, new in REPLACEMENTS:
        if path not in contents:
            with open(path, "r", encoding="utf-8", newline="") as f:
                contents[path] = f.read()
        n = contents[path].count(old)
        if n != 1:
            print(f"FAIL {path}: expected 1 occurrence, found {n}")
            sys.exit(1)
    for path, old, new in REPLACEMENTS:
        contents[path] = contents[path].replace(old, new)
        print(f"OK {path}")
    for path, content in contents.items():
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    print(f"Applied {len(REPLACEMENTS)} replacements.")


if __name__ == "__main__":
    main()

from scripts.news_projection import canonical_url, project


def test_canonical_url_removes_tracking_and_fragment():
    assert (
        canonical_url("HTTPS://Example.com/a/?utm_source=x&b=2#frag") == "https://example.com/a?b=2"
    )


def test_projection_dedupes_and_prefers_richer_record():
    rows = [
        {
            "url": "https://example.com/a?utm_source=x",
            "title": "Fed decision",
            "text": "short",
            "published_at": "2026-07-13T08:00:00Z",
        },
        {
            "url": "https://example.com/a",
            "title": "Fed decision",
            "summary": "official release",
            "official": True,
            "published_at": "2026-07-13T09:00:00Z",
        },
    ]
    result = project(rows, ["Fed"], 8)
    assert len(result) == 1
    assert result[0]["primary_source"] is True
    assert result[0]["keyword_hits"] == ["Fed"]


def test_projection_is_bounded_and_ranked():
    rows = [
        {"url": f"https://example.com/{index}", "title": f"item {index}"} for index in range(10)
    ]
    result = project(rows, [], 3)
    assert len(result) == 3
    assert all("_time" not in item for item in result)

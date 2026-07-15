from scout.search import build_queries, search_offers


def test_build_queries_one_per_role():
    assert build_queries(["SDET", "AI Engineer"]) == [
        '"SDET" remote job apply',
        '"AI Engineer" remote job apply',
    ]


def test_dedup_and_ad_filtering():
    def fn(query, max_results):
        return [
            {"title": "A", "href": "https://a.io/1", "body": "x"},
            {"title": "A dup", "href": "https://a.io/1", "body": "x"},
            {"title": "Ad", "href": "https://www.bing.com/aclick?ld=zzz", "body": "ad"},
            {"title": "", "href": "", "body": ""},
        ]
    results, queries = search_offers(["SDET"], search_fn=fn, sleep=lambda s: None)
    assert queries == 1
    assert [r["url"] for r in results] == ["https://a.io/1"]


def test_failed_query_is_skipped():
    calls = []
    def fn(query, max_results):
        calls.append(query)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return [{"title": "B", "href": "https://b.io/1", "body": "y"}]
    results, queries = search_offers(["QA", "SDET"], search_fn=fn, sleep=lambda s: None)
    assert queries == 2
    assert [r["url"] for r in results] == ["https://b.io/1"]


def test_pause_between_queries():
    delays = []
    def fn(query, max_results):
        return []
    search_offers(["A", "B", "C"], search_fn=fn, pause=2.0, sleep=delays.append)
    assert delays == [2.0, 2.0]  # brak pauzy po ostatnim zapytaniu

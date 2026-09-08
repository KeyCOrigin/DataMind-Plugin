from datamind_dataplane.rag import exact_uid_results, normalize_results


def _chunk(uid: str, score: float, source: str | None = None) -> dict:
    return {
        "id": f"{uid}-{score}",
        "text": f"来源：UID-{uid}.eml\n正文内容 {uid}",
        "source": source or f"notes/UID-{uid}.eml.md",
        "score": score,
    }


def test_results_are_deduplicated_by_mail_uid():
    results = normalize_results([_chunk("408", .7), _chunk("408", .6), _chunk("409", .8)], "文件中转站", 5)
    assert [item["source"] for item in results] == ["notes/UID-409.eml.md", "notes/UID-408.eml.md"]


def test_exact_uid_query_filters_semantic_neighbors():
    results = normalize_results([_chunk("387", .9), _chunk("385", .2), _chunk("385", .1)], "QQ 邮件 UID-385", 10)
    assert len(results) == 1
    assert "385" in results[0]["source"]


def test_exact_uid_lookup_does_not_depend_on_vector_rank():
    results = exact_uid_results([
        ("a", "来源：UID-385.eml\nGitHub 2FA", {"source": "notes/UID-385.eml.md"}),
        ("b", "来源：UID-408.eml\n文件中转站", {"source": "notes/UID-408.eml.md"}),
    ], {"385"})
    assert len(results) == 1
    assert results[0]["source"] == "notes/UID-385.eml.md"

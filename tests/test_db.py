from zero.db import ProgramDB


def test_insert_and_top_k(tmp_path):
    db = ProgramDB(tmp_path / "p.sqlite")
    db.start_run("sortnet8", 0, {"foo": 1})
    for i, sc in enumerate([30.0, 25.0, 27.0, 22.0]):
        db.insert_program(generation=0, island=0, parent_ids=[], source=f"# {i}",
                          score=sc, runtime=0.01, status="ok")
    top = db.top_k(island=0, k=2, higher_is_better=False)
    assert [r.score for r in top] == [22.0, 25.0]
    assert db.count() == 4
    best = db.best(higher_is_better=False)
    assert best is not None and best.score == 22.0
    db.close()


def test_llm_log(tmp_path):
    db = ProgramDB(tmp_path / "p.sqlite")
    db.log_llm_call(generation=1, island=0, model="claude-opus-4-6",
                    temperature=0.8, prompt_hash="abc",
                    prompt="p", response="r", cached=False, elapsed=1.2)
    rows = db._conn.execute("SELECT * FROM llm_calls").fetchall()
    assert len(rows) == 1
    assert rows[0]["model"] == "claude-opus-4-6"
    db.close()

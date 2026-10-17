from fastapi.testclient import TestClient

from app.api.routes import get_assistant
from app.llm.client import LLMError
from app.rag.ingest import Chunk, chunk_text, document_chunks, school_chunks
from app.rag.retriever import RetrievalError, Retriever
from app.rag.store import VectorStore
from app.services.assistant import LEAK_ANSWER, STEP_LIMIT_ANSWER, Assistant
from app.tools.matcher import School
from app.tools.registry import Toolbox, parse_text_tool_call
from main import app

GRADES = {"english": 2, "mathematics": 3, "science": 2, "social_studies": 3, "electives": {"ict": 1, "french": 4}}


class FakeClient:
    """Scripted chat replies; embeds text into a 2-D vector keyed on a keyword."""
    embed_model = "fake-embed"

    def __init__(self, replies=()):
        self.replies = list(replies)
        self.calls = 0

    def chat(self, messages, tools=None, temperature=0.0):
        self.calls += 1
        reply = self.replies.pop(0) if self.replies else self.replies_default()
        if isinstance(reply, Exception):
            raise reply
        return reply

    def replies_default(self):
        return {"content": "ok"}

    def embed(self, texts):
        return [[1.0, 0.0] if "aggregate" in t.lower() else [0.0, 1.0] for t in texts]


def tool_call(name, **arguments):
    return {"content": "", "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}


def make_retriever(tmp_path, min_score=0.65):
    store = VectorStore("fake-embed")
    store.add([Chunk("doc#0", "The aggregate is a sum of grades.", {"source": "methodology.md"}),
               Chunk("doc#1", "Unrelated text about football.", {"source": "other.md"})],
              [[1.0, 0.0], [0.0, 1.0]])
    path = tmp_path / "index.json"
    store.save(path)
    return Retriever(FakeClient(), index_path=path, min_score=min_score)


# --- chunking / ingestion ---

def test_chunk_text_respects_size_and_keeps_all_content():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 40 for i in range(10))
    chunks = chunk_text(text, size=300, overlap=40)
    assert len(chunks) > 1
    assert all(len(c) <= 400 for c in chunks)
    assert "Paragraph 9" in chunks[-1]


def test_chunk_text_splits_a_single_huge_paragraph():
    assert len(chunk_text("A sentence here. " * 200, size=300, overlap=30)) > 5


def test_document_chunks_carry_metadata(tmp_path):
    (tmp_path / "a.md").write_text("Hello world.\n\nSecond paragraph.", encoding="utf-8")
    (tmp_path / "skip.bin").write_bytes(b"x")
    chunks = document_chunks(tmp_path)
    assert len(chunks) == 1
    assert chunks[0].metadata["source"] == "a.md" and chunks[0].metadata["source_type"] == "document"


def test_school_chunks():
    s = School("Test SHS", "B", "Ashanti", "girls", "boarding", ("science",))
    c = school_chunks([s])[0]
    assert "Test SHS" in c.text and c.metadata["category"] == "B"


# --- vector store / retriever ---

def test_store_ranks_and_roundtrips(tmp_path):
    r = make_retriever(tmp_path)
    store = VectorStore.load(r.index_path)
    hits = store.search([1.0, 0.1], top_k=2)
    assert hits[0].chunk.id == "doc#0" and hits[0].score > hits[1].score


def test_retriever_returns_relevant_hit(tmp_path):
    hits = make_retriever(tmp_path).retrieve("how is the aggregate computed")
    assert [h.chunk.id for h in hits] == ["doc#0"]


def test_retriever_returns_nothing_below_threshold(tmp_path):
    assert make_retriever(tmp_path, min_score=1.5).retrieve("aggregate") == []


def test_retriever_missing_or_stale_index(tmp_path):
    missing = Retriever(FakeClient(), index_path=tmp_path / "nope.json")
    try:
        missing.retrieve("x")
        assert False
    except RetrievalError:
        pass
    r = make_retriever(tmp_path)
    r.client.embed_model = "other-model"
    try:
        r.retrieve("x")
        assert False
    except RetrievalError as exc:
        assert "Rebuild" in str(exc)


# --- tools ---

def test_toolbox_recommend_schools(tmp_path):
    tb = Toolbox(make_retriever(tmp_path))
    out = tb.execute("recommend_schools", {**GRADES, "gender": "girls", "region": "Ashanti"})
    assert out["aggregate"] == 15 and out["estimated_categories"] == ["B", "C"]
    assert out["showing"] <= 10 and "unofficial" in out["note"]
    assert tb.sources


def test_toolbox_coerces_stringified_args(tmp_path):
    out = Toolbox(make_retriever(tmp_path)).execute(
        "compute_aggregate", {**{k: str(v) for k, v in GRADES.items() if k != "electives"},
                              "electives": '{"ict": "1", "french": "4"}'})
    assert out["aggregate"] == 15


def test_toolbox_errors_are_returned_not_raised(tmp_path):
    tb = Toolbox(make_retriever(tmp_path))
    assert "error" in tb.execute("nope", {})
    assert "error" in tb.execute("compute_aggregate", {"english": 1})
    assert "error" in tb.execute("compute_aggregate", {**GRADES, "english": 12})
    assert "error" in tb.execute("find_schools", {"aggregate": 99})


def test_toolbox_search_knowledge_and_no_evidence(tmp_path):
    tb = Toolbox(make_retriever(tmp_path))
    found = tb.execute("search_knowledge", {"query": "aggregate"})
    assert found["passages"] and tb.sources[0]["source"] == "methodology.md"
    empty = Toolbox(make_retriever(tmp_path, min_score=1.5)).execute("search_knowledge", {"query": "aggregate"})
    assert empty["passages"] == [] and "No relevant" in empty["message"]


def test_toolbox_missing_index_is_a_tool_error(tmp_path):
    tb = Toolbox(Retriever(FakeClient(), index_path=tmp_path / "missing.json"))
    assert "error" in tb.execute("search_knowledge", {"query": "x"})


def test_parse_text_tool_call():
    call = parse_text_tool_call('Sure: {"name": "find_schools", "parameters": {"aggregate": 12}}')
    assert call == {"name": "find_schools", "arguments": {"aggregate": 12}}
    assert parse_text_tool_call("no json here") is None
    assert parse_text_tool_call('{"foo": 1}') is None


# --- assistant loop ---

def test_assistant_uses_tool_then_answers(tmp_path):
    client = FakeClient([tool_call("compute_aggregate", **GRADES), {"content": "Your aggregate is 15."}])
    result = Assistant(client, make_retriever(tmp_path)).ask("my grades...")
    assert result.answer == "Your aggregate is 15."
    assert result.tool_calls == [{"tool": "compute_aggregate", "arguments": GRADES, "ok": True}]


def test_assistant_runs_only_first_parallel_tool_call(tmp_path):
    parallel = {"content": "", "tool_calls": [
        {"function": {"name": "compute_aggregate", "arguments": GRADES}},
        {"function": {"name": "find_schools", "arguments": {"aggregate": 1}}}]}
    result = Assistant(FakeClient([parallel, {"content": "done"}]), make_retriever(tmp_path)).ask("x")
    assert [c["tool"] for c in result.tool_calls] == ["compute_aggregate"]


def test_assistant_recovers_text_tool_call(tmp_path):
    text = {"content": '{"name": "compute_aggregate", "parameters": ' + __import__("json").dumps(GRADES) + "}"}
    result = Assistant(FakeClient([text, {"content": "15"}]), make_retriever(tmp_path)).ask("x")
    assert result.tool_calls[0]["ok"] and result.answer == "15"


def test_assistant_suppresses_leaked_tool_text(tmp_path):
    leak = {"content": 'I will call {"name":"x","parameters":{"a":1'}
    assert Assistant(FakeClient([leak]), make_retriever(tmp_path)).ask("x").answer == LEAK_ANSWER


def test_assistant_step_limit(tmp_path):
    loop = [tool_call("find_schools", aggregate=20)] * 20
    client = FakeClient(loop)
    result = Assistant(client, make_retriever(tmp_path)).ask("x")
    assert result.answer == STEP_LIMIT_ANSWER and client.calls == 5


def test_assistant_empty_answer_is_an_error(tmp_path):
    try:
        Assistant(FakeClient([{"content": "  "}]), make_retriever(tmp_path)).ask("x")
        assert False
    except LLMError:
        pass


# --- /ask endpoint ---

def _override(assistant):
    app.dependency_overrides[get_assistant] = lambda: assistant


def teardown_function():
    app.dependency_overrides.clear()


def test_ask_endpoint_success(tmp_path):
    _override(Assistant(FakeClient([tool_call("compute_aggregate", **GRADES), {"content": "15"}]),
                        make_retriever(tmp_path)))
    r = TestClient(app).post("/ask", json={"message": "grades"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "15" and body["tool_calls"][0]["tool"] == "compute_aggregate" and body["sources"]


def test_ask_endpoint_validation():
    c = TestClient(app)
    assert c.post("/ask", json={"message": ""}).status_code == 422
    assert c.post("/ask", json={"message": "   "}).status_code == 422
    assert c.post("/ask", json={"message": "x" * 2001}).status_code == 422
    assert c.post("/ask", json={}).status_code == 422


def test_ask_endpoint_llm_down_returns_503(tmp_path):
    _override(Assistant(FakeClient([LLMError("Cannot reach the model server")]), make_retriever(tmp_path)))
    r = TestClient(app).post("/ask", json={"message": "hi"})
    assert r.status_code == 503 and "unavailable" in r.json()["detail"]

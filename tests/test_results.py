from fastapi.testclient import TestClient

from main import app

client = TestClient(app)
CSV = "subject,grade\nEnglish,2\nMathematics,3\nScience,2\nSocial Studies,3\nRME,4\nICT,2\n"
JSON = (
    '{"english":2,"mathematics":3,"science":2,"social_studies":3,'
    '"electives":{"rme":4,"ict":2}}'
)


def _upload(name, data):
    return client.post("/results/upload", files={"file": (name, data)})


def test_upload_csv():
    r = _upload("r.csv", CSV)
    assert r.status_code == 200
    assert r.json()["aggregate"] == 16
    assert r.json()["grades"]["electives"] == {"rme": 4, "ict": 2}


def test_upload_json():
    assert _upload("r.json", JSON).json()["aggregate"] == 16


def test_manual():
    body = {"english": 2, "mathematics": 3, "science": 2, "social_studies": 3, "electives": {"RME": 4, "ict": 2}}
    r = client.post("/results/manual", json=body)
    assert r.status_code == 200 and r.json()["aggregate"] == 16


def test_upload_rejects_bad_input():
    assert _upload("r.txt", CSV).status_code == 422
    assert _upload("r.csv", CSV.replace("English,2", "English,12")).status_code == 422
    assert _upload("r.csv", "subject,grade\nEnglish,2\n").status_code == 422
    assert _upload("r.csv", "x" * 200_000).status_code == 422


class FakeAssistant:
    def __init__(self):
        self.seen = []

    def ask(self, message, history=None):
        from app.services.assistant import AssistantResult
        self.seen.append(history)
        return AssistantResult("hi")


def test_chat_remembers_grades_and_history():
    from app.api.routes import get_assistant
    fake = FakeAssistant()
    app.dependency_overrides[get_assistant] = lambda: fake
    try:
        grades = {"english": 2, "mathematics": 3, "science": 2, "social_studies": 3, "electives": {"rme": 4, "ict": 2}}
        assert client.post("/chat", json={"session_id": "s1", "message": "hello", "grades": grades}).status_code == 200
        client.post("/chat", json={"session_id": "s1", "message": "again"})
        assert "confirmed" in fake.seen[1][0]["content"] and len(fake.seen[1]) == 3
        assert client.post("/chat", json={"session_id": "s1", "message": " "}).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_chat_page_served():
    assert "SHS School Recommender" in client.get("/").text

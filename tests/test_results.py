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

    def ask(self, message, history=None, grades=None):
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


def test_confirmed_grades_override_bad_model_args():
    from app.tools.registry import Toolbox, parse_text_tool_call
    grades = {"english": 2, "mathematics": 3, "science": 4, "social_studies": 2, "electives": {"career_tech": 2, "french": 1}}
    bad = '{"name":"find_schools","parameters":{"aggregate":compute_aggregate,"region":"Accra","gender":"null"}}'
    call = parse_text_tool_call(bad)
    assert call["name"] == "find_schools" and call["arguments"]["region"] == "Accra"
    result = Toolbox(retriever=None, grades=grades).execute(call["name"], call["arguments"])
    assert "error" not in result and result["aggregate"] == 14 and result["total_matches"] > 0


SLIP_ROWS = [("SUBJECT", "SCORE", "GRADE"), ("English Language", "78", "2"), ("Mathematics", "65", "3"),
             ("Integrated Science", "60", "4"), ("Social Studies", "80", "2"),
             ("Religious and Moral Education", "70", "3"), ("Information and Communication Technology", "85", "1"),
             ("Total Aggregate", "", "15")]


def test_grades_from_lines():
    from app.services.ocr import grades_from_lines
    data = grades_from_lines([f"{a} {b} {c}" for a, b, c in SLIP_ROWS])
    assert data == {"english": 2, "mathematics": 3, "science": 4, "social_studies": 2,
                    "electives": {"rme": 3, "ict": 1}}


def _slip_image():
    import pytest
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except OSError:
        pytest.skip("arial.ttf not available")
    img = Image.new("RGB", (1000, 520), "white")
    draw = ImageDraw.Draw(img)
    for i, row in enumerate(SLIP_ROWS):
        for x, text in zip((30, 700, 880), row):
            draw.text((x, 20 + i * 60), text, fill="black", font=font)
    return img


def test_upload_image_and_scanned_pdf():
    import io
    img = _slip_image()
    png, pdf = io.BytesIO(), io.BytesIO()
    img.save(png, "PNG")
    img.save(pdf, "PDF")
    for name, data in (("slip.png", png.getvalue()), ("slip.pdf", pdf.getvalue())):
        r = _upload(name, data)
        assert r.status_code == 200, r.text
        assert r.json()["aggregate"] == 2 + 3 + 4 + 2 + 1 + 3


def test_upload_unreadable_scan():
    import io
    from PIL import Image
    blank = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(blank, "PNG")
    assert _upload("blank.png", blank.getvalue()).status_code == 422
    assert _upload("fake.png", b"not an image").status_code == 422
    assert _upload("fake.pdf", b"not a pdf").status_code == 422

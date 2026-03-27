from app.llm.client import build_llm


def test_build_llm_exists():
    assert callable(build_llm)


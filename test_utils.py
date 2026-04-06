from utils import hash_text

def test_hash_text():
    text = "Exemplo"
    result = hash_text(text)
    assert isinstance(result, str)
    assert len(result) == 64
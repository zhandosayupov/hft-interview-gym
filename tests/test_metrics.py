import pytest

from gym.metrics import analyze_answer, analyze_transcript, repetitions, sentences, words


def test_words_normalise_apostrophes():
    assert words("I’m sure, it's O(n).") == ["i'm", "sure", "it's", "o", "n"]


def test_filled_pauses_counted_as_tokens_only():
    m = analyze_answer(0, "Um, so uh I would use a heap. Umm, under the hood, err no.")
    assert m.filled_pauses == {"uh": 1, "um": 1, "umm": 1}
    # "under", "hood" and "err" must not count as "uh"/"er".
    assert "er" not in m.filled_pauses


def test_discourse_and_hedges():
    m = analyze_answer(0, "Basically I think it's, you know, kind of O(n log n). Maybe.")
    assert m.discourse_fillers == {"basically": 1, "you know": 1, "kind of": 1}
    assert m.hedges == {"i think": 1, "maybe": 1}


@pytest.mark.parametrize("text,expected", [
    ("Like, I would use a map.", 1),
    ("It is, like, a ring buffer.", 1),
    ("I would like a lock-free queue.", 0),
    ("It looks like a heap.", 0),
])
def test_like_filler_heuristic(text, expected):
    assert analyze_answer(0, text).like_fillers == expected


def test_repetitions():
    assert repetitions(words("I I think the the queue is very very fast")) == 2


def test_sentences():
    assert sentences("One. Two? Three!") == ["One", "Two", "Three"]
    assert sentences("O(n) is fine") == ["O(n) is fine"]


def test_transcript_aggregate():
    long = " ".join(["word"] * 160)
    t = analyze_transcript(["Uh, use a hash map.", "", "   ", long, "Um um, basically yes."])
    assert t.answers == 3
    assert t.total_words == 5 + 160 + 4
    assert t.filled_pauses_total == 3
    assert t.long_answers == [1]
    assert t.max_answer_words == 160
    assert t.median_answer_words == 5
    assert t.filled_per_100w == round(300 / 169, 2)
    assert dict(t.top_fillers)["um"] == 2


def test_zero_filler_caveat():
    t = analyze_transcript(["Use a min-heap of size K; push and pop are log K."])
    assert any("transcriber" in c for c in t.caveats)


def test_empty_transcript():
    t = analyze_transcript([])
    assert t.total_words == 0 and t.filled_per_100w == 0.0 and t.median_answer_words == 0.0

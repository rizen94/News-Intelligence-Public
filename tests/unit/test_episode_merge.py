"""Episode title match helpers (no DB)."""

from shared.episode_title_match import episode_title_similarity, normalize_episode_title


def test_normalize_title_collapses_whitespace():
    assert normalize_episode_title("  Meta   Court  ") == "meta court"


def test_title_similarity_exact():
    assert episode_title_similarity(
        "Meta heads to court in a landmark trial",
        "Meta heads to court in a landmark trial",
    ) == 1.0


def test_title_similarity_near_duplicate():
    a = "Luigi Mangione Pleads Guilty to Killing Healthcare CEO in Federal Court"
    b = "Luigi Mangione Pleads Guilty to Killing Healthcare CEO in Federal Case"
    assert episode_title_similarity(a, b) >= 0.88


def test_title_similarity_unrelated():
    assert episode_title_similarity("Meta court trial", "Netanyahu Gaza plan") < 0.5

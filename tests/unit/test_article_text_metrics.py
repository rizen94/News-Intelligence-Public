from shared.article_text_metrics import compute_word_count, word_count_sql_expr


def test_compute_word_count_empty():
    assert compute_word_count(None) == 0
    assert compute_word_count("   ") == 0


def test_compute_word_count_basic():
    assert compute_word_count("one two three") == 3


def test_word_count_sql_expr_includes_columns():
    expr = word_count_sql_expr()
    assert "word_count" in expr
    assert "content" in expr

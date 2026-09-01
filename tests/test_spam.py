from bot import parse_spam_command, spam_text_for_index


def test_spam_parses_single_text():
    assert parse_spam_command('.spam 3 hello world') == (3, ['hello world'])


def test_spam_parses_comma_separated_variants_with_optional_spaces():
    assert parse_spam_command('.spam 4 one,two, three') == (4, ['one', 'two', 'three'])


def test_spam_rejects_invalid_or_unsafe_count():
    assert parse_spam_command('.spam 0 hello') is None
    assert parse_spam_command('.spam 51 hello') is None
    assert parse_spam_command('.spam many hello') is None
    assert parse_spam_command('.spam 3') is None


def test_spam_alternates_variants_round_robin():
    variants = ['one', 'two', 'three']
    assert [spam_text_for_index(variants, i) for i in range(7)] == [
        'one', 'two', 'three', 'one', 'two', 'three', 'one'
    ]

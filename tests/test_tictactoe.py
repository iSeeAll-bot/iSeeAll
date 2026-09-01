from bot import (
    new_game,
    apply_move,
    game_status,
    game_keyboard_rows,
)


def test_new_game_has_empty_board_and_owner_turn():
    game = new_game(owner_id=1, opponent_id=2, owner_name="Алиса", opponent_name="Боб")
    assert game["board"] == [" "] * 9
    assert game["turn"] == 1
    assert game["status"] == "active"


def test_render_uses_player_names_for_turn_and_winner():
    game = new_game(1, 2, "Алиса", "Боб")
    assert "Ход: <b>Алиса</b>" in __import__('bot').render_game(game)
    for index, player in ((0, 1), (3, 2), (1, 1), (4, 2), (2, 1)):
        assert apply_move(game, index, player) is True
    assert "Победитель: <b>Алиса</b>" in __import__('bot').render_game(game)


def test_apply_move_alternates_players():
    game = new_game(1, 2)
    assert apply_move(game, 0, 1) is True
    assert game["board"][0] == "X"
    assert game["turn"] == 2
    assert apply_move(game, 1, 2) is True
    assert game["board"][1] == "O"


def test_player_cannot_move_twice_or_take_occupied_cell():
    game = new_game(1, 2)
    assert apply_move(game, 0, 1) is True
    assert apply_move(game, 1, 1) is False
    assert apply_move(game, 0, 2) is False


def test_winner_and_draw_are_detected():
    game = new_game(1, 2)
    for index in (0, 3, 1, 4):
        apply_move(game, index, game["turn"])
    assert apply_move(game, 2, 1) is True
    assert game_status(game) == "winner:1"

    draw = new_game(1, 2)
    for index, player in ((0, 1), (1, 2), (2, 1), (4, 2),
                          (3, 1), (5, 2), (7, 1), (6, 2), (8, 1)):
        assert apply_move(draw, index, player) is True
    assert game_status(draw) == "draw"


def test_board_has_nine_buttons():
    rows = game_keyboard_rows([" "] * 9)
    assert sum(len(row) for row in rows) == 9


def test_game_turn_alternates_and_owner_cannot_move_twice():
    game = new_game(10, 20)
    assert apply_move(game, 0, 10) is True
    assert apply_move(game, 1, 10) is False
    assert apply_move(game, 1, 20) is True
    assert apply_move(game, 2, 20) is False

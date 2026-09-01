from types import SimpleNamespace

from bot import (
    apply_rps_choice,
    game_menu_keyboard,
    new_rps_game,
    rps_keyboard,
    rps_result,
)


def test_rps_game_starts_empty():
    game = new_rps_game(1, 2, "Алиса", "Боб")
    assert game["owner_choice"] is None
    assert game["opponent_choice"] is None
    assert game["status"] == "active"


def test_rps_choices_are_private_and_each_player_chooses_once():
    game = new_rps_game(1, 2, "Алиса", "Боб")
    assert apply_rps_choice(game, 1, "rock") is True
    assert apply_rps_choice(game, 1, "paper") is False
    assert apply_rps_choice(game, 2, "scissors") is True
    assert game["status"] == "finished"


def test_rps_rejects_unknown_player_and_choice():
    game = new_rps_game(1, 2, "Алиса", "Боб")
    assert apply_rps_choice(game, 3, "rock") is False
    assert apply_rps_choice(game, 1, "lizard") is False


def test_rps_rules():
    assert rps_result("rock", "scissors") == "owner"
    assert rps_result("paper", "rock") == "owner"
    assert rps_result("scissors", "paper") == "owner"
    assert rps_result("rock", "rock") == "draw"
    assert rps_result("scissors", "rock") == "opponent"


def test_keyboards_have_expected_buttons():
    assert len(game_menu_keyboard().inline_keyboard) == 2
    assert len(rps_keyboard(123).inline_keyboard[0]) == 3

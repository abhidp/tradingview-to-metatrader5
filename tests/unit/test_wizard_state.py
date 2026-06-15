from app.wizard import state


def test_onboarding_defaults_incomplete(temp_db_path):
    assert state.is_onboarding_complete() is False
    assert state.get_step() == 1


def test_set_complete_and_step(temp_db_path):
    state.set_step(3)
    assert state.get_step() == 3
    state.set_onboarding_complete(True)
    assert state.is_onboarding_complete() is True

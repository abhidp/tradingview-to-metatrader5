from app.storage.secret_box import PlaintextSecretBox


def test_protect_adds_prefix():
    box = PlaintextSecretBox()
    assert box.protect("hunter2") == "plain:hunter2"


def test_unprotect_inverts_protect():
    box = PlaintextSecretBox()
    assert box.unprotect(box.protect("hunter2")) == "hunter2"


def test_unprotect_of_unprefixed_value_is_identity():
    """Legacy/manually-written values without the prefix read back verbatim."""
    box = PlaintextSecretBox()
    assert box.unprotect("rawvalue") == "rawvalue"

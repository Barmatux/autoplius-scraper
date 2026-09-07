from pathlib import Path

import pytest

from scraper.db import (
    count_unread_feedback,
    create_feedback_message,
    fetch_feedback_messages,
    init_db,
    set_feedback_status,
)


def test_feedback_callback_and_message(tmp_path: Path):
    db = tmp_path / "t.db"
    init_db(db)

    callback = create_feedback_message(db, kind="callback", phone="+375291112233")
    assert callback["kind"] == "callback"
    assert count_unread_feedback(db) == 1

    message = create_feedback_message(
        db,
        kind="message",
        name="Иван",
        body="Нужна помощь с подбором",
    )
    assert message["kind"] == "message"
    assert count_unread_feedback(db) == 2

    rows = fetch_feedback_messages(db)
    assert len(rows) == 2

    updated = set_feedback_status(db, int(callback["id"]), status="done")
    assert updated["status"] == "done"
    assert count_unread_feedback(db) == 1


def test_feedback_validation(tmp_path: Path):
    db = tmp_path / "t.db"
    init_db(db)
    with pytest.raises(ValueError):
        create_feedback_message(db, kind="callback", phone="12")
    with pytest.raises(ValueError):
        create_feedback_message(db, kind="message", body="hi")

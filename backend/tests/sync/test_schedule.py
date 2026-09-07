from backend.app.sync.schedule import PRODUCTION_SYNC_SCHEDULE


def test_production_schedule_is_disabled_by_default() -> None:
    assert PRODUCTION_SYNC_SCHEDULE.enabled is False
    assert PRODUCTION_SYNC_SCHEDULE.reason == "PRODUCTION_SCHEDULE_DISABLED_UNTIL_APPROVAL"

from backend.app.sync.run_lock import SyncRunLock


def test_first_run_acquires_lock() -> None:
    lock = SyncRunLock()

    acquired = lock.acquire(
        tenant_id="store-a",
        provider="demo",
        resource="sales",
    )

    assert acquired is True
    assert (
        lock.is_locked(
            tenant_id="store-a",
            provider="demo",
            resource="sales",
        )
        is True
    )


def test_same_provider_resource_cannot_run_twice() -> None:
    lock = SyncRunLock()

    assert (
        lock.acquire(
            tenant_id="store-a",
            provider="demo",
            resource="sales",
        )
        is True
    )

    assert (
        lock.acquire(
            tenant_id="store-a",
            provider="demo",
            resource="sales",
        )
        is False
    )


def test_different_resource_can_run_independently() -> None:
    lock = SyncRunLock()

    assert (
        lock.acquire(
            tenant_id="store-a",
            provider="demo",
            resource="sales",
        )
        is True
    )

    assert (
        lock.acquire(
            tenant_id="store-a",
            provider="demo",
            resource="inventory",
        )
        is True
    )


def test_different_tenant_has_separate_lock() -> None:
    lock = SyncRunLock()

    assert (
        lock.acquire(
            tenant_id="store-a",
            provider="demo",
            resource="sales",
        )
        is True
    )

    assert (
        lock.acquire(
            tenant_id="store-b",
            provider="demo",
            resource="sales",
        )
        is True
    )


def test_release_allows_next_run() -> None:
    lock = SyncRunLock()

    assert (
        lock.acquire(
            tenant_id="store-a",
            provider="demo",
            resource="sales",
        )
        is True
    )

    lock.release(
        tenant_id="store-a",
        provider="demo",
        resource="sales",
    )

    assert (
        lock.acquire(
            tenant_id="store-a",
            provider="demo",
            resource="sales",
        )
        is True
    )

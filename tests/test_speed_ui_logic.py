import time
from types import SimpleNamespace

from uac_desktop.storage import Storage
from uac_desktop.ui import MainWindow


def test_recent_working_sni_precedes_higher_unverified_lab_score():
    dummy = SimpleNamespace(storage=SimpleNamespace(
        scan_results=[
            {"domain": "new-score.example", "success": True, "score": 1200},
            {"domain": "working.example", "success": True, "score": 600},
        ],
        bookmarks=[],
        settings={
            "working_pattern_sni_irancell": "working.example",
            "working_pattern_sni_at_irancell": time.time(),
        },
        tuning=SimpleNamespace(carrier_mode="irancell"),
    ))

    assert MainWindow._sni_candidates(dummy, carrier="irancell", limit=2) == [
        "working.example", "new-score.example"
    ]


def _migrated_tuning(tuning, version=0):
    storage = Storage.__new__(Storage)
    storage.settings = {"tuning": dict(tuning), "speed_core_version": version}
    storage.save_settings = lambda: None
    Storage._migrate_speed_core(storage)
    return storage.settings["tuning"], storage.settings["speed_core_version"]


def test_speed_migration_lifts_old_fast_handshake_cap():
    tuning, version = _migrated_tuning({"mode": "fast", "pattern_max_sessions": 6})

    assert tuning["pattern_max_sessions"] == 10
    assert tuning["xray_mux_enabled"] is True
    assert tuning["background_quality_probe_enabled"] is False
    assert version == 3


def test_speed_migration_uses_streaming_mux_and_session_defaults():
    tuning, version = _migrated_tuning({"mode": "streaming"})

    assert tuning["xray_mux_enabled"] is False
    assert tuning["xray_mux_concurrency"] == 4
    assert tuning["pattern_max_sessions"] == 10
    assert tuning["pattern_keepalive_interval_s"] == 2
    assert version == 3


def test_speed_migration_preserves_compatibility_and_stealth_low_caps():
    for mode, cap in (("compatibility", 4), ("stealth", 5)):
        tuning, _ = _migrated_tuning({
            "mode": mode,
            "pattern_max_sessions": cap,
            "xray_mux_enabled": True,
        })
        assert tuning["pattern_max_sessions"] == cap
        assert tuning["xray_mux_enabled"] is False


def test_speed_migration_repairs_v2_generic_compatibility_defaults():
    tuning, version = _migrated_tuning({
        "mode": "compatibility",
        "pattern_quality_preset": "compatibility",
        "pattern_max_sessions": 10,
        "xray_mux_enabled": True,
    }, version=2)

    assert tuning["pattern_max_sessions"] == 4
    assert tuning["xray_mux_enabled"] is False
    assert version == 3


def test_speed_migration_uses_pattern_preset_for_missing_custom_values():
    tuning, _ = _migrated_tuning({
        "mode": "custom",
        "pattern_quality_preset": "streaming",
        "pattern_max_sessions": 5,
    })

    assert tuning["pattern_max_sessions"] == 5
    assert tuning["xray_mux_enabled"] is False
    assert tuning["xray_mux_concurrency"] == 4
    assert tuning["pattern_keepalive_interval_s"] == 2


def test_speed_migration_preserves_unknown_mode_explicit_low_cap():
    tuning, _ = _migrated_tuning({
        "mode": "my-private-profile",
        "pattern_quality_preset": "low_latency",
        "pattern_max_sessions": 3,
        "xray_mux_enabled": False,
    })

    assert tuning["pattern_max_sessions"] == 3
    assert tuning["xray_mux_enabled"] is False
    assert tuning["pattern_edge_failure_cooldown_s"] == 6

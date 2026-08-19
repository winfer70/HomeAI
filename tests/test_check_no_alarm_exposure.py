from __future__ import annotations

import re
from pathlib import Path

from heimdall.scripts import check_no_alarm_exposure
from homeai.guardrails import scan_paths

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_main_without_args_expands_real_heimdall_tree(monkeypatch, capsys) -> None:
    monkeypatch.chdir(REPO_ROOT)
    scanned_paths: list[Path] = []

    def fake_scan_paths(paths: list[Path]) -> list[object]:
        scanned_paths.extend(paths)
        return []

    monkeypatch.setattr(check_no_alarm_exposure, "scan_paths", fake_scan_paths)

    exit_code = check_no_alarm_exposure.main([])
    captured = capsys.readouterr()
    match = re.search(r"Checked (\d+) file\(s\); no forbidden alarm exposure found\.", captured.out)

    assert exit_code == 0
    assert match is not None
    assert len(scanned_paths) > 1
    assert all(path.is_file() for path in scanned_paths)
    assert all(path.parts and path.parts[0] == "heimdall" for path in scanned_paths)
    assert int(match.group(1)) == len(scanned_paths)

    # Regression: the old implementation returned [Path("heimdall")] here, so
    # scan_paths() received a single directory path and silently scanned zero files.


def test_collect_paths_expands_directory_and_scan_paths_finds_violation(tmp_path) -> None:
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    clean_file = nested_dir / "clean.yaml"
    clean_file.write_text("entity_id: light.kitchen\n", encoding="utf-8")
    violating_file = nested_dir / "violation.yaml"
    violating_file.write_text("entity_id: alarm_control_panel.satel_test\n", encoding="utf-8")

    paths = check_no_alarm_exposure._collect_paths([str(tmp_path)])
    violations = scan_paths(paths)

    assert clean_file in paths
    assert violating_file in paths
    assert any(
        violation.source == str(violating_file)
        and violation.rule == "forbidden alarm entity id"
        and violation.match == "alarm_control_panel.satel_test"
        for violation in violations
    )

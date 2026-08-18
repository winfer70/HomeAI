#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLES_DIR = REPO_ROOT / "heimdall" / "tests" / "audio_samples"
EXPECTED_LANGUAGE_BY_PREFIX = {
    "en": "English",
    "pl": "Polish",
}


@dataclass(frozen=True)
class BenchmarkResult:
    filename: str
    expected_language: str
    detected_language: str
    text: str
    latency_seconds: float


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure faster-whisper transcription latency.")
    parser.add_argument(
        "--samples-dir",
        type=Path,
        default=DEFAULT_SAMPLES_DIR,
        help="Directory containing WAV clips to transcribe.",
    )
    parser.add_argument(
        "--model-size",
        default="medium",
        help="Whisper model size to benchmark (for example: small, medium).",
    )
    return parser.parse_args(argv)


def _expected_language(sample_path: Path) -> str:
    prefix = sample_path.stem.split("_", 1)[0].lower()
    return EXPECTED_LANGUAGE_BY_PREFIX.get(prefix, "Unknown")


def _collect_samples(samples_dir: Path) -> list[Path]:
    if not samples_dir.exists():
        raise FileNotFoundError(f"Samples directory does not exist: {samples_dir}")
    if not samples_dir.is_dir():
        raise NotADirectoryError(f"Samples path is not a directory: {samples_dir}")

    samples = sorted(path for path in samples_dir.glob("*.wav") if path.is_file())
    if not samples:
        raise FileNotFoundError(f"No WAV files found in: {samples_dir}")
    return samples


def _load_model(model_size: str) -> WhisperModel:
    try:
        from faster_whisper import WhisperModel
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "faster-whisper is required to run this benchmark. "
            "Install it in the benchmark environment before running the script."
        ) from exc

    return WhisperModel(model_size, device="cpu", compute_type="int8")


def _transcribe_sample(model: WhisperModel, sample_path: Path) -> BenchmarkResult:
    started_at = time.perf_counter()
    segments, info = model.transcribe(str(sample_path))
    text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
    latency_seconds = time.perf_counter() - started_at

    return BenchmarkResult(
        filename=sample_path.name,
        expected_language=_expected_language(sample_path),
        detected_language=info.language or "unknown",
        text=text,
        latency_seconds=latency_seconds,
    )


def _print_result(result: BenchmarkResult) -> None:
    print(f"File: {result.filename}")
    print(f"Expected language: {result.expected_language}")
    print(f"Detected language: {result.detected_language}")
    print(f"Transcribed text: {result.text}")
    print(f"Latency (s): {result.latency_seconds:.3f}")
    print()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        samples = _collect_samples(args.samples_dir)
        model = _load_model(args.model_size)
    except (FileNotFoundError, NotADirectoryError, ModuleNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"Benchmarking {len(samples)} clip(s) from {args.samples_dir}")
    print(f"Model size: {args.model_size}")
    print()

    for sample_path in samples:
        result = _transcribe_sample(model, sample_path)
        _print_result(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

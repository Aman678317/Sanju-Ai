"""Minimal MLOps-style batch job for rolling-mean signal metrics.

The job reads a CSV containing a ``close`` column, loads runtime configuration
from YAML, computes a rolling-mean signal, and writes machine-readable metrics
for both success and failure cases.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


REQUIRED_CONFIG_FIELDS = ("seed", "window", "version")


class JobError(Exception):
    """Expected validation or processing error that should be reported cleanly."""


def setup_logging(log_file: Path) -> None:
    """Configure file logging for each run."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a reproducible rolling-mean signal batch job."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input CSV path.")
    parser.add_argument("--config", required=True, type=Path, help="YAML config path.")
    parser.add_argument(
        "--output", required=True, type=Path, help="Output metrics JSON path."
    )
    parser.add_argument("--log-file", required=True, type=Path, help="Run log path.")
    return parser.parse_args()


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise JobError(f"Config file does not exist: {config_path}")

    try:
        with config_path.open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise JobError(f"Invalid YAML config: {exc}") from exc
    except OSError as exc:
        raise JobError(f"Unable to read config file: {exc}") from exc

    if not isinstance(config, dict):
        raise JobError("Config must be a YAML mapping/object.")

    missing_fields = [field for field in REQUIRED_CONFIG_FIELDS if field not in config]
    if missing_fields:
        raise JobError(f"Missing required config field(s): {', '.join(missing_fields)}")

    seed = config["seed"]
    window = config["window"]
    version = config["version"]

    if not isinstance(seed, int):
        raise JobError("Config field 'seed' must be an integer.")
    if not isinstance(window, int) or window <= 0:
        raise JobError("Config field 'window' must be a positive integer.")
    if not isinstance(version, str) or not version.strip():
        raise JobError("Config field 'version' must be a non-empty string.")

    validated_config = {"seed": seed, "window": window, "version": version}
    logging.info("Config loaded and validated.")
    logging.info(
        "Runtime config: seed=%s window=%s version=%s",
        seed,
        window,
        version,
    )
    return validated_config


def load_data(input_path: Path) -> pd.DataFrame:
    if not input_path.exists():
        raise JobError(f"Input file does not exist: {input_path}")

    try:
        data = pd.read_csv(input_path)
    except pd.errors.EmptyDataError as exc:
        raise JobError("Input CSV is empty or has no columns.") from exc
    except pd.errors.ParserError as exc:
        raise JobError(f"Input CSV is not readable: {exc}") from exc
    except OSError as exc:
        raise JobError(f"Unable to read input CSV: {exc}") from exc

    if data.empty:
        raise JobError("Input CSV contains no rows.")
    if "close" not in data.columns:
        raise JobError("Input CSV must contain a 'close' column.")

    close_only = data[["close"]].copy()
    close_only["close"] = pd.to_numeric(close_only["close"], errors="coerce")
    if close_only["close"].isna().any():
        raise JobError("Input 'close' column must contain only numeric values.")

    logging.info("Rows loaded: %s", len(close_only))
    return close_only


def compute_signal_rate(data: pd.DataFrame, window: int) -> float:
    if len(data) < window:
        raise JobError(
            f"Input CSV must contain at least {window} rows for the configured window."
        )

    logging.info("Rolling mean step started.")
    rolling_mean = data["close"].rolling(window=window).mean()

    logging.info("Signal generation step started.")
    signal = (data["close"] > rolling_mean).astype(int)
    valid_signal = signal[rolling_mean.notna()]

    if valid_signal.empty:
        raise JobError("No valid signal rows were produced.")

    return float(valid_signal.mean())


def write_metrics(metrics: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)
        file.write("\n")


def build_error_metrics(version: str, error_message: str) -> dict[str, Any]:
    return {
        "version": version,
        "status": "error",
        "error_message": error_message,
    }


def main() -> int:
    args = parse_args()
    setup_logging(args.log_file)

    start_time = time.perf_counter()
    version = "unknown"
    exit_code = 1

    logging.info("Job start timestamp.")

    try:
        config = load_config(args.config)
        version = config["version"]
        np.random.seed(config["seed"])
        logging.info("Deterministic seed set: %s", config["seed"])

        data = load_data(args.input)
        signal_rate = compute_signal_rate(data, config["window"])
        latency_ms = int(round((time.perf_counter() - start_time) * 1000))

        metrics = {
            "version": version,
            "rows_processed": int(len(data)),
            "metric": "signal_rate",
            "value": round(signal_rate, 4),
            "latency_ms": latency_ms,
            "seed": config["seed"],
            "status": "success",
        }
        logging.info("Metrics summary: %s", metrics)
        logging.info("Job end status: success")
        exit_code = 0
    except Exception as exc:
        error_message = str(exc)
        metrics = build_error_metrics(version, error_message)
        if isinstance(exc, JobError):
            logging.error("Validation or processing error: %s", error_message)
        else:
            logging.exception("Unexpected exception occurred.")
        logging.info("Job end status: error")

    write_metrics(metrics, args.output)
    print(json.dumps(metrics, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

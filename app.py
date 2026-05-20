"""Vercel web entrypoint for the MLOps batch task.

The internship deliverable is still the CLI in ``run.py``. This file only
adapts the same processing logic into a small Flask app so Vercel can deploy
the repository as a Python project.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
from flask import Flask, jsonify

from run import build_error_metrics, compute_signal_rate, load_config, load_data


app = Flask(__name__)


def run_batch_job() -> dict[str, Any]:
    """Run the same batch calculation used by the CLI and return metrics."""
    start_time = time.perf_counter()
    version = "unknown"

    try:
        config = load_config(Path("config.yaml"))
        version = config["version"]
        np.random.seed(config["seed"])

        data = load_data(Path("data.csv"))
        signal_rate = compute_signal_rate(data, config["window"])
        latency_ms = int(round((time.perf_counter() - start_time) * 1000))

        return {
            "version": version,
            "rows_processed": int(len(data)),
            "metric": "signal_rate",
            "value": round(signal_rate, 4),
            "latency_ms": latency_ms,
            "seed": config["seed"],
            "status": "success",
        }
    except Exception as exc:
        return build_error_metrics(version, str(exc))


@app.get("/")
def home():
    metrics = run_batch_job()
    status_code = 200 if metrics["status"] == "success" else 500
    return jsonify(
        {
            "project": "Sanju-Ai",
            "description": "Minimal ML/MLOps rolling-mean batch job deployed on Vercel.",
            "cli_command": "python run.py --input data.csv --config config.yaml --output metrics.json --log-file run.log",
            "metrics": metrics,
        }
    ), status_code


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/metrics")
def metrics():
    metrics_payload = run_batch_job()
    status_code = 200 if metrics_payload["status"] == "success" else 500
    return jsonify(metrics_payload), status_code

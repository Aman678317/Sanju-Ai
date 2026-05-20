# Sanju-Ai

## Project overview

This project implements a minimal production-style batch job for an ML/MLOps internship technical assessment. It reads market-like CSV data, loads a YAML configuration, computes a rolling-mean signal from the `close` column, and writes machine-readable metrics and logs.

The job demonstrates:

- Reproducibility through config-driven parameters and deterministic seeding.
- Observability through structured metrics and run logs.
- Deployment readiness through Docker and a one-command container run.

## Requirements

- Python 3.9+
- pandas
- numpy
- PyYAML
- Docker, optional for container execution

Install Python dependencies with:

```bash
pip install -r requirements.txt
```

## File structure

```text
.
|-- Dockerfile
|-- README.md
|-- config.yaml
|-- data.csv
|-- metrics.json
|-- requirements.txt
|-- run.log
`-- run.py
```

## Configuration

`config.yaml` must include:

```yaml
seed: 42
window: 5
version: "v1"
```

- `seed`: integer used with `numpy.random.seed`.
- `window`: positive integer rolling window.
- `version`: non-empty string included in metrics output.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Local run command

```bash
python run.py --input data.csv --config config.yaml --output metrics.json --log-file run.log
```

The command prints the final metrics JSON to stdout and writes:

- `metrics.json`
- `run.log`

## Docker build command

```bash
docker build -t mlops-task .
```

## Docker run command

```bash
docker run --rm mlops-task
```

The container includes `data.csv` and `config.yaml`, runs the batch job, prints final metrics JSON to stdout, and exits with code `0` on success.

## Vercel deployment

This repository includes `app.py`, a small Flask entrypoint for Vercel. The original assessment CLI remains in `run.py`; `app.py` only exposes the same calculation as HTTP JSON so Vercel can deploy the repository.

Available routes:

- `/`: project summary plus current metrics
- `/metrics`: metrics JSON only
- `/health`: health check

In Vercel, use:

- Framework Preset: Python
- Root Directory: `./`
- Branch: `main`

## GitHub Actions

The repository includes a CI workflow that installs dependencies and runs the required CLI on every push and pull request. This gives evaluators a direct proof that the task runs successfully from GitHub.

## Expected output

Successful runs produce metrics with these keys:

```json
{
  "version": "v1",
  "rows_processed": 20,
  "metric": "signal_rate",
  "value": 0.9375,
  "latency_ms": 23,
  "seed": 42,
  "status": "success"
}
```

`latency_ms` can vary by machine.

## Error handling

The job writes `metrics.json` even when it fails. Error output uses this shape:

```json
{
  "version": "v1",
  "status": "error",
  "error_message": "Description of what went wrong"
}
```

Validation covers:

- Missing config file
- Invalid YAML
- Missing required config fields
- Invalid `seed`, `window`, or `version`
- Missing input CSV
- Unreadable CSV
- Empty CSV
- Missing `close` column
- Non-numeric values in `close`
- Too few rows for the configured rolling window

Failures are logged to `run.log` and return a non-zero exit code.

## Implementation notes

The rolling mean is computed using only the `close` column. The first `window - 1` rows have `NaN` rolling means and are excluded from the signal-rate calculation. For valid rows:

```text
signal = 1 if close > rolling_mean else 0
```

The final metric is the average signal value across valid signal rows.

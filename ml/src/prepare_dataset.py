"""Dataset preparation CLI for Naseej (Phase 2).

Examples:

    # Sample 100k rows from the full HI-Small CSV, write parquet.
    python ml/src/prepare_dataset.py \
        --input ml/data/raw/HI-Small_Trans.csv \
        --output ml/data/processed/transactions_sample.parquet \
        --sample 100000

    # Smaller CSV sample for the test suite / demos.
    python ml/src/prepare_dataset.py \
        --input ml/data/raw/HI-Small_Trans.csv \
        --output ml/data/samples/transactions_demo.csv \
        --sample 5000
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import data_loader, preprocessing

logger = logging.getLogger("naseej.prepare_dataset")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Prepare AML synthetic transactions for Naseej.")
    p.add_argument("--input", required=True, help="Path to raw transactions CSV / parquet.")
    p.add_argument("--output", required=True, help="Path to write the processed file (csv or parquet).")
    p.add_argument("--sample", type=int, default=100_000, help="Sampled row count. Use 0 for full dataset.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--salt", default="naseej", help="Salt used when hashing account IDs.")
    p.add_argument("--keep-raw-accounts", action="store_true",
                   help="Retain raw account columns (default: drop for zero-PII posture).")
    p.add_argument("--report", default=None,
                   help="Optional path to write a JSON ingestion report.")
    return p


def run(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_arg_parser().parse_args(argv)

    in_path = Path(args.input)
    out_path = Path(args.output)

    df = data_loader.load_transactions(in_path)
    df = data_loader.normalize_columns(df)
    schema_report = data_loader.validate_schema(df, strict=True)

    if args.sample and args.sample > 0:
        df = data_loader.sample_transactions(df, n=args.sample, seed=args.seed)

    processed = preprocessing.build_processed_table(
        df,
        salt=args.salt,
        drop_raw_accounts=not args.keep_raw_accounts,
    )
    processed = preprocessing.select_default_columns(processed)

    data_loader.save_processed(processed, out_path)

    report = {
        "input": str(in_path),
        "output": str(out_path),
        "rows_in": schema_report["row_count"],
        "rows_out": int(len(processed)),
        "sampled": bool(args.sample),
        "sample_target": args.sample,
        "prevalence_label": preprocessing.prevalence(processed, "label"),
        "columns_out": list(processed.columns),
        "schema": schema_report,
        "drop_raw_accounts": not args.keep_raw_accounts,
        "salt_used": bool(args.salt),
    }
    logger.info("Prepared dataset: %s rows out, prevalence=%.5f",
                report["rows_out"], report["prevalence_label"])

    if args.report:
        rp = Path(args.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logger.info("Wrote ingestion report -> %s", rp)
    else:
        sys.stdout.write(json.dumps(report, indent=2) + "\n")

    return 0


def main() -> int:
    return run()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

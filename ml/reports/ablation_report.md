# Feature Ablation — Naseej ML Evaluation

- Generated: 2026-06-13T10:08:06Z  ·  Model family: `random_forest`

| Feature set | #Features | test PR-AUC | Δ vs transaction_only | test ROC-AUC | F1 | Recall |
|---|---|---|---|---|---|---|
| transaction_only | 10 | 0.0766 | +0.0000 | 0.8854 | 0.1579 | 0.1858 |
| graph | 18 | 0.1790 | +0.1024 | 0.9328 | 0.2349 | 0.2197 |
| graph_context | 30 | 0.5548 | +0.4782 | 0.9694 | 0.5388 | 0.5227 |
| full_with_account_ids | 32 | 0.5740 | +0.4974 | 0.9658 | 0.5580 | 0.5426 |

- **transaction_only** — Amount, currency/payment-format encodings, bank ids, cross-bank flags, time-of-day fields.
- **graph** — transaction_only + point-in-time degree/history features (counts, sums, unique counterparties, fan-in/fan-out scores).
- **graph_context** — graph + point-in-time context features (1h/24h rolling windows, account-pair first-seen history, sweep ratio, rapid-movement flag).
- **full_with_account_ids** — graph_context + account-identifier encodings (as used by the deployed baseline; flags identity-memorisation lift).

All graph/context features are point-in-time (strictly-before cumulative and trailing-window semantics from ml/scripts/build_graph_features.py); no feature uses future transactions. Live feature-store context (backend /api/features) remains online-only; these offline equivalents follow the same point-in-time discipline.

full_with_account_ids adds account-identifier encodings as used by the deployed baseline. Lift over graph_context is attributable to account-identity memorisation and would not transfer to unseen accounts.

> Research prototype evaluated on the synthetic AMLworld HI-Small benchmark. Not production validation. Accuracy is intentionally not reported: at ~0.1% laundering prevalence a model that alerts on nothing is 99.9% accurate and useless.

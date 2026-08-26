# IPO evaluation set

## Current benchmark status

| Split | Case | Manifest | Human-verified labels |
|---|---|---:|---:|
| development | Hosonsoft | yes | 8 metrics + 6 findings |
| validation | Yonyou | yes | pending |
| test | Jingze | yes | pending |
| test | Topstar | yes | pending |

Only Hosonsoft currently supports quantitative scoring. The other manifests
reserve company and split boundaries but **must not** be presented as measured
test performance until their labels are independently verified. This is a
deliberate anti-leakage rule, not a claim of four-case accuracy.

This directory stores versioned case metadata and human-verified gold labels.
Prospectus PDFs and generated predictions are deliberately excluded from Git.

Splits:

- `development`: Hosonsoft, used while changing extraction rules.
- `validation`: Yonyou, used for tuning without touching the test cases.
- `test`: Jingze and Topstar, reserved for final reporting.

Generate deterministic review candidates:

```powershell
python scripts/eval_prepare_case.py --case evaluation/cases/hosonsoft.json --pdf <PDF> --output work/eval/hosonsoft_candidates.json
```

Only labels with `status: verified` are included in scoring. Test cases reject
candidate labels, preventing provisional machine output from becoming gold data.

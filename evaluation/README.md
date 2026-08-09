# IPO evaluation set

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

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Set

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _normalize_col_map(columns: Iterable[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for c in columns:
        key = re.sub(r"\s+", " ", str(c).strip().lower())
        mapping[key] = str(c)
    return mapping


def _pick_col(col_map: Dict[str, str], *candidates: str) -> str:
    for c in candidates:
        key = re.sub(r"\s+", " ", c.strip().lower())
        if key in col_map:
            return col_map[key]
    raise KeyError(f"Missing required column. Tried: {candidates}")


def _norm_label(value: str) -> str:
    txt = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return txt


def _split_csv_labels(value: str) -> Set[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return set()
    parts = [p.strip() for p in str(value).split(",")]
    return {_norm_label(p) for p in parts if _norm_label(p)}


def _extract_price_number(price_obj: Dict) -> float | None:
    if not isinstance(price_obj, dict):
        return None
    label = str(price_obj.get("label", "") or "")
    clean = label.replace(",", "")

    # Prefer the Inc. VAT linked amount when multiple prices exist in one label.
    inc_vat_patterns = [
        r"([0-9]+(?:\.[0-9]{1,2})?)\s*inc\.?\s*vat",
        r"inc\.?\s*vat[^0-9]*([0-9]+(?:\.[0-9]{1,2})?)",
    ]
    for pat in inc_vat_patterns:
        m_inc = re.search(pat, clean, flags=re.I)
        if m_inc:
            try:
                return float(m_inc.group(1))
            except Exception:
                pass

    m = re.search(r"([0-9]+(?:\.[0-9]{1,2})?)", clean)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _collect_actual_labels(inputs: List[Dict]) -> Set[str]:
    labels: Set[str] = set()
    for item in inputs or []:
        label = _norm_label(item.get("label", ""))
        if label:
            labels.add(label)
        group_label = _norm_label(item.get("group_label", ""))
        if group_label:
            labels.add(group_label)
    return labels


def _to_csv(items: Iterable[str]) -> str:
    vals = sorted({x for x in items if x})
    return ", ".join(vals)


def _run_report(input_xlsx: Path, sheet: str, output_xlsx: Path, limit: int | None) -> Dict[str, int]:
    # Import here to avoid startup cost when only checking args/help.
    from playwright_input_labels import get_inputs

    df = pd.read_excel(input_xlsx, sheet_name=sheet)
    col_map = _normalize_col_map(df.columns)

    url_col = _pick_col(col_map, "url")
<<<<<<< HEAD
    expected_price_col = _pick_col(col_map, "expected_price", "expected_price ")
=======
    expected_price_col = _pick_col(
        col_map,
        "expected_price_incl_vat",
        "expected_price_incl_vat ",
        # Backward-compatible fallback for older sheets.
        "expected_price",
        "expected_price ",
    )
>>>>>>> 22d44e23b866688259d5fdb858bdca24e56fbe03
    expected_labels_col = _pick_col(col_map, "expected_labels_csv")
    active_col = col_map.get("active")
    site_col = col_map.get("site")
    sl_col = col_map.get("sl#", "sl#")

    rows: List[Dict] = []
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    work_df = df
    if limit is not None and limit > 0:
        work_df = df.head(limit)

    for _, row in work_df.iterrows():
        if active_col:
            active_val = row.get(active_col)
            if str(active_val).strip() in {"0", "false", "False", "no", "No"}:
                continue

        url = str(row.get(url_col, "") or "").strip()
        if not url:
            continue

        expected_price = row.get(expected_price_col)
        expected_price_val = None
        if expected_price is not None and not (isinstance(expected_price, float) and pd.isna(expected_price)):
            try:
                expected_price_val = float(expected_price)
            except Exception:
                expected_price_val = None

        expected_labels = _split_csv_labels(row.get(expected_labels_col))

        actual_price_val = None
        actual_price_label = ""
        actual_labels: Set[str] = set()
        error = ""
        try:
            data = get_inputs(url)
            price_obj = data.get("price")
            if isinstance(price_obj, dict):
                actual_price_label = str(price_obj.get("label", "") or "")
            actual_price_val = _extract_price_number(price_obj)
            actual_labels = _collect_actual_labels(data.get("inputs", []))
        except Exception as exc:
            error = str(exc)

        if expected_price_val is None:
            price_status = "NO_EXPECTED"
        elif actual_price_val is None:
            price_status = "NO_PRICE"
        else:
            price_status = "PASS" if abs(actual_price_val - expected_price_val) < 0.01 else "FAIL"

        if not expected_labels:
            labels_status = "NO_EXPECTED"
            missing_labels = set()
        else:
            missing_labels = expected_labels - actual_labels
            labels_status = "PASS" if not missing_labels else "FAIL"

        final_status = "PASS" if price_status == "PASS" and labels_status in {"PASS", "NO_EXPECTED"} and not error else "FAIL"

        rows.append(
            {
                "sl#": row.get(sl_col) if sl_col in row else "",
                "site": row.get(site_col, "") if site_col else "",
                "url": url,
<<<<<<< HEAD
                "expected_price": expected_price_val,
=======
                "expected_price_incl_vat": expected_price_val,
>>>>>>> 22d44e23b866688259d5fdb858bdca24e56fbe03
                "actual_price": actual_price_val,
                "actual_price_label": actual_price_label,
                "price_status": price_status,
                "expected_labels_csv": _to_csv(expected_labels),
                "actual_labels_csv": _to_csv(actual_labels),
                "missing_labels_csv": _to_csv(missing_labels),
                "labels_status": labels_status,
                "final_status": final_status,
                "error": error,
                "run_at_utc": run_at,
            }
        )

    results_df = pd.DataFrame(rows)
    summary = {
        "total_rows": int(len(results_df)),
        "pass_rows": int((results_df["final_status"] == "PASS").sum()) if not results_df.empty else 0,
        "fail_rows": int((results_df["final_status"] == "FAIL").sum()) if not results_df.empty else 0,
        "no_price_rows": int((results_df["price_status"] == "NO_PRICE").sum()) if not results_df.empty else 0,
        "label_fail_rows": int((results_df["labels_status"] == "FAIL").sum()) if not results_df.empty else 0,
    }
    summary_df = pd.DataFrame([summary])

    output_xlsx.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        results_df.to_excel(writer, sheet_name="results", index=False)
        summary_df.to_excel(writer, sheet_name="summary", index=False)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate input-controls test report from expected Excel data.")
    parser.add_argument(
        "--input",
        default=str(_project_root() / "data" / "expected" / "input_controls_expected.xlsx"),
        help="Path to expected workbook.",
    )
    parser.add_argument("--sheet", default="Sheet1", help="Input sheet name.")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit for dry runs.")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional explicit output workbook path. Default: data/results/input_controls_results_<timestamp>.xlsx",
    )
    args = parser.parse_args()

    input_xlsx = Path(args.input).resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_output = _project_root() / "data" / "results" / f"input_controls_results_{stamp}.xlsx"
    output_xlsx = Path(args.output).resolve() if args.output else default_output

    summary = _run_report(input_xlsx=input_xlsx, sheet=args.sheet, output_xlsx=output_xlsx, limit=args.limit)
    print(f"Output file: {output_xlsx}")
    print(
        "Summary: "
        f"total={summary['total_rows']} "
        f"pass={summary['pass_rows']} "
        f"fail={summary['fail_rows']} "
        f"no_price={summary['no_price_rows']} "
        f"label_fail={summary['label_fail_rows']}"
    )


if __name__ == "__main__":
    main()

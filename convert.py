import json
import csv
from pathlib import Path
import argparse
from typing import Any, Dict, List, Optional


def _flatten(obj: Any, parent_key: str = "", sep: str = ".", list_sep: str = "; ") -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            items.update(_flatten(v, new_key, sep=sep, list_sep=list_sep))
    elif isinstance(obj, list):
        # If list contains only primitives, join them; otherwise serialize the whole list
        if all(not isinstance(x, (dict, list)) for x in obj):
            items[parent_key] = list_sep.join("" if x is None else str(x) for x in obj)
        else:
            items[parent_key] = json.dumps(obj, ensure_ascii=False)
    else:
        items[parent_key] = obj
    return items


def _rows_from_value(value: Any) -> List[Dict[str, Any]]:
    """
    Normalize a top-level value into a list of dict rows.
    - If value is a list of dicts -> return as-is
    - If value is a single dict -> return [dict]
    - If value is a list of non-dicts -> represent each item as {'value': item}
    - Otherwise -> [{'value': value}]
    """
    if isinstance(value, list):
        if all(isinstance(x, dict) for x in value):
            return value  # list of dict rows
        else:
            # list of primitives -> create rows with single key 'value'
            return [{"value": x} for x in value]
    elif isinstance(value, dict):
        return [value]
    else:
        return [{"value": value}]


def convert_top_level_json_to_csvs(
    json_path: str,
    out_dir: Optional[str] = None,
    flatten_sep: str = ".",
    list_sep: str = "; ",
    encoding: str = "utf-8",
    verbose: bool = False,
) -> List[str]:
    """
    Read a JSON file that contains a top-level object with keys like 'shipments', 'waybills', etc.
    For each top-level key whose value is a list or dict, write a CSV file named <key>.csv
    in `out_dir` (defaults to the same directory as the JSON file).

    Returns a list of written CSV paths.
    """
    json_path = Path(json_path)
    if out_dir:
        out_dir = Path(out_dir)
    else:
        out_dir = json_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    text = json_path.read_text(encoding=encoding)
    data = json.loads(text)

    if not isinstance(data, dict):
        raise ValueError("Top-level JSON must be an object/dict with named sections.")

    written_files: List[str] = []

    for key, value in data.items():
        rows_raw = _rows_from_value(value)
        if not rows_raw:
            if verbose:
                print(f"Skipping empty section '{key}'")
            continue

        # Flatten rows and collect column order (union preserving first-seen order)
        flat_rows: List[Dict[str, Any]] = []
        seen_cols: List[str] = []
        for r in rows_raw:
            flat = _flatten(r, sep=flatten_sep, list_sep=list_sep)
            # normalize values: None -> "", non-primitive -> json dumps
            for k, v in list(flat.items()):
                if v is None:
                    flat[k] = ""
                elif not isinstance(v, (str, int, float, bool)):
                    flat[k] = json.dumps(v, ensure_ascii=False)
            flat_rows.append(flat)
            for c in flat.keys():
                if c not in seen_cols:
                    seen_cols.append(c)

        if not seen_cols:
            seen_cols = ["value"]

        csv_file = out_dir / f"{key}.csv"
        with csv_file.open("w", newline="", encoding=encoding) as f:
            writer = csv.DictWriter(f, fieldnames=seen_cols, extrasaction="ignore")
            writer.writeheader()
            for fr in flat_rows:
                row_out = {c: (fr.get(c, "") if fr.get(c, "") is not None else "") for c in seen_cols}
                writer.writerow(row_out)

        written_files.append(str(csv_file))
        if verbose:
            print(f"Wrote {len(flat_rows)} rows to {csv_file}")

    return written_files


def _cli():
    parser = argparse.ArgumentParser(description="Convert top-level JSON sections to per-section CSV files.")
    parser.add_argument("json_file", help="Input JSON file (top-level object with named arrays/dicts).")
    parser.add_argument("--out-dir", "-o", help="Output directory for CSV files (defaults to JSON file's folder).")
    parser.add_argument("--sep", default=".", help="Separator for nested keys (default '.')")
    parser.add_argument("--list-sep", default="; ", help="Separator for list items when flattened (default '; ')")
    parser.add_argument("--encoding", default="utf-8", help="File encoding (default utf-8)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    files = convert_top_level_json_to_csvs(
        args.json_file,
        out_dir=args.out_dir,
        flatten_sep=args.sep,
        list_sep=args.list_sep,
        encoding=args.encoding,
        verbose=args.verbose,
    )
    if args.verbose:
        print("Created files:")
        for p in files:
            print(" -", p)


if __name__ == "__main__":
    _cli()
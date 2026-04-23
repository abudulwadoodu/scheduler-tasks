import os
import sys
import importlib.util
import pandas as pd
import asyncio
from generate_expression import run_step2_and_3_on_dataset_v2, structured_model

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # module level, before all functions


def load_scrape_function(script_path: str):
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Module not found: {script_path}")

    module_name = os.path.splitext(os.path.basename(script_path))[0]
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "scrape_price"):
        raise AttributeError(f"'scrape_price' function not found in {script_path}")

    return module.scrape_price


def run_extraction(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "ExtractedPrice" not in df.columns:
        df["ExtractedPrice"] = None

    for idx, row in df.iterrows():
        script_path = row.get("ScriptPath")
        url         = row.get("URL")
        description = row.get("Description")
        comment     = row.get("Comment", "")

        if not script_path or not isinstance(script_path, str):
            print(f"[SKIP] Row {idx}: missing or invalid ScriptPath")
            continue

        if not url or not description:
            print(f"[SKIP] Row {idx}: missing URL or Description")
            continue

        # ── THIS was the bug: now uses BASE_DIR instead of relative path ──────
        if not os.path.isabs(script_path):
            script_path = os.path.join(BASE_DIR, "extractor_modules", script_path)

        try:
            scrape_price = load_scrape_function(script_path)
            result = scrape_price(url=url, description=description, comment=comment)
            df.at[idx, "ExtractedPrice"] = result.get("extracted_price")
            print(f"[OK]   Row {idx}: £{result.get('extracted_price')} — {url}")

        except FileNotFoundError as e:
            print(f"[ERROR] Row {idx}: {e}")
        except AttributeError as e:
            print(f"[ERROR] Row {idx}: {e}")
        except Exception as e:
            print(f"[ERROR] Row {idx}: {url} → {e}")

    return df

def run_generate_math_experession(df :  pd.DataFrame) -> pd.DataFrame:
    output = asyncio.run(run_step2_and_3_on_dataset_v2(
        dataset=df,
        structured_model=structured_model,
        semaphore_limit=5,
    ))
     
    return output     

if __name__ == "__main__":
    input_path  = os.path.join(BASE_DIR, "input_data", "scenario_1.xlsx")
    output_path = os.path.join(BASE_DIR, "output", "scenario_1.xlsx")

    os.makedirs(os.path.join(BASE_DIR, "output"), exist_ok=True)

    df = pd.read_excel(input_path)
    result_df = run_extraction(df[:2])
    output_df = run_generate_math_experession(result_df)
    output_df.to_excel(output_path, index=False)
    print(output_df[["URL", "ScriptPath", "ExtractedPrice","FinalPrice"]])
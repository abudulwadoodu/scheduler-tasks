"""
LangChain-enabled version: uses GPT-4.1-mini vision to filter price-relevant controls.
Requires: OPENAI_API_KEY in .env, langchain-openai, langchain-core.
"""
import json
import os
import base64
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
load_dotenv()

from PIL import Image
from playwright.sync_api import sync_playwright

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
except Exception:
    ChatOpenAI = None
    HumanMessage = None

# Import shared logic from base module
from playwright_input_labels import (
    _clean_text,
    _rect_from_dict,
    _distance_score,
    _hard_exclude_result,
    get_price_element,
    get_inputs as get_inputs_base,
)


def _manual_output_path(url: str, suffix: str) -> Path:
    parsed = urlparse((url or "").strip())
    host = re.sub(r"[^a-z0-9]+", "-", (parsed.netloc or "site").lower()).strip("-")
    path_part = re.sub(r"[^a-z0-9]+", "-", (parsed.path or "/").lower()).strip("-")
    slug = f"{host}-{path_part}" if path_part else host
    slug = slug[:120] if len(slug) > 120 else slug
    root = Path(__file__).resolve().parent
    out_dir = root / "data" / "results" / "playwright_manual_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{slug}{suffix}"


def _crop_to_base64(image_path: str, bbox: Dict[str, float], pad: int = 120) -> str:
    with Image.open(image_path) as im:
        w, h = im.size
        l = max(0, int(bbox["left"] - pad))
        t = max(0, int(bbox["top"] - pad))
        r = min(w, int(bbox["right"] + pad))
        b = min(h, int(bbox["bottom"] + pad))
        crop = im.crop((l, t, r, b))
        buf = BytesIO()
        crop.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")


def _nearby_ocr_boxes(
    bbox_ss: Dict[str, float], text_nodes: List[Dict[str, Any]], max_boxes: int = 30
) -> List[Dict[str, Any]]:
    b = _rect_from_dict(bbox_ss)
    if not b:
        return []
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for n in text_nodes:
        r = n.get("rect_ss")
        rr = _rect_from_dict(r)
        if not rr:
            continue
        score = _distance_score(b, rr)
        scored.append((score, {"text": n.get("text", ""), "bbox": r}))
    scored.sort(key=lambda x: x[0])
    return [x[1] for x in scored[:max_boxes]]


def filter_price_inputs_with_llm(
    results: List[Dict[str, Any]],
    screenshot_path: str,
    text_nodes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Final quality gate: use LLM vision to keep only true product option controls
    and improve label/group_label assignment.
    Falls back to deterministic results when model/api is unavailable.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or ChatOpenAI is None or HumanMessage is None:
        return [r for r in results if not _hard_exclude_result(r)]

    model_name = os.getenv("UI_LLM_MODEL", "gpt-4.1-mini")
    llm = ChatOpenAI(model=model_name, temperature=0)

    refined: List[Dict[str, Any]] = []
    for idx, item in enumerate(results):
        if _hard_exclude_result(item):
            continue
        bbox_ss = item.get("_bbox_ss")
        if not bbox_ss:
            refined.append(item)
            continue

        nearby = _nearby_ocr_boxes(bbox_ss, text_nodes)
        img_b64 = _crop_to_base64(screenshot_path, bbox_ss, pad=140)

        payload = {
            "control_id": f"ctrl_{idx}",
            "tag": item.get("tag", ""),
            "type": item.get("type", ""),
            "name": item.get("name", ""),
            "id": item.get("id", ""),
            "label": item.get("label", ""),
            "group_label": item.get("group_label", ""),
            "bbox": bbox_ss,
        }

        prompt = f"""
You are validating one UI control from a product configurator screenshot.
Return STRICT JSON ONLY with keys:
control_id,label,group_label,is_option_control,is_price_relevant,confidence,reason

Control metadata:
{json.dumps(payload, ensure_ascii=False)}

Nearby OCR boxes:
{json.dumps(nearby, ensure_ascii=False)}

Rules:
1) Keep only real product option controls that affect pricing/configuration.
2) Reject reward/points/search/login/coupon/address/stepper/add-minus controls.
3) Prefer visible label text nearest left/above/same-row to the control.
4) If uncertain, set is_option_control=false.
"""
        try:
            msg = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                ]
            )
            resp = llm.invoke([msg])
            raw = resp.content if isinstance(resp.content, str) else str(resp.content)
            parsed = json.loads(raw)
            if not parsed.get("is_option_control", False):
                continue
            if not parsed.get("is_price_relevant", True):
                continue

            lbl = _clean_text(parsed.get("label"))
            grp = _clean_text(parsed.get("group_label"))
            if lbl:
                item["label"] = lbl
            if grp:
                item["group_label"] = grp
            refined.append(item)
        except Exception:
            refined.append(item)

    return refined


def get_inputs(url: str) -> Dict[str, Any]:
    """Same as base get_inputs but uses LLM vision for final filtering.

    Returns: {"price": {...price element metadata...}, "inputs": [...]}
    """
    data = get_inputs_base(url, final_filter=filter_price_inputs_with_llm)

    # If base extraction returns null price (intermittent on some sites), re-run
    # the exact base price detector in a lightweight recovery pass.
    if not isinstance(data.get("price"), dict):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    device_scale_factor=1,
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                )
                page = context.new_page()
                page.set_default_navigation_timeout(120_000)
                page.set_default_timeout(60_000)
                page.goto(url, wait_until="load", timeout=120_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=30_000)
                except Exception:
                    pass

                recovered = get_price_element(page)
                if recovered:
                    price_rect = recovered.get("rect") or {}
                    data["price"] = {
                        "label": _clean_text(recovered.get("text")),
                        "tag": _clean_text(recovered.get("tag")),
                        "type": "",
                        "name": _clean_text(recovered.get("name")),
                        "id": _clean_text(recovered.get("id")),
                        "class_name": _clean_text(recovered.get("class_name")),
                        "bbox": {
                            "left": float(price_rect.get("left", 0.0)),
                            "top": float(price_rect.get("top", 0.0)),
                            "right": float(price_rect.get("right", 0.0)),
                            "bottom": float(price_rect.get("bottom", 0.0)),
                        },
                    }
                browser.close()
        except Exception:
            pass

    # Defensive normalization: keep current/final displayed price if promo text leaks in.
    price = data.get("price")
    if isinstance(price, dict):
        label = _clean_text(price.get("label"))
        if label:
            now_match = re.search(r"\bnow\b[^£$€\d]{0,20}([£$€]\s*\d[\d,.]*)", label, flags=re.I)
            if now_match:
                price["label"] = _clean_text(now_match.group(1))
            elif re.search(r"\b(was|rrp|save|saving)\b", label, flags=re.I):
                money = re.search(r"[£$€]\s*\d[\d,.]*", label)
                if money:
                    price["label"] = _clean_text(money.group(0))
        data["price"] = price

    return data


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python playwright_input_labels_langchain.py <url>")
        raise SystemExit(2)

    target_url = sys.argv[1]
    data = get_inputs(target_url)
    out_path = _manual_output_path(target_url, "_labels_langchain.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(json.dumps(data, indent=2, ensure_ascii=False))

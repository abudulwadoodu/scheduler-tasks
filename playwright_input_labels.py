import json
import os
import re
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from playwright.sync_api import ElementHandle, sync_playwright

from PIL import Image
from PIL import ImageDraw


_WHITESPACE_RE = re.compile(r"\s+")


def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return _WHITESPACE_RE.sub(" ", value).strip()


def _clean_candidate(value: Optional[str]) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    # ignore long paragraphs / blocks
    if len(text) > 100:
        return ""
    return text


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def cx(self) -> float:
        return (self.left + self.right) / 2

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2


def _rect_from_dict(d: Optional[Dict[str, Any]]) -> Optional[Rect]:
    if not d:
        return None
    try:
        return Rect(float(d["left"]), float(d["top"]), float(d["right"]), float(d["bottom"]))
    except Exception:
        return None


def _distance_score(input_rect: Rect, text_rect: Rect) -> float:
    # Prefer same row and to-the-right. Score = dx + 2*dy (as requested)
    dy = abs(text_rect.cy - input_rect.cy)
    if text_rect.left >= input_rect.right - 2:
        dx = max(0.0, text_rect.left - input_rect.right)
    else:
        dx = max(0.0, input_rect.left - text_rect.right) * 3.0
    score = dx + (dy * 2.0)
    if dy < 20:
        score *= 0.5
    if text_rect.left >= input_rect.right - 2:
        score *= 0.85
    return score


def _looks_like_noise(text: str) -> bool:
    t = text.lower()
    if re.search(r"\b\S+@\S+\.[a-z]{2,}\b", text):
        return True
    if re.fullmatch(r"[0-9\s+().-]{8,}", text):
        return True
    if any(k in t for k in ["click here", "lead time", "free nationwide", "price promise"]):
        return True
    return False


def run_stamp(dt: Optional[datetime] = None) -> str:
    d = dt or datetime.now()
    return d.strftime("%Y%m%d_%H%M%S")


def screenshot_page(page, path: str) -> Tuple[int, int]:
    """
    Capture full-page screenshot (top-of-page) and return (width,height) in pixels.
    """
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(250)
    page.screenshot(path=path, full_page=True)
    with Image.open(path) as im:
        return im.size[0], im.size[1]


def ocr_text_boxes(image_path: str) -> List[Dict[str, Any]]:
    """
    OCR the screenshot and return list of {text, rect} in screenshot pixel coords.
    Requires EasyOCR (installed via pip).
    """
    import easyocr  # local import to avoid import cost when unused

    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    results = reader.readtext(image_path)
    out: List[Dict[str, Any]] = []
    for bbox, text, conf in results:
        txt = _clean_candidate(text)
        if not txt:
            continue
        if len(txt) > 50:
            continue
        if conf is not None and float(conf) < 0.35:
            continue
        if _looks_like_noise(txt):
            continue
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        rect = {
            "left": float(min(xs)),
            "top": float(min(ys)),
            "right": float(max(xs)),
            "bottom": float(max(ys)),
        }
        out.append({"text": txt, "rect": rect})
    return out


def get_price_element(page) -> Optional[Dict[str, Any]]:
    """
    Best-effort locate a visible price element and return its rect + text.
    """
    return page.evaluate(
        """() => {
          const clean = (t) => (t || '').replace(/\\s+/g,' ').trim();
          const visible = (el) => {
            if (!el || el.nodeType !== 1) return false;
            const s = getComputedStyle(el);
            if (s.display === 'none' || s.visibility === 'hidden') return false;
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
          };

          const selectors = [
            '.price',
            '[class*=\"price\"]',
            '#price',
            '[id*=\"price\"]',
            '[data-price]',
          ];
          const candidates = [];
          for (const sel of selectors) {
            for (const el of Array.from(document.querySelectorAll(sel))) {
              if (!visible(el)) continue;
              const t = clean(el.innerText || el.textContent || '');
              if (!t) continue;
              // must contain a currency-ish marker or digits
              if (!(/[£$€]/.test(t) || /\\b\\d+[\\d,.]*\\b/.test(t))) continue;
              const r = el.getBoundingClientRect();
              candidates.push({ el, t, r });
            }
          }
          if (!candidates.length) return null;
          // pick the smallest (often the actual price value), bias towards top area
          candidates.sort((a,b) => {
            const aArea = a.r.width * a.r.height;
            const bArea = b.r.width * b.r.height;
            if (aArea !== bArea) return aArea - bArea;
            return a.r.top - b.r.top;
          });
          const best = candidates[0];
          return {
            text: best.t,
            rect: { left: best.r.left, top: best.r.top, right: best.r.right, bottom: best.r.bottom },
          };
        }"""
    )


def get_all_inputs(page) -> List[ElementHandle]:
    return page.query_selector_all("input, select, textarea")


def _get_visual_proxy_rect(el: ElementHandle) -> Optional[Rect]:
    """
    Return the rect of the thing the user actually sees/clicks for this control.
    - If element is visible: its rect
    - If hidden: nearest visible proxy (label, sibling, parent wrapper)
    """
    rect = el.evaluate(
        """(el) => {
          const isActuallyVisible = (node) => {
            if (!node || node.nodeType !== 1) return false;
            // Walk ancestors: if any ancestor hides it, it's not visible to the user.
            let cur = node;
            while (cur) {
              const s = window.getComputedStyle(cur);
              if (s.display === 'none' || s.visibility === 'hidden') return false;
              if (parseFloat(s.opacity || '1') === 0) return false;
              cur = cur.parentElement;
            }
            // Must have on-screen geometry.
            if (!node.getClientRects || node.getClientRects().length === 0) return false;
            const r = node.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
          };
          const rectOf = (node) => {
            const r = node.getBoundingClientRect();
            return { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
          };

          if (isActuallyVisible(el)) return rectOf(el);

          const proxies = [];
          const lab = el.closest('label');
          if (lab) proxies.push(lab);
          // Only consider parent as proxy if it's itself a label-like wrapper.
          if (el.parentElement && el.parentElement.tagName && el.parentElement.tagName.toLowerCase() === 'label') {
            proxies.push(el.parentElement);
          }
          if (el.previousElementSibling) proxies.push(el.previousElementSibling);
          if (el.nextElementSibling) proxies.push(el.nextElementSibling);

          for (const p of proxies) {
            if (p && isActuallyVisible(p)) return rectOf(p);
          }

          return null;
        }"""
    )
    return _rect_from_dict(rect)


def find_visual_label_match(
    input_el: ElementHandle, text_nodes: List[Dict[str, Any]]
) -> Tuple[str, Optional[Dict[str, float]]]:
    input_rect = _get_visual_proxy_rect(input_el)
    if not input_rect:
        return "", None

    tag = (input_el.evaluate("el => el.tagName") or "").lower()
    input_type = _clean_text(input_el.get_attribute("type")).lower()

    def overlaps(a: Rect, b: Rect) -> bool:
        left = max(a.left, b.left)
        right = min(a.right, b.right)
        top = max(a.top, b.top)
        bottom = min(a.bottom, b.bottom)
        if right <= left or bottom <= top:
            return False
        inter = (right - left) * (bottom - top)
        area_b = max(1.0, (b.right - b.left) * (b.bottom - b.top))
        return (inter / area_b) > 0.5

    best: Tuple[float, str] = (float("inf"), "")
    best_rect_ss: Optional[Dict[str, float]] = None
    for item in text_nodes:
        t = _clean_candidate(item.get("text"))
        if not t:
            continue
        r = _rect_from_dict(item.get("rect"))
        if not r:
            continue

        # Avoid picking text that is effectively "inside" the control (e.g. selected value in a <select>).
        if overlaps(input_rect, r):
            continue

        score = _distance_score(input_rect, r)
        # prefer very short label-like strings
        if len(t) <= 30:
            score *= 0.9
        # For selects/text inputs, labels are commonly above/left; slightly penalize far-right text.
        if tag in {"select"} or (tag == "input" and input_type in {"text", "number"}):
            if r.left >= input_rect.right:
                score *= 1.15
        if score < best[0]:
            best = (score, t)
            best_rect_ss = item.get("rect_ss")
    return best[1], best_rect_ss


def find_visual_label(input_el: ElementHandle, text_nodes: List[Dict[str, Any]]) -> str:
    return find_visual_label_match(input_el, text_nodes)[0]


def is_price_relevant(
    input_el: ElementHandle,
    label: str,
    group_label: str,
    price: Optional[Dict[str, Any]],
) -> bool:
    """
    Heuristic: include product option controls, exclude generic site/search/login/contact/etc.
    Also prefer controls spatially near the price element if one is found.
    """
    label_l = (label or "").lower()
    group_l = (group_label or "").lower()
    name_l = (_clean_text(input_el.get_attribute("name"))).lower()
    id_l = (_clean_text(input_el.get_attribute("id"))).lower()

    hay = " ".join([label_l, group_l, name_l, id_l])

    excluded = [
        "search",
        "filter",
        "sort",
        "login",
        "sign in",
        "email",
        "password",
        "phone",
        "address",
        "shipping",
        "billing",
        "coupon",
        "promo",
        "voucher",
        "qty",
        "quantity",
        "add to cart",
        "submit",
        "newsletter",
        "contact",
    ]
    if any(k in hay for k in excluded):
        return False

    included = [
        "size",
        "thickness",
        "width",
        "height",
        "length",
        "colour",
        "color",
        "finish",
        "material",
        "type",
        "option",
        "variant",
        "rating",
        "glass",
        "frame",
        "insulation",
        "energy",
        "cill",
        "hinge",
        "handle",
        "trickle",
    ]

    score = 0.0
    if any(k in hay for k in included):
        score += 3.0
    if group_l and any(k in group_l for k in ["option", "variant", "configuration", "glazing", "rating", "colour", "color"]):
        score += 2.0

    # Prefer inputs near the price (above/near it)
    if price and price.get("rect"):
        price_rect = _rect_from_dict(price.get("rect"))
        input_rect = _get_visual_proxy_rect(input_el)
        if price_rect and input_rect:
            dx = abs(input_rect.cx - price_rect.cx)
            dy = abs(input_rect.cy - price_rect.cy)
            dist = dx + dy
            if dist < 600:
                score += 2.0
            if input_rect.top <= price_rect.bottom + 50:
                score += 1.0

    # Select/radio/checkbox are often price-relevant; plain text fields usually not (unless keyword hit)
    tag = (input_el.evaluate("el => el.tagName") or "").lower()
    itype = (_clean_text(input_el.get_attribute("type"))).lower()
    if tag == "select" or itype in {"radio", "checkbox"}:
        score += 1.5
    if itype in {"text", "email", "tel", "password"}:
        score -= 1.0

    return score >= 3.0


def extract_label(element: ElementHandle) -> Dict[str, str]:
    """
    Extract a meaningful label for an input/select/textarea plus an optional group label.

    Label priority:
      a) <label for="id">
      b) wrapped/parent <label> (direct visible text nodes only)
      c) aria-label
      d) placeholder
      e) name attribute
      f) nearby/visually-associated text (small/span/short div, etc.)
    """
    group_label = ""
    input_type = (element.get_attribute("type") or "").lower()

    group_label_js = element.evaluate(
        """(el) => {
          const isVisible = (node) => {
            if (!node || node.nodeType !== 1) return false;
            const style = window.getComputedStyle(node);
            if (style.visibility === 'hidden' || style.display === 'none') return false;
            const rect = node.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          };

          const clean = (t) => (t || '').replace(/\\s+/g, ' ').trim();

          const isHeadingCandidate = (node) => {
            if (!node || node.nodeType !== 1) return false;
            const tag = node.tagName.toLowerCase();
            if (/^h[1-6]$/.test(tag)) return true;
            const cls = (node.getAttribute('class') || '').toLowerCase();
            if (/(^|\\s)h[1-6](\\s|$)/.test(cls)) return true;
            if (/(^|\\s)(title|heading|section-title|section_heading)(\\s|$)/.test(cls)) return true;
            return false;
          };

          const pick = (node) => {
            if (!node || !isVisible(node)) return '';
            const t = clean(node.innerText || node.textContent || '');
            if (!t) return '';
            if (t.length > 100) return '';
            return t;
          };

          // Search previous siblings of ancestors for a heading-like element.
          let cur = el;
          for (let depth = 0; depth < 6 && cur; depth++) {
            const parent = cur.parentElement;
            if (!parent) break;
            let sib = parent.previousElementSibling;
            let steps = 0;
            while (sib && steps < 8) {
              if (isHeadingCandidate(sib)) {
                const t = pick(sib);
                if (t) return t;
              }
              // Sometimes headings are nested in wrappers.
              const nested = sib.querySelector && sib.querySelector('h1,h2,h3,h4,h5,h6,.h1,.h2,.h3,.h4,.h5,.h6,.title,.heading,.section-title,.section_heading');
              if (nested) {
                const t = pick(nested);
                if (t) return t;
              }
              sib = sib.previousElementSibling;
              steps++;
            }
            cur = parent;
          }
          return '';
        }"""
    )
    group_label = _clean_candidate(group_label_js)

    # a) <label for="id">
    label_for = element.evaluate(
        """(el) => {
          const id = el.getAttribute('id');
          if (!id) return '';
          const esc = (window.CSS && CSS.escape) ? CSS.escape(id) : id.replace(/["\\\\]/g, '\\\\$&');
          const lab = el.ownerDocument.querySelector(`label[for="${esc}"]`);
          return lab ? (lab.innerText || lab.textContent || '') : '';
        }"""
    )
    label_for = _clean_candidate(label_for)
    if label_for:
        return {"label": label_for, "group_label": group_label}

    # b) parent <label> (wrapped)
    wrapped_label = element.evaluate(
        """(el) => {
          const lab = el.closest('label');
          if (!lab) return '';

          const isVisibleEl = (node) => {
            if (!node || node.nodeType !== 1) return false;
            const style = window.getComputedStyle(node);
            if (style.visibility === 'hidden' || style.display === 'none') return false;
            const rect = node.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          };

          // Take only *direct* text nodes of the label so we avoid icon <i>, wrappers, etc.
          const parts = [];
          for (const child of Array.from(lab.childNodes)) {
            if (child === el) continue;
            if (child.nodeType === Node.TEXT_NODE) {
              const t = (child.textContent || '').replace(/\\s+/g, ' ').trim();
              if (t) parts.push(t);
              continue;
            }
            if (child.nodeType === Node.ELEMENT_NODE) {
              const tag = child.tagName.toLowerCase();
              if (tag === 'input' || tag === 'select' || tag === 'textarea' || tag === 'button') continue;
              // allow common label text containers, but only if they are simple and visible
              if (!isVisibleEl(child)) continue;
              if (['span', 'small', 'strong', 'em', 'b'].includes(tag)) {
                const t = ((child.innerText || child.textContent || '')).replace(/\\s+/g, ' ').trim();
                if (t) parts.push(t);
              }
            }
          }
          return parts.join(' ').trim();
        }"""
    )
    wrapped_label = _clean_candidate(wrapped_label)
    if wrapped_label:
        return {"label": wrapped_label, "group_label": group_label}

    # c) aria-label
    aria_label = _clean_candidate(element.get_attribute("aria-label"))
    if aria_label:
        return {"label": aria_label, "group_label": group_label}

    # d) placeholder
    placeholder = _clean_candidate(element.get_attribute("placeholder"))
    if placeholder:
        return {"label": placeholder, "group_label": group_label}

    # Strong visual label detection for radio/checkbox options:
    # run bounding-box label search BEFORE falling back to "name".
    if input_type in {"radio", "checkbox"}:
        # Fast-path for common modern UI pattern:
        # <label> [hidden input] [icon wrapper] TEXT </label>
        wrapped_label_fast = element.evaluate(
            """(el) => {
              const lab = el.closest('label');
              if (!lab) return '';
              const parts = [];
              for (const child of Array.from(lab.childNodes)) {
                if (child.nodeType === Node.TEXT_NODE) {
                  const t = (child.textContent || '').replace(/\\s+/g, ' ').trim();
                  if (t) parts.push(t);
                }
              }
              return parts.join(' ').trim();
            }"""
        )
        wrapped_label_fast = _clean_candidate(wrapped_label_fast)
        if wrapped_label_fast:
            return {"label": wrapped_label_fast, "group_label": group_label}

        bbox_label = element.evaluate(
            """(el) => {
              const clean = (t) => (t || '').replace(/\\s+/g, ' ').trim();
              const isVisibleEl = (node) => {
                if (!node || node.nodeType !== 1) return false;
                const style = window.getComputedStyle(node);
                if (style.visibility === 'hidden' || style.display === 'none') return false;
                const rect = node.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              };

              const isIconLike = (node) => {
                if (!node || node.nodeType !== 1) return true;
                const tag = node.tagName.toLowerCase();
                if (['svg','img','i','path','use'].includes(tag)) return true;
                const cls = (node.getAttribute('class') || '').toLowerCase();
                if (cls.includes('icon') || cls.includes('fa-') || cls.includes('material-icons')) return true;
                return false;
              };

              const txt = (node) => clean(node.innerText || node.textContent || '');
              const isValidText = (t) => t && t.length <= 50;

              // Use the clickable proxy element for layout if the input itself is display:none.
              const proxy = el.closest('label') || el;
              const elRect = proxy.getBoundingClientRect();
              const elCy = (elRect.top + elRect.bottom) / 2;
              const elRight = elRect.right;

              // Limit the search to a nearby container, but expand outward if needed.
              // This handles patterns like: <small>Autumn</small> ... <label><input type=radio/></label>
              // where the text is not inside the <label>.
              const containers = [];
              const label = el.closest('label');
              if (label && label.parentElement) containers.push(label.parentElement);
              if (label && label.parentElement && label.parentElement.parentElement) containers.push(label.parentElement.parentElement);
              if (label) containers.push(label);
              if (el.parentElement) containers.push(el.parentElement);
              let cur = (label && label.parentElement) ? label.parentElement.parentElement : (el.parentElement && el.parentElement.parentElement);
              for (let depth = 0; depth < 4 && cur; depth++) {
                containers.push(cur);
                cur = cur.parentElement;
              }
              containers.push(el.ownerDocument.body);

              const collectCandidates = (container) => Array.from(
                container.querySelectorAll('span,small,div,label,p')
              ).filter((n) => {
                if (!isVisibleEl(n)) return false;
                if (n.contains(el)) return false;
                if (isIconLike(n)) return false;
                // ignore wrappers that contain other controls (usually not the label itself)
                if (n.querySelector('input,select,textarea,button')) return false;
                const t = txt(n);
                if (!isValidText(t)) return false;
                // ignore known unrelated UI text blocks / marketing CTAs
                if (/click here/i.test(t)) return false;
                if (/lead time/i.test(t)) return false;
                // ignore phone-like / numeric-only strings
                if (/^[0-9\\s+().-]{8,}$/.test(t)) return false;
                // ignore obvious marketing banners
                if (/free\\s+nationwide/i.test(t)) return false;
                // ignore emails
                if (/\\b\\S+@\\S+\\.[A-Za-z]{2,}\\b/.test(t)) return false;
                return true;
              });

              let bestText = '';
              let bestScore = Infinity;

              for (const container of containers) {
                if (!container) continue;
                const candidates = collectCandidates(container);
                if (!candidates.length) continue;

                for (const c of candidates) {
                  const r = c.getBoundingClientRect();
                  const cCy = (r.top + r.bottom) / 2;

                  const dy = Math.abs(cCy - elCy);

                  // Horizontal distance: prefer to the right; penalize left-side labels strongly.
                  let dx = 0;
                  if (r.left >= elRight - 2) {
                    dx = r.left - elRight;
                  } else {
                    dx = (elRight - r.right) * 3;
                  }

                  let score = dx + (dy * 2);
                  if (dy < 20) score *= 0.5; // same row bonus
                  if (r.left >= elRight - 2) score *= 0.8; // right-side bonus

                  const t = txt(c);
                  if (t.length <= 30) score *= 0.85; // short label bonus
                  // Strongly prefer <small>/<span> for option labels (e.g., glass patterns)
                  const tag = c.tagName.toLowerCase();
                  if (tag === 'small') score *= 0.55;
                  if (tag === 'span') score *= 0.8;

                  if (score < bestScore) {
                    bestScore = score;
                    bestText = t;
                  }
                }

                // If we found a strong match in a tight container, stop early.
                if (bestText && bestScore < 60) break;
              }

              // If we still picked a global/irrelevant label, fall back to input's value/id.
              const looksBad = (t) => /free\\s+nationwide|lead time|click here/i.test(t || '');
              if (bestText && !looksBad(bestText)) return bestText;
              return '';
            }"""
        )
        bbox_label = _clean_candidate(bbox_label)
        if bbox_label:
            return {"label": bbox_label, "group_label": group_label}

    # e) name attribute
    name_attr = _clean_candidate(element.get_attribute("name"))
    if name_attr:
        return {"label": name_attr, "group_label": group_label}

    # f) nearby/visually-associated text (small/span/short div/etc) + closest text nodes in container
    nearby = element.evaluate(
        """(el) => {
          const isVisibleEl = (node) => {
            if (!node || node.nodeType !== 1) return false;
            const style = window.getComputedStyle(node);
            if (style.visibility === 'hidden' || style.display === 'none') return false;
            const rect = node.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          };

          const clean = (t) => (t || '').replace(/\\s+/g, ' ').trim();
          const isShort = (t) => t && t.length > 0 && t.length <= 100;
          const textOf = (node) => (node ? clean(node.innerText || node.textContent || '') : '');

          const candidateFromEl = (node) => {
            if (!node || node.nodeType !== 1) return '';
            if (!isVisibleEl(node)) return '';
            const tag = node.tagName.toLowerCase();
            // Prefer classic small inline label elements and short text blocks.
            const t = textOf(node);
            if (!isShort(t)) return '';
            if (['small', 'span', 'label', 'strong', 'em', 'b'].includes(tag)) return t;
            if (tag === 'div' || tag === 'p' || tag === 'li') {
              // only accept short div/p/li text as label-like
              if (t.length <= 60) return t;
            }
            return '';
          };

          // Pattern A/B: closest preceding text element within the same parent container.
          const parent = el.parentElement;
          if (parent) {
            const children = Array.from(parent.children);
            const idx = children.indexOf(el);
            if (idx >= 0) {
              // Look back a few siblings for <small>/<span>/<div short text>
              for (let i = idx - 1; i >= 0 && i >= idx - 5; i--) {
                const cand = candidateFromEl(children[i]);
                if (cand) return cand;
              }
              // Sometimes input is nested (e.g., img + small + input inside wrapper)
              for (let i = idx - 1; i >= 0 && i >= idx - 5; i--) {
                const node = children[i];
                if (!node || !isVisibleEl(node)) continue;
                const nested = node.querySelector('small,span,label,strong,em,b,div,p');
                if (nested) {
                  const cand = candidateFromEl(nested);
                  if (cand) return cand;
                }
              }
            }
          }

          // Search within the parent container for closest *text nodes* around the input.
          // Prefer short text (more likely a label) and closest DOM distance.
          const score = [];
          const container = parent || el.parentElement;
          if (container && isVisibleEl(container)) {
            const walker = el.ownerDocument.createTreeWalker(
              container,
              NodeFilter.SHOW_TEXT,
              {
                acceptNode: (n) => {
                  const t = clean(n.textContent || '');
                  if (!isShort(t)) return NodeFilter.FILTER_REJECT;
                  // ignore whitespace-only
                  if (!t) return NodeFilter.FILTER_REJECT;
                  // ignore text inside the control itself
                  const p = n.parentElement;
                  if (!p) return NodeFilter.FILTER_REJECT;
                  const tag = p.tagName.toLowerCase();
                  if (['script','style','noscript'].includes(tag)) return NodeFilter.FILTER_REJECT;
                  if (p.closest('input,select,textarea,button')) return NodeFilter.FILTER_REJECT;
                  if (!isVisibleEl(p)) return NodeFilter.FILTER_REJECT;
                  return NodeFilter.FILTER_ACCEPT;
                }
              },
              false
            );
            let node;
            while ((node = walker.nextNode())) {
              score.push(node);
              if (score.length > 80) break;
            }

            const elRect = el.getBoundingClientRect();
            let bestText = '';
            let bestScore = Infinity;
            for (const tn of score) {
              const p = tn.parentElement;
              if (!p) continue;
              const r = p.getBoundingClientRect();
              const t = clean(tn.textContent || '');
              if (!t) continue;
              // prefer elements that are above/left and close
              const dx = Math.abs((r.left + r.right) / 2 - (elRect.left + elRect.right) / 2);
              const dy = Math.abs((r.top + r.bottom) / 2 - (elRect.top + elRect.bottom) / 2);
              let s = dx + dy;
              if (r.bottom <= elRect.top + 2) s *= 0.75; // above gets a bonus
              if (t.length <= 30) s *= 0.75; // short text gets a bonus
              if (s < bestScore) {
                bestScore = s;
                bestText = t;
              }
            }
            if (bestText) return bestText;
          }

          return '';
        }"""
    )
    nearby = _clean_candidate(nearby)
    return {"label": nearby, "group_label": group_label}


def get_inputs(url: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
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
        # Some ecommerce pages keep background requests running and may never reach
        # Playwright's "networkidle". We navigate on "load", then *attempt* a
        # best-effort wait for "networkidle" before extracting inputs.
        page.set_default_navigation_timeout(120_000)
        page.set_default_timeout(60_000)
        page.goto(url, wait_until="load", timeout=120_000)
        try:
            page.wait_for_load_state("networkidle", timeout=30_000)
        except Exception:
            pass

        # Note: We intentionally do NOT auto-click accordions/collapses here.
        # Many sites implement accordions as toggles; clicking can accidentally
        # close sections that were already open, making visible controls hidden.

        # Best-effort cookie/consent dismissal (varies by site).
        try:
            page.get_by_role("button", name=re.compile(r"accept|agree|allow all", re.I)).first.click(
                timeout=3_000
            )
        except Exception:
            pass

        # Wait a moment for dynamic product option controls to render.
        try:
            page.wait_for_selector("input, select, textarea", timeout=15_000)
        except Exception:
            pass

        price = get_price_element(page)

        stamp = run_stamp()
        debug_dir = "debug"
        os.makedirs(debug_dir, exist_ok=True)

        # OCR: read visible UI text from a screenshot and use it for labels.
        screenshot_path = os.path.join(debug_dir, f"page_{stamp}.png")
        ss_w, ss_h = screenshot_page(page, screenshot_path)

        # Normalize OCR coordinates to CSS pixels if needed.
        viewport_w = page.evaluate("() => window.innerWidth")
        viewport_h = page.evaluate("() => document.documentElement.scrollHeight")
        scale_x = float(viewport_w) / float(ss_w) if ss_w else 1.0
        scale_y = float(viewport_h) / float(ss_h) if ss_h else 1.0
        ss_scale_x = float(ss_w) / float(viewport_w) if viewport_w else 1.0
        ss_scale_y = float(ss_h) / float(viewport_h) if viewport_h else 1.0

        ocr_boxes = ocr_text_boxes(screenshot_path)
        text_nodes: List[Dict[str, Any]] = []
        for b in ocr_boxes:
            r = b.get("rect") or {}
            rect_ss = {
                "left": float(r.get("left", 0.0)),
                "top": float(r.get("top", 0.0)),
                "right": float(r.get("right", 0.0)),
                "bottom": float(r.get("bottom", 0.0)),
            }
            text_nodes.append(
                {
                    "text": b.get("text", ""),
                    "rect": {
                        "left": rect_ss["left"] * scale_x,
                        "top": rect_ss["top"] * scale_y,
                        "right": rect_ss["right"] * scale_x,
                        "bottom": rect_ss["bottom"] * scale_y,
                    },
                    "rect_ss": rect_ss,
                }
            )

        overlay_items: List[Dict[str, Any]] = []

        elements = get_all_inputs(page)
        for el in elements:
            tag = (el.evaluate("el => el.tagName") or "").lower()

            # skip hidden inputs and inputs not in the layout flow
            input_type = ""
            if tag == "input":
                input_type = (el.get_attribute("type") or "").lower()
                if input_type == "hidden":
                    continue

            # Include hidden controls only when a visible proxy exists (LIVE UI).
            proxy_rect_css = _get_visual_proxy_rect(el)
            if not proxy_rect_css:
                continue

            # avoid duplicate elements without mutating DOM attributes
            key = el.evaluate(
                """(el) => {
                  const doc = el.ownerDocument;
                  doc.__pwLabelKey = doc.__pwLabelKey || new WeakMap();
                  const m = doc.__pwLabelKey;
                  if (!m.has(el)) m.set(el, Math.random().toString(36).slice(2));
                  return m.get(el);
                }"""
            )
            if not key or key in seen:
                continue
            seen.add(str(key))

            # Primary label: OCR (what the user sees). We only keep DOM label if OCR fails.
            labels = extract_label(el)
            group_label = _clean_text(labels.get("group_label"))
            label = _clean_text(labels.get("label"))
            name_clean = _clean_text(el.get_attribute("name"))
            id_clean = _clean_text(el.get_attribute("id"))

            # If we only got a weak fallback (name/id), prefer what the user actually sees.
            weak_fallback = (not label) or (label and label in {name_clean, id_clean})
            if weak_fallback:
                visual, match_rect_ss = find_visual_label_match(el, text_nodes)
                visual = _clean_text(visual)
                if visual:
                    label = visual
                    if match_rect_ss:
                        overlay_items.append(
                            {
                                "label": label,
                                "proxy_rect_ss": {
                                    "left": proxy_rect_css.left * ss_scale_x,
                                    "top": proxy_rect_css.top * ss_scale_y,
                                    "right": proxy_rect_css.right * ss_scale_x,
                                    "bottom": proxy_rect_css.bottom * ss_scale_y,
                                },
                                "ocr_rect_ss": match_rect_ss,
                            }
                        )

            price_relevant = is_price_relevant(el, label, group_label, price)
            if not price_relevant:
                continue

            results.append(
                {
                    "label": label,
                    "group_label": group_label,
                    "tag": tag,
                    "type": input_type if tag == "input" else "",
                    "name": _clean_text(el.get_attribute("name")),
                    "id": _clean_text(el.get_attribute("id")),
                    "bbox": {
                        "left": proxy_rect_css.left,
                        "top": proxy_rect_css.top,
                        "right": proxy_rect_css.right,
                        "bottom": proxy_rect_css.bottom,
                    },
                    "is_price_relevant": True,
                }
            )

        # Write timestamped JSON output
        json_path = os.path.join(debug_dir, f"labels_{stamp}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        # Create overlay image with control proxy boxes + matched OCR boxes
        overlay_path = os.path.join(debug_dir, f"overlay_{stamp}.png")
        try:
            with Image.open(screenshot_path) as im:
                draw = ImageDraw.Draw(im)
                for item in overlay_items:
                    pr = item["proxy_rect_ss"]
                    orr = item["ocr_rect_ss"]
                    draw.rectangle([pr["left"], pr["top"], pr["right"], pr["bottom"]], outline="lime", width=3)
                    draw.rectangle([orr["left"], orr["top"], orr["right"], orr["bottom"]], outline="red", width=3)
                im.save(overlay_path)
        except Exception:
            pass

        browser.close()

    return results


if __name__ == "__main__":
    # Example usage:
    #   python playwright_input_labels.py https://example.com
    import sys

    if len(sys.argv) < 2:
        print("Usage: python playwright_input_labels.py <url>")
        raise SystemExit(2)

    data = get_inputs(sys.argv[1])
    print(json.dumps(data, indent=2, ensure_ascii=False))


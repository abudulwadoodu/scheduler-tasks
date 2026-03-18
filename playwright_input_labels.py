import json
import re
from typing import Any, Dict, List, Optional, Set

from playwright.sync_api import ElementHandle, sync_playwright


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
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
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

        elements = page.query_selector_all("input, select, textarea")
        for el in elements:
            tag = (el.evaluate("el => el.tagName") or "").lower()

            # skip hidden inputs and inputs not in the layout flow
            input_type = ""
            if tag == "input":
                input_type = (el.get_attribute("type") or "").lower()
                if input_type == "hidden":
                    continue

            # Exclude hidden/invisible elements.
            #
            # Exception: many modern UIs hide the real radio/checkbox input (display:none)
            # and render a clickable, visible <label> as the control. In that case, treat
            # the input as visible if its closest label is visible.
            if not el.is_visible():
                if tag == "input" and input_type in {"radio", "checkbox"}:
                    label_visible = bool(
                        el.evaluate(
                            """(el) => {
                              const lab = el.closest('label');
                              if (!lab) return false;
                              const style = window.getComputedStyle(lab);
                              if (style.display === 'none' || style.visibility === 'hidden') return false;
                              const r = lab.getBoundingClientRect();
                              return r.width > 0 && r.height > 0;
                            }"""
                        )
                    )
                    if not label_visible:
                        continue
                else:
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

            labels = extract_label(el)
            label = _clean_text(labels.get("label"))
            group_label = _clean_text(labels.get("group_label"))

            results.append(
                {
                    "label": label,
                    "group_label": group_label,
                    "tag": tag,
                    "type": input_type if tag == "input" else "",
                    "name": _clean_text(el.get_attribute("name")),
                    "id": _clean_text(el.get_attribute("id")),
                }
            )

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


"""
Screenshot analyzer using GPT-4 Vision to identify price-relevant input components.
"""
import base64
from typing import List
from playwright.sync_api import sync_playwright
from openai import OpenAI
from .models import (
    IdentifiedComponent,
    ComponentsAnalysisResponse,
    PriceElement,
    PriceXPathEntry,
    PriceXPaths,
    PriceSelection,
    VisualPriceClue,
    ScreenshotPriceAnalysis,
    ValidatedPriceCandidate,
    PriceMatchResponse,
)
from .xpath_utils import build_xpath


class ScreenshotAnalyzer:
    """Analyzes webpage screenshots to identify price-relevant input components."""

    def __init__(
        self,
        api_key: str,
        api_base: str,
        api_version: str,
        model: str = "gpt-4.1-vision-preview"
    ):
        """Initialize the screenshot analyzer with Azure OpenAI credentials."""
        self.client = OpenAI(
            api_key=api_key,
        )
        self.model = model

    def capture_screenshot(self, url: str) -> bytes:
        """
        Capture a full-page screenshot of the given URL.

        Args:
            url: The webpage URL to screenshot

        Returns:
            Screenshot as bytes
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})

            try:
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                except Exception as e:
                    print(f"[WARN] networkidle timed out, retrying with 'load' event: {e}")
                    page.goto(url, wait_until="load", timeout=60000)
                    page.wait_for_timeout(5000)
                else:
                    page.wait_for_timeout(2000)
                screenshot_bytes = page.screenshot(full_page=True)
                return screenshot_bytes
            finally:
                browser.close()

    def analyze_screenshot(self, screenshot_bytes: bytes, ui_flow_hint: str = None) -> ComponentsAnalysisResponse:
        """
        Analyze screenshot using GPT-4 Vision to identify price-relevant inputs.

        Args:
            screenshot_bytes: Screenshot image as bytes
            ui_flow_hint: Optional hint string to guide UI flow ordering

        Returns:
            ComponentsAnalysisResponse with identified components and extracted prices
        """
        base64_image = base64.b64encode(screenshot_bytes).decode('utf-8')

        system_prompt = (
            "You are an expert web scraping analyst. Your task is to identify ALL interactive input components on a webpage that could affect the final price of a product or service, AND determine the correct order in which those components must be interacted with.\n"
            "\nLook for:\n"
            "- Text input fields (dimensions, quantities, custom text)\n"
            "- Dropdown/select menus (options, materials, colors)\n"
            "- Radio buttons (choices that may change price)\n"
            "- Checkboxes (add-ons, extras, features)\n"
            "- Sliders or number spinners\n"
            "- Date pickers\n"
            "- Any other interactive element that affects pricing\n"
            "\nFor EACH component, provide:\n"
            "1. label: The visible label or text associated with it\n"
            "2. type: The input type (text, select, radio, checkbox, slider, etc.)\n"
            "3. description: Clear description of what it controls\n"
            "4. price_relevance_reason: Why this affects the final price\n"
            "5. group_context: The section/group it belongs to (if visible)\n"
            "6. execution_order: A 1-based integer indicating the strict sequential step at which this component should be interacted with. Every component MUST have a unique execution_order — no two components may share the same number. Number them 1, 2, 3, 4... with no gaps and no ties. Order them by dependency: components whose value gates or reveals other components come first; among independent components, order them top-to-bottom as they appear on the page.\n"
            "7. execution_order_reason: A brief explanation of why the component has that execution_order — what it unlocks, what it depends on, or where it sits relative to its neighbours.\n"
            "\nWhen determining execution_order, think through the dependency chain:\n"
            "- Which selections gate or reveal other options? → lowest numbers\n"
            "- Which fields only make sense after a prior choice is made? → after their dependency\n"
            "- Which fields are completely independent? → order them by visual position (top to bottom, left to right)\n"
            "\nBe thorough - identify ALL inputs, even if they seem minor.\n"
            "\nAlso extract any currently displayed price for the product:\n"
            "- price_without_tax: the price shown excluding tax (e.g. '£12.99'), or null if not visible\n"
            "- price_with_tax: the price shown including tax (e.g. '£15.59'), or null if not visible\n"
        )

        if ui_flow_hint:
            system_prompt += ("\n\n---\n\nADDITIONAL UI FLOW HINT:\n"
                              f"{ui_flow_hint}\n"
                              "If this hint describes a specific order (e.g., 'Select Width dropdown before Height'), use it to guide execution_order and execution_order_reason, but only if it is consistent with visible UI dependencies. If the hint conflicts with clear UI logic, explain why in execution_order_reason.")

        user_prompt = (
            "Analyze this webpage screenshot and identify ALL input components that could affect the final price.\n\n"
            "For each component assign a strictly sequential, unique execution_order (1, 2, 3, 4...) — no two components may share the same number. Order by dependency first (components that gate/reveal others come earliest), then by visual position top-to-bottom for independent ones. Provide an execution_order_reason explaining your decision.\n\n"
            "Be comprehensive and identify every single price-relevant input on this page."
        )

        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                response_format=ComponentsAnalysisResponse,
                max_tokens=4096,
                temperature=0.1
            )

            parsed_response = response.choices[0].message.parsed
            components = parsed_response.components

            # Guarantee strictly sequential, unique execution_order (1, 2, 3…)
            components.sort(key=lambda c: c.execution_order)
            for i, component in enumerate(components, start=1):
                component.execution_order = i

            parsed_response.components = components
            return parsed_response

        except Exception as e:
            print(f"Error analyzing screenshot: {e}")
            raise

    @staticmethod
    def get_price_xpath(price_element: PriceElement) -> str:
        """Generate an XPath selector for a price element using build_xpath."""
        return build_xpath(
            tag=price_element.tag,
            id_=price_element.id,
            name=price_element.name,
            type_=price_element.type,
            class_name=price_element.class_name,
        )

    def analyze_prices_from_screenshot(
        self,
        screenshot_bytes: bytes,
    ) -> ScreenshotPriceAnalysis:
        """
        Step 3a — Vision-only.

        Identify the price-with-tax, price-without-tax, and base/original price
        purely from the screenshot. No DOM or XPaths involved.

        Args:
            screenshot_bytes: Full-page screenshot captured by capture_screenshot().

        Returns:
            ScreenshotPriceAnalysis with visual clues for each price type.
        """
        base64_image = base64.b64encode(screenshot_bytes).decode("utf-8")

        system_prompt = (
            "You are an expert e-commerce price analyst.\n"
            "You will be shown a webpage screenshot. Your sole task is to identify up to three "
            "distinct price values and classify them by tax status:\n"
            "  1. price_with_tax   — the final price the customer pays, INCLUDING tax (e.g. 'inc. VAT')\n"
            "  2. price_without_tax — the price BEFORE tax is added (e.g. 'ex. VAT', 'nett')\n"
            "  3. base_price       — the original/undiscounted price shown SEPARATELY (e.g. a struck-through "
            "RRP or 'was' price). Set to null when no such separate original price is visible.\n\n"
            "For each identified price provide:\n"
            "  • value             — the price string exactly as displayed (e.g. '£15.59')\n"
            "  • with_tax_indicator — any nearby label revealing tax status (e.g. 'inc. VAT')\n"
            "  • surrounding_text  — a few words of context around the price\n"
            "  • visual_description — brief note on its visual prominence / position\n\n"
            "Set a price type to null if it is not present or cannot be determined from the screenshot."
        )

        user_prompt = (
            "Examine the screenshot and identify the price-with-tax, price-without-tax, "
            "and base/original price. Return structured JSON."
        )

        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                        },
                    ],
                },
            ],
            response_format=ScreenshotPriceAnalysis,
            max_tokens=1024,
            temperature=0.1,
        )
        return response.choices[0].message.parsed

    def validate_all_price_candidates(
        self,
        url: str,
        all_prices: List[PriceElement],
    ) -> List[ValidatedPriceCandidate]:
        """
        Step 3b — DOM validation only (single Playwright session).

        For every element in all_prices, build its XPath and check whether it
        matches exactly one element on the live page. Collect text_content and
        outer_html for verified elements.

        Args:
            url:        Webpage URL (same one used for the screenshot).
            all_prices: Candidate price elements from the labels JSON.

        Returns:
            List of ValidatedPriceCandidate, one per element in all_prices.
        """
        candidates: List[ValidatedPriceCandidate] = []
        if not all_prices:
            return candidates

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            try:
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                except Exception as e:
                    print(f"[WARN] networkidle timed out, retrying with 'load': {e}")
                    page.goto(url, wait_until="load", timeout=60000)
                    page.wait_for_timeout(5000)
                else:
                    page.wait_for_timeout(2000)

                for i, price_el in enumerate(all_prices):
                    xpath = self.get_price_xpath(price_el)
                    try:
                        locator = page.locator(f"xpath={xpath}")
                        count = locator.count()
                        if count == 1:
                            candidates.append(ValidatedPriceCandidate(
                                index=i,
                                label=price_el.label,
                                xpath=xpath,
                                verified=True,
                                text_content=locator.inner_text(),
                                outer_html=locator.evaluate("el => el.outerHTML"),
                            ))
                        else:
                            reason = "no match" if count == 0 else f"{count} matches (ambiguous)"
                            print(f"  [WARN] candidate[{i}] xpath={xpath!r}: {reason}")
                            candidates.append(ValidatedPriceCandidate(
                                index=i, label=price_el.label, xpath=xpath, verified=False,
                            ))
                    except Exception as e:
                        print(f"  [WARN] candidate[{i}] xpath={xpath!r} error: {e}")
                        candidates.append(ValidatedPriceCandidate(
                            index=i, label=price_el.label, xpath=xpath, verified=False,
                        ))
            finally:
                browser.close()

        return candidates

    def match_prices_to_xpaths(
        self,
        price_analysis: ScreenshotPriceAnalysis,
        validated_candidates: List[ValidatedPriceCandidate],
    ) -> PriceXPaths:
        """
        Step 3c — Text-only LLM matching.

        Given the visual price clues (from analyze_prices_from_screenshot) and the
        DOM-validated candidates (from validate_all_price_candidates), ask the LLM
        (text only — no image) to match each visual clue to its best candidate.

        Args:
            price_analysis:       Output of analyze_prices_from_screenshot.
            validated_candidates: Output of validate_all_price_candidates.

        Returns:
            PriceXPaths populated from the matched ValidatedPriceCandidate entries.
        """
        if not validated_candidates:
            return PriceXPaths()

        def _clue_text(label: str, clue: "VisualPriceClue | None") -> str:
            if clue is None:
                return f"{label}: NOT identified in screenshot"
            parts = [f"{label}: value={clue.value!r}"]
            if clue.with_tax_indicator:
                parts.append(f"tax_indicator={clue.with_tax_indicator!r}")
            if clue.surrounding_text:
                parts.append(f"surrounding={clue.surrounding_text!r}")
            if clue.visual_description:
                parts.append(f"visual={clue.visual_description!r}")
            return "  " + ", ".join(parts)

        visual_block = "\n".join([
            "Visual price clues from screenshot:",
            _clue_text("price_with_tax",    price_analysis.price_with_tax),
            _clue_text("price_without_tax", price_analysis.price_without_tax),
            _clue_text("base_price",        price_analysis.base_price),
        ])

        candidates_block = "Validated DOM candidates:\n" + "\n".join(
            f"  [{c.index}] label={c.label!r}  verified={c.verified}"
            + (f"  text={c.text_content!r}" if c.text_content else "  (no text — unverified)")
            for c in validated_candidates
        )

        system_prompt = (
            "You are an expert web analyst.\n"
            "You will be given:\n"
            "  A) Visual price clues observed in a screenshot.\n"
            "  B) A numbered list of DOM price candidates with their text_content.\n\n"
            "Your task: match each visual price clue to the most appropriate DOM candidate "
            "by comparing the observed price value and context with the DOM text_content.\n\n"
            "Rules:\n"
            "  - Use 0-based index from the candidates list.\n"
            "  - A single candidate can only satisfy one price type.\n"
            "  - If a price type is 'NOT identified' or no suitable candidate exists, set index=null.\n"
            "  - Prefer verified candidates (verified=True) over unverified ones.\n"
            "  - Provide clear reasoning for each selection."
        )

        user_prompt = (
            f"{visual_block}\n\n"
            f"{candidates_block}\n\n"
            "Match each price type to its best DOM candidate. Return structured JSON."
        )

        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=PriceMatchResponse,
            max_tokens=1024,
            temperature=0.1,
        )
        match: PriceMatchResponse = response.choices[0].message.parsed

        def _entry_for_selection(sel: PriceSelection) -> "PriceXPathEntry | None":
            if sel.index is None:
                return None
            matches = [c for c in validated_candidates if c.index == sel.index]
            if not matches:
                return None
            c = matches[0]
            return PriceXPathEntry(
                xpath=c.xpath,
                verified=c.verified,
                text_content=c.text_content,
                outer_html=c.outer_html,
            )

        return PriceXPaths(
            price_with_tax=_entry_for_selection(match.price_with_tax),
            price_without_tax=_entry_for_selection(match.price_without_tax),
            base_price=_entry_for_selection(match.base_price),
        )

    def analyze_url(self, url: str) -> ComponentsAnalysisResponse:
        """
        Complete workflow: capture screenshot and analyze it.

        Args:
            url: The webpage URL to analyze

        Returns:
            ComponentsAnalysisResponse with identified components and extracted prices
        """
        print(f"📸 Capturing screenshot of {url}...")
        screenshot_bytes = self.capture_screenshot(url)

        print(f"🔍 Analyzing screenshot with vision model...")
        result = self.analyze_screenshot(screenshot_bytes)

        print(f"✅ Identified {len(result.components)} price-relevant components")

        return result

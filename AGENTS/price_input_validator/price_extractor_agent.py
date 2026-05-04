"""
Price extractor code-generation agent.

Given the visual price clues from the screenshot and the DOM content of the matched
price elements, this agent generates a ready-to-import Python module containing:

  - ExtractedPrice  — dataclass with fields: with_tax (bool), price (float),
                      currency_symbol (str)
  - extract_price_with_tax(text_content: str) -> ExtractedPrice
  - extract_price_without_tax(text_content: str) -> ExtractedPrice

The LLM reasons about the observed text patterns *before* writing code, so the
generated functions are tailored to the specific format seen on the target page.
"""
from pathlib import Path
from openai import OpenAI
from .models import (
    PriceExtractorCodeResponse,
    PriceExtractorOutput,
    PriceXPaths,
    ScreenshotPriceAnalysis,
)


class PriceExtractorAgent:
    """Generates price-extractor Python functions using the LLM."""

    def __init__(
        self,
        api_key: str,
        api_base: str,
        api_version: str,
        model: str = "gpt-4",
    ):
        self.client = OpenAI(
            api_key=api_key,
        )
        self.model = model

    def generate(
        self,
        price_analysis: ScreenshotPriceAnalysis,
        price_xpaths: PriceXPaths,
        output_path: str,
    ) -> PriceExtractorOutput:
        """
        Generate a Python module that can extract the price values from the
        text_content strings of the matched price DOM elements.

        Args:
            price_analysis: Visual price clues from the screenshot (step 3a).
            price_xpaths:   Matched XPath entries with text_content / outer_html
                            from the live DOM (step 3c output).
            output_path:    Absolute path where the generated .py file will be saved.

        Returns:
            PriceExtractorOutput with reasoning, python_code, and output_file_path.
        """

        def _price_section(label: str, clue, entry) -> str:
            lines = [f"=== {label} ==="]
            if clue is not None:
                lines.append(f"  Visual value seen in screenshot : {clue.value!r}")
                if clue.with_tax_indicator:
                    lines.append(f"  Tax indicator                  : {clue.with_tax_indicator!r}")
                if clue.surrounding_text:
                    lines.append(f"  Surrounding text (screenshot)  : {clue.surrounding_text!r}")
                if clue.visual_description:
                    lines.append(f"  Visual description             : {clue.visual_description!r}")
            else:
                lines.append("  NOT identified in screenshot — function must raise NotImplementedError.")

            if entry is not None and entry.verified:
                lines.append(f"  DOM text_content               : {entry.text_content!r}")
                lines.append(f"  DOM outer_html (first 400 ch)  : {(entry.outer_html or '')[:400]!r}")
            else:
                lines.append("  No verified DOM element found — function must raise NotImplementedError.")

            return "\n".join(lines)

        with_tax_section = _price_section(
            "price_with_tax",
            price_analysis.price_with_tax if price_analysis else None,
            price_xpaths.price_with_tax,
        )
        without_tax_section = _price_section(
            "price_without_tax",
            price_analysis.price_without_tax if price_analysis else None,
            price_xpaths.price_without_tax,
        )
        base_price_section = _price_section(
            "base_price",
            price_analysis.base_price if price_analysis else None,
            price_xpaths.base_price,
        )

        system_prompt = (
            "You are an expert Python developer who writes robust price-extraction functions.\n\n"
            "You will be given observed data about price elements on a webpage:\n"
            "  A) The price value seen in the screenshot, any tax indicator, and surrounding text.\n"
            "  B) The actual text_content and outer_html fetched from the matched DOM element.\n\n"
            "Your task is to write a self-contained Python module with:\n"
            "  1. An ExtractedPrice dataclass (with_tax: bool, price: float, currency_symbol: str)\n"
            "  2. extract_price_with_tax(text_content: str) -> ExtractedPrice\n"
            "  3. extract_price_without_tax(text_content: str) -> ExtractedPrice\n\n"
            "CRITICAL rules for the generated code:\n"
            "  - Use only the Python standard library (re, decimal) — no third-party packages.\n"
            "  - Functions must be reliable for the OBSERVED pattern; do NOT hardcode the actual "
            "price value. The real price will change; the FORMAT will stay the same.\n"
            "  - If the text_content contains multiple numbers, use the surrounding context "
            "(e.g. 'Now £X inc. VAT', a specific CSS class, or position) to select the right one.\n"
            "  - If a price type was NOT identified (see section marked NotImplementedError), "
            "the function body must be: raise NotImplementedError('<type> not identified for this page')\n"
            "  - If the function IS implemented but the format is not found in text_content, "
            "raise ValueError(f'Could not parse <type> from: {text_content!r}')\n"
            "  - Fill with_tax_reasoning BEFORE writing code for extract_price_with_tax.\n"
            "  - Fill without_tax_reasoning BEFORE writing code for extract_price_without_tax.\n"
            "  - python_code must be the COMPLETE module source — no markdown fences, no ellipsis.\n"
            "  - Include a short module docstring and an if __name__ == '__main__' demo.\n"
        )

        user_prompt = (
            f"{with_tax_section}\n\n"
            f"{without_tax_section}\n\n"
            f"{base_price_section}\n\n"
            "First reason carefully about each function's parsing strategy, then write the complete "
            "Python module. Return structured JSON."
        )

        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=PriceExtractorCodeResponse,
                max_tokens=4096,
                temperature=0.1,
            )
            result: PriceExtractorCodeResponse = response.choices[0].message.parsed

        except Exception as e:
            print(f"Error generating price extractor code: {e}")
            raise

        # Save the generated module
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(result.python_code, encoding="utf-8")
        print(f"  💾 Price extractor saved to: {output_path}")

        return PriceExtractorOutput(
            with_tax_reasoning=result.with_tax_reasoning,
            without_tax_reasoning=result.without_tax_reasoning,
            python_code=result.python_code,
            output_file_path=output_path,
        )

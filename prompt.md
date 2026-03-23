Write a Python web scraping script using the Playwright sync API.

## Function Signature

def scrape_price(
    url: str,
    steps: list[dict],
    price_xpath: str,
    headless: bool = True,
    screenshot_path: str | None = None,
    timeout: int = 30_000,
) -> str:

## Parameters

- url: Page URL to navigate to
- steps: Ordered list of interaction step dicts (see Step Format below)
- price_xpath: XPath of the element containing the final price
- headless: Launch browser headless when True (default)
- screenshot_path: If provided, save a screenshot after extraction
- timeout: Milliseconds for all waits (default 30_000)

## Step Format

Each step dict supports:
{
    "action": "select_dropdown" | "click" | "hover" | "fill" | "wait",
    "xpath": "<xpath string>",    # not required for "wait"
    "value": "<value>"            # required for select_dropdown / fill;
                                  # for "wait" treated as milliseconds
}

## Browser Behaviour

- Launch Chromium with stealth args and a realistic user agent to reduce automation detection:
    browser = playwright.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ..."
    )
- Block images, fonts, and media via context.route to speed up page load 2-5x:
    context.route("**/*", lambda route: route.abort()
        if route.request.resource_type in {"image", "font", "media"}
        else route.continue_())
- Create the page from the context: page = context.new_page()
- Navigation strategy:
  - First attempt: wait_until="domcontentloaded" - more reliable than networkidle
    which times out on sites with continuous background requests (analytics, chat widgets)
  - Fallback on timeout: retry with wait_until="load"
  - After navigation: time.sleep(2) to allow JS frameworks (Alpine.js, Vue, React) to hydrate
- Add a random delay of 0.5-1.5s between each non-wait step to mimic human behaviour
- Wrap the entire browser lifecycle in try/finally to always close browser and stop Playwright

## Dropdown Selection - Partial / Fuzzy Match

For select_dropdown, do NOT use exact value matching (select_option(str(value))).
Instead implement a helper _select_option_partial(page, xpath, target) that tries
3 strategies in order, stopping at the first match:

Strategy 1 - Leading number exact match:
Extract the leading number from the option's value attribute and compare with ==.
    leading = re.match(r"^(\d+(?:\.\d+)?)", raw_value)
    if leading and leading.group(1) == target_stripped: ...
This handles values like "25+0.65", "25mm", "25-standard" when target is "25".
It is safe: "15" == "15" matches, but "15" == "150" does not - no false matches.

Strategy 2 - Word-boundary match on visible text.
Strategy 3 - Word-boundary match on raw value attribute.
Both use a pre-compiled regex with negative digit lookarounds:
    boundary_pattern = re.compile(
        r"(?<!\d)" + re.escape(target_stripped) + r"(?!\d)",
        re.IGNORECASE,
    )
This ensures "15" matches "15mm Thick" and "pipe-15-foil"
but does NOT match "150mm Thick" or "pipe-150-foil".

Plain substring (in) must NOT be used - it causes false matches
(e.g. "15" in "150" is True).

If no strategy matches, print all available options with their text and value
to aid debugging, then return False.

Also implement a helper _xpath_to_css_for_select(xpath) that converts simple
id-based XPaths like //*[@id='attribute188'] to CSS #attribute188 so
query_selector_all works cleanly.

## Dropdown Retry Logic

Wrap each select_dropdown attempt in a retry loop (3 attempts, 1s sleep between)
to handle DOM rebuilds from Alpine.js, React, and Magento configurable products.
Re-raise RuntimeError (no match found) immediately without retrying - retries are
only for transient exceptions (e.g. element detached mid-interaction).

## Click Behaviour

Before clicking an element, call scroll_into_view_if_needed() to ensure it is
within the viewport. This prevents click failures in headless mode.

## Price Change Detection

Before executing steps, attempt to read the current price text from price_xpath
and store it as old_price (None if the element is not yet present).

After all steps complete, if old_price is not None, wait for the price element
text to differ from old_price using page.wait_for_function:

    page.wait_for_function(
        """([xpath, oldPrice]) => {
            const el = document.evaluate(
                xpath, document, null,
                XPathResult.FIRST_ORDERED_NODE_TYPE, null
            ).singleNodeValue;
            return el && el.innerText.trim() !== oldPrice;
        }""",
        arg=[price_xpath, old_price],
        timeout=timeout,
    )

If this wait times out (PlaywrightTimeoutError), silently continue - the price
may not have changed, and the extraction step will validate it.

This prevents reading a stale default price before the page updates.

## Price Extraction

- Locate the price element using price_xpath
- Wait for it to be attached (wait_for(state="attached", timeout=timeout))
  Note: Use "attached" not "visible" - price elements are often hidden in the DOM
- Once attached, use Playwright's expect to wait for non-empty text:
    from playwright.sync_api import expect
    expect(price_locator).not_to_be_empty(timeout=timeout)
- Extract inner text and clean it:
  - Strip whitespace
  - Remove currency symbols ($, €, £, ¥, ₹) and commas
- Print "Extracted price: <value>"
- Return the cleaned price string

## Error Handling

- Step dict missing action key        -> ValueError with step index
- Unknown action value                -> ValueError listing valid actions
- Element timeout during a step       -> RuntimeError with step index, action, and XPath
- select_dropdown finds no match      -> RuntimeError with step index and target value
- Price element not found             -> TimeoutError with the XPath used
- Price element found but empty       -> TimeoutError with the XPath used

Re-raise ValueError and RuntimeError unchanged. Catch both PlaywrightTimeoutError
and AssertionError (raised by expect) and wrap them in the appropriate exception above.

## Module-level Configuration

Before the scrape_price function, define two module-level constants:

STEPS = [
    {
        "action": "select_dropdown",
        "xpath": "//*[@id='attribute188']",
        "value": "15"
    },
    {
        "action": "select_dropdown",
        "xpath": "//*[@id='attribute187']",
        "value": "25"
    },
    {
        "action": "wait",
        "value": "800"
    }
]

PRICE_XPATH = "//div[contains(@class,'final-price-excl-tax')]//span[contains(@class,'price text-base')]"

## Main Block

At the end of the script, include the following `if __name__ == "__main__":` block.

- `url` is accepted as user input via `input()` at runtime
- `steps` and `price_xpath` are passed using the module-level STEPS and PRICE_XPATH constants

```python
if __name__ == "__main__":

    url = input("Enter URL: ")

    price = scrape_price(
        url=url,
        steps=STEPS,
        price_xpath=PRICE_XPATH,
        headless=False,
        screenshot_path="price_screenshot.png",
        timeout=20_000,
    )
    print(f"Final price: {price}")
```

## Output

- Return the cleaned price string
- Print "Extracted price: <value>"
- If screenshot_path is provided, save full-page screenshot and print the path
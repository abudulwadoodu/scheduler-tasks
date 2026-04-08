Write a Python web scraping script using the Playwright sync API.

## Function Signature

def scrape_price(
    url: str,
    comment: comment,
    price_xpath: str,
    headless: bool = True,
    screenshot_path: str | None = None,
    timeout: int = 30_000,
) -> str:

## Parameters

- url: Page URL to navigate to
- comment: hint for interaction step used parse_comment function to form values for each interaction 
- price_xpath: XPath of the element containing the final price
- headless: Launch browser headless when True (default)
- screenshot_path: If provided, save a screenshot after extraction
- timeout: Milliseconds for all waits (default 30_000)

## Comment Parser Function

- map comment to the label and value
- output will be dict

```python

{comment_parser_function}



```
## Navigation steps
- Navigation steps contain all the possible steps to perform to get correct price
- Includes select, text input, radio button
- Each steps have the following information as dict
- using xpath,tag, and type create interaction steps
- Match the label and use value from comment parse output to perform web interaction

{
    label : <label_name> 
    tag : <input, select>
    type : <checkbox, radio, text>
    xpath : <xpath of the element>  
}

## Steps

{navigation steps}

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

## Radio buttons and checkboxes
- Modern sites often hide the actual element and attach click handlers to visible elements.
- Examples:
    Attempting locator.check() on hidden inputs causes timeout errors.

- Therefore the script must automatically detect hidden inputs and click the visible label or wrapper instead.
- Do NOT:locator.wait_for(state="visible") for radio inputs directly.
- Do NOT rely only on locator.check() for radio buttons.
- Do NOT force click hidden inputs unless no label exists.
- The generated script MUST use the helper below.

```python
def _smart_locator(page, step, timeout=5000):
    base = page.locator(f"xpath={step['xpath']}")

    try:
        base.wait_for(state="attached", timeout=2000)
    except Exception:
        return None

    if base.is_visible():
        return base

    element_id = base.get_attribute("id")

    if element_id:
        # ✅ PRIMARY: click the u-check-icon div inside the label
        icon_div = page.locator(
            f"label[for='{element_id}'] div[class*='u-check-icon']"
        )
        if icon_div.count() > 0:
            return icon_div.first

        # Fallback: plain label[for=id]
        label_for = page.locator(f"label[for='{element_id}']")
        if label_for.count() > 0:
            return label_for.first

    # ancestor label → also try its icon div first
    ancestor_label = page.locator(
        f"xpath={step['xpath']}/ancestor::label"
    )
    if ancestor_label.count() > 0:
        ancestor_icon = ancestor_label.first.locator("div[class*='u-check-icon']")
        if ancestor_icon.count() > 0:
            return ancestor_icon.first
        return ancestor_label.first

    # label by visible text
    text = step["label"].lower()
    label_by_text = page.locator(
        f"""//label[contains(
                translate(normalize-space(.),
                'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                'abcdefghijklmnopqrstuvwxyz'),
                '{text}'
        )]"""
    )
    if label_by_text.count() > 0:
        icon = label_by_text.first.locator("div[class*='u-check-icon']")
        if icon.count() > 0:
            return icon.first
        return label_by_text.first

    # clickable wrapper fallback
    wrapper = page.locator(
        f"xpath={step['xpath']}/ancestor::*[self::div or self::span][1]"
    )
    if wrapper.count() > 0:
        return wrapper.first

    return base
```

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
- Locate the first resolved
- Wait for it to be attached (wait_for(state="attached", timeout=timeout))
  Note: Use "attached" not "visible" - price elements are often hidden in the DOM
- Once attached, use Playwright's expect to wait for non-empty text:
    from playwright.sync_api import expect
    expect(price_locator).not_to_be_empty(timeout=timeout)
- Extract inner text and clean it:
  - Strip whitespace
  - Remove currency symbols (€, £, ¥, ₹) and commas
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

Before the scrape_price function, define module-level constants:

PRICE_XPATH = {price_xpath}

## Main Block

At the end of the script, include the following `if __name__ == "__main__":` block.

- `url` is accepted as user input via `input()` at runtime
- `steps` and `price_xpath` are passed using the module-level STEPS and PRICE_XPATH constants

```python
if __name__ == "__main__":

    url = input("Enter URL: ")
    comment =  input("comment : ")

    price = scrape_price(
        url=url,
        comment=comment,
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
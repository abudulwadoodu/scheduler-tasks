"""
Agent 2 — Generates the parse_comment() function as a Python source string.
Input  : pydantic_model_code (str from Agent 1), comment (str sample)
Output : parse_comment() function source string, validated by ast.parse()
"""

import ast
import re

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

import dotenv

dotenv.load_dotenv()
# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

AGENT2_PROMPT = """\
I am automating a website form using Playwright.
## Task
Write a single reusable Python function:
    def parse_comment(comment: str) -> NagivationStepsModel
The function must parse any free-text product comment and return a fully
populated `NagivationStepsModel` Pydantic instance.
---
## Rules
### General
- Return a `NagivationStepsModel` instance populated with parsed values
- Use `comment.lower()` for all matching — case-insensitive throughout
- If a field is not mentioned in the comment, apply the most sensible default
- Construct the model in a single `NagivationStepsModel(...)` call at the end,
  passing all fields as keyword arguments using their Python field names
### Text inputs (numeric)
- Extract values using regex: support patterns like NNN x NNN, NNN×NNN, NNN-NNN, NNN/NNN, NNN by NNN
- If contextual keywords exist (width, height, W=, H=), use them to assign correctly
- Otherwise assume values appear in the same order as the related form fields (e.g. width first, height second)
- Default to None if not found
### Radio button groups
- Set the matched field to `True`, all others in the same group to `None`
- Use a priority-ordered if/elif chain — most specific pattern first, most generic last
- For colour groups: if the comment implies a base/default product (e.g. "White UPVC"), set all colour fields to `None`
- Always use two lists for colours: one for match-order (specific-first), one for field-name order (for output)
- Default to a sensible option (e.g. `Clear=True`, `Standard_A_Rated=True`) when not mentioned
### Checkboxes
- Set to `True` if the keyword is found in the comment, `None` otherwise
### Select dropdowns
- Match the exact option value string if mentioned in the comment
- For fields that expect a numerical quantity, extract the number using a single `re.search` call with alternation (`|`) covering all these patterns: digit before keyword (`2 trickle vents`), digit after keyword (`trickle vents 2`), `x`-prefix (`x2`, `2x`), and bracketed (`(2)`, `[2]`)
- `re.search` scans left to right — if the keyword appears multiple times, it will skip occurrences with no digit and land on the one that has a digit. This is correct and intended
- If the keyword is present but no quantity pattern matches anywhere in the comment, trigger the fallback: `return parse_order_from_comment(comment)`
- Default to the first/default option value if the keyword is not mentioned at all
### Fallback Condition
- If the dimensions regex returns no match, immediately `return parse_order_from_comment(comment)`
- If a select dropdown keyword is present but no quantity can be extracted by any regex branch, immediately `return parse_order_from_comment(comment)`
- Both fallback cases short-circuit the rest of the parsing logic
- This function returns a fully populated `NagivationStepsModel`
---
## Output style  <- IMPORTANT
- Return ONLY the raw Python function — no markdown, no code fences, no explanation
- The function must be importable as-is
- Do NOT include import statements — `re` is already imported in the module
Produce code in this exact style — no classes, no schema dicts, no helper functions:
def parse_comment(comment: str) -> NagivationStepsModel:
    c = comment.lower()
    # --- Dimensions ---
    dim = re.search(r'...', c)
    if dim:
        width, height = dim.group(1), dim.group(2)
    else:
        return parse_order_from_comment(comment)
    # --- Radio group ---
    if '...' in c:
        selected_x = 'A'
    elif '...' in c:
        selected_x = 'B'
    else:
        selected_x = None
    # --- Checkboxes ---
    thing = True if '...' in c else None
    # --- Select (quantity) ---
    qty_field = 'Not Required'
    qty_match = re.search(r'...', c)
    if qty_match:
        qty = next(g for g in qty_match.groups() if g is not None)
        qty_field = qty if qty in ('1', '2') else 'Not Required'
    elif '...' in c:
        return parse_order_from_comment(comment)
    # --- Build and return model ---
    return NagivationStepsModel(
        Frame_Width_mm=width,
        Frame_Height_mm=height,
        Field_A=True if selected_x == 'A' else None,
        Field_B=True if selected_x == 'B' else None,
        Toughened_Glass=thing,
        Qty_Field=qty_field,
    )
No extra classes, no schema, no helper functions. Flat and readable.

---
## Pydantic Model

{pydantic_model_code}

## Comment
{comment}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_code(response: str) -> str:
    """Strip markdown code fences if the LLM wrapped the output in them."""
    # ```python ... ``` or ``` ... ```
    match = re.search(r"```(?:python)?\s*(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return response.strip()


def _validate_code(code: str) -> None:
    """
    Raise SyntaxError with a clear message if the generated code
    cannot be parsed by Python's AST.
    """
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise SyntaxError(
            f"[Agent 2] Generated parse_comment() has a syntax error "
            f"at line {e.lineno}: {e.msg}\nSnippet: {e.text}"
        ) from e


def _validate_function_present(code: str) -> None:
    """Ensure the generated code actually contains the parse_comment function."""
    tree = ast.parse(code)
    func_names = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]
    if "parse_comment" not in func_names:
        raise ValueError(
            "[Agent 2] Generated code does not contain a 'parse_comment' function. "
            f"Found functions: {func_names}"
        )


# ---------------------------------------------------------------------------
# Agent 2
# ---------------------------------------------------------------------------

def parser_generator(pydantic_model_code: str, comment: str) -> str:
    """
    Generate the parse_comment() function source string.

    Parameters
    ----------
    pydantic_model_code : str
        Full Pydantic model source from Agent 1.
    comment : str
        A sample product comment for the LLM to use as context.

    Returns
    -------
    str
        Validated parse_comment() function source, ready to inject into
        the scraper template via Agent 3.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("human", AGENT2_PROMPT),
    ])

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    chain = prompt | llm

    response = chain.invoke({
        "pydantic_model_code": pydantic_model_code,
        "comment": comment,
    })

    raw = response.content if hasattr(response, "content") else str(response)

    # Clean → validate → return
    code = _extract_code(raw)
    _validate_code(code)
    _validate_function_present(code)

    print("[Agent 2] parse_comment() generated and validated successfully.")
    return code


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    SAMPLE_MODEL = """

# ── Pydantic Model ────────────────────────────────────────────────────────────

class NagivationStepsModel(BaseModel):
    model_config = {"populate_by_name": True}

    # -- Dimensions --
    Frame_Width_mm: Optional[str] = Field(default=None, alias="Frame Width (mm)")
    Frame_Height_mm: Optional[str] = Field(default=None, alias="Frame Height (mm)")
    # -- Cill Options --
    No: Optional[bool] = Field(default=None, alias="No")
    mm85_Stub: Optional[bool] = Field(default=None, alias="85mm Stub")
    Standard_150mm: Optional[bool] = Field(default=None, alias="Standard 150mm")
    mm180: Optional[bool] = Field(default=None, alias="180mm")
    # -- Colour Options --
    White: Optional[bool] = Field(default=None, alias="White")
    Oak_Both_Sides: Optional[bool] = Field(default=None, alias="Oak Both Sides")
    Oak_White: Optional[bool] = Field(default=None, alias="Oak/White")
    Rosewood_Both_Sides: Optional[bool] = Field(default=None, alias="Rosewood Both Sides")
    Rosewood_White: Optional[bool] = Field(default=None, alias="Rosewood/White")
    Anthracite_Grev_Both_Sides: Optional[bool] = Field(default=None, alias="Anthracite Grev Both Sides")
    Anthracite_Grev_White: Optional[bool] = Field(default=None, alias="Anthracite Grev/White")
    Chartwell_White: Optional[bool] = Field(default=None, alias="Chartwell/White")
    Cream_Both_Sides: Optional[bool] = Field(default=None, alias="Cream Both Sides")
    Cream_White: Optional[bool] = Field(default=None, alias="Cream/White")
    Black_Brown_Both_Sides: Optional[bool] = Field(default=None, alias="Black-Brown Both Sides")
    Black_Brown_White: Optional[bool] = Field(default=None, alias="Black-Brown/White")
    Whitegrain_Both_Sides: Optional[bool] = Field(default=None, alias="Whitegrain Both Sides")
    Irish_Oak_Both_Sides: Optional[bool] = Field(default=None, alias="Irish Oak Both Sides")
    Smooth_Anthracite_Grey_White: Optional[bool] = Field(default=None, alias="Smooth Anthracite Grey/White")
    Agate_Grey_White: Optional[bool] = Field(default=None, alias="Agate Grey/White")
    # -- Glass Type --
    Clear: Optional[bool] = Field(default=None, alias="Clear")
    Obscure: Optional[bool] = Field(default=None, alias="Obscure")
    # -- Energy Rating --
    Standard_A_Rated: Optional[bool] = Field(default=None, alias="Standard A Rated")
    A_Rated_Energy_Upgrade: Optional[bool] = Field(default=None, alias="A+ Rated Energy Upgrade")
    A_Triple_Glazed: Optional[bool] = Field(default=None, alias="A++ Triple Glazed")
    # -- Glass Add-ons --
    Toughened_Glass: Optional[bool] = Field(default=None, alias="Toughened Glass")
    Laminated_Glass: Optional[bool] = Field(default=None, alias="Laminated Glass")
    # -- Ventilation --
    Trickle_Vents: Literal["Not Required", "1", "2"] = Field(default="Not Required", alias="Trickle Vents")
    # -- Accessories --
    Fit_Pack: Optional[bool] = Field(default=None, alias="Fit Pack")
"""

    SAMPLE_COMMENT = "White UPVC windows with one fixed light 630 x 600mm (style 1) inc standard cill, A energy rated trickle vent and fit pack Style 1 - 150mm standard cill, white, Clear, A Triple glazed with trickle vents (1) and fit pack Update Apr 24 ce shown prices inc vat  Deduct VAT added/Use URL to access and drop down lists for all styles Note Vents qty in description/comments "

    result = parser_generator(SAMPLE_MODEL, SAMPLE_COMMENT)
    print("\n--- Generated parse_comment() ---\n")
    print(result)
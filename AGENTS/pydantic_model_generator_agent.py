"""
Agent 1 — Generates the NagivationStepsModel Pydantic class as a Python source string.
Input  : html_elements (str), comment (str sample)
Output : Pydantic model source string, validated by ast.parse()
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

AGENT1_PROMPT = """\
# Pydantic Model Generator from HTML Form Elements

You are given a list of HTML form input elements along with their label names.
Your task is to generate a single Pydantic BaseModel class that represents the form.
Follow every rule below strictly.

---

## Rules

### 0. Model Name
Always use `NagivationStepsModel` as the class name.

---

### 1. Field Naming
- Use the label name as the **alias** for every field (exact characters, spaces, symbols included).
- Do not start field name with an underscore or numerical it will throw an error . eg - do not name like "_180mm" instead 'mm180' 
- Use a Python-safe version of the label as the **actual field name** (replace spaces and special characters with underscores, e.g. `"Frame Width (mm)"` → `Frame_Width_mm`).
- Set `model_config = {{"populate_by_name": True}}` so both the alias and the Python name can be used for construction.

---

### 2. Text Inputs (`type="text"`)
- Type: `Optional[str]`
- Default: `None`
- No validators, no `ge`/`le`, no numeric constraints — use plain string.

---

### 3. Radio Buttons (`type="radio"`)
- Do not group radio buttons that share the same `name` attribute.
- Each `<input type="radio">` becomes its own individual field.
- Type: `Optional[bool]`
- Default: `None`

---

### 4. Checkboxes (`type="checkbox"`)
- Each checkbox is its own individual field.
- Type: `Optional[bool]`
- Default: `None`

---

### 5. Select Dropdowns (`<select>`)
- Strip any price suffix (e.g. ` + £X.XX`) from visible option labels to get the map key.
- **If visible label text and option value differ** for any option:
  - Type: `str`
  - Default: `""`
  - Include a `field_validator` with `mode="before"` mapping stripped visible label → actual option value.
- **If visible label text and option value are identical for all options**:
  - Type: `Literal[<all_option_values>]`
  - Default: first option value
  - **Omit the validator entirely** — it is redundant.
- Never mix both approaches for the same field.

---

### 6. Value Mapping (for select fields with differing labels/values)
- Add a `field_validator` with `mode="before"` for every select field where labels and values differ.
- Map stripped visible label text → actual option value.
- Use `map_.get(str(v), str(v))` as the return so unrecognised values pass through unchanged.

---

### 7. No Validation Constraints
- Do not add `ge`, `le`, `min_length`, `max_length`, or any other validators.
- Do not add `description` unless explicitly asked.

---

### 8. Imports
Always include:
```
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator
```

---

## Output style <- IMPORTANT
- model_config = \'{{"populate_by_name"}}\ at beginning of the class
- Return ONLY the raw Python class — no markdown, no code fences, no explanation
- The class must be importable as-is

## HTML Elements
{html_elements}

## Comment
{comment}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_code(response: str) -> str:
    """Strip markdown code fences if the LLM wrapped the output in them."""
    match = re.search(r"```(?:python)?\s*(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return response.strip()


def _validate_code(code: str) -> None:
    """Raise SyntaxError with a clear message if the code cannot be parsed."""
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise SyntaxError(
            f"[Agent 1] Generated model has a syntax error "
            f"at line {e.lineno}: {e.msg}\nSnippet: {e.text}"
        ) from e


def _validate_model_present(code: str) -> None:
    """Ensure the generated code contains the NagivationStepsModel class."""
    tree = ast.parse(code)
    class_names = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    ]
    if "NagivationStepsModel" not in class_names:
        raise ValueError(
            "[Agent 1] Generated code does not contain 'NagivationStepsModel'. "
            f"Found classes: {class_names}"
        )


# ---------------------------------------------------------------------------
# Agent 1
# ---------------------------------------------------------------------------

def model_generator(html_elements: str, comment: str) -> str:
    """
    Generate the NagivationStepsModel Pydantic class source string.

    Parameters
    ----------
    html_elements : str
        Raw HTML of the form inputs (or a structured description of them).
    comment : str
        A sample product comment for the LLM to use as context.

    Returns
    -------
    str
        Validated Pydantic model source, ready to inject into
        the scraper template via Agent 3.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("human", AGENT1_PROMPT),
    ])

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    chain = prompt | llm

    response = chain.invoke({
        "html_elements": html_elements,
        "comment": comment,
    })

    raw = response.content if hasattr(response, "content") else str(response)

    # Clean → validate → return
    code = _extract_code(raw)
    _validate_code(code)
    _validate_model_present(code)

    print("[Agent 1] NagivationStepsModel generated and validated successfully.")
    return code


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    SAMPLE_HTML = """label name - Frame Width (mm):

<input name="framewidth" type="text" required="" class="form-control form-control-md rounded-0 g-mb-10" id="framewidth" data-msg-required="Please enter a frame width" is="dmx-input" value="" placeholder="Please enter a width between 300 - 1300" data-msg-min="Please enter a width greater than 300mm" data-msg-max="Please enter a width less than 1300mm" max="1300" data-rule-max="1300" min="300" data-rule-min="300"/>
                  
label name - Frame Height (mm):

<input name="frameheight" type="text" required="" class="form-control form-control-md rounded-0 g-mb-10" id="frameheight" data-msg-required="Please enter a frame height" is="dmx-input" value="" placeholder="Please enter a height between 300 - 2200" data-msg-min="Please enter a frame height greater than 300mm" data-msg-max="Please enter a frame height less than 2200mm" max="2200" data-rule-max="2200" min="300" data-rule-min="300"/>
                  
label name - No:

<input name="cill" type="radio" required="" class="cill form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" id="cillno" is="dmx-radio" data-msg-required="Please select a cill option" value="No"/>
                   
                    
label name - 85mm Stub:

<input class="cill form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" name="cill" type="radio" id="cill85" is="dmx-radio" value="85mm"/>
                    
                    
label name - Standard 150mm:

<input name="cill" type="radio" class="cill form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" id="cill150" is="dmx-radio" value="150mm"/>
                    
                    
label name - 180mm:

<input name="cill" type="radio" class="cill form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" id="cill180" is="dmx-radio" value="180mm"/>
                    
                    
label name - White:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="White" id="White" data-price="1.00"/>
                    
label name - Oak Both Sides:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Oak Both Sides" id="Oak Both Sides" data-price="1.30"/>
                    
label name - Oak/White:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Oak/White" id="Oak/White" data-price="1.30"/>
                    
label name - Rosewood Both Sides:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Rosewood Both Sides" id="Rosewood Both Sides" data-price="1.30"/>
                    
label name - Rosewood/White:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Rosewood/White" id="Rosewood/White" data-price="1.30"/>
                    
label name - Anthracite Grev Both Sides:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Anthracite Grey Both Sides" id="Anthracite Grey Both Sides" data-price="1.30"/>
                    
label name - Anthracite Grev/White:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Anthracite Grey/White" id="Anthracite Grey/White" data-price="1.30"/>
                    
label name - Chartwell/White:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Chartwell/White" id="Chartwell/White" data-price="1.50"/>
                    
label name - Cream Both Sides:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Cream Both Sides" id="Cream Both Sides" data-price="1.30"/>
                    
label name - Cream/White:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Cream/White" id="Cream/White" data-price="1.30"/>
                    
label name - Black-Brown Both Sides:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Black-Brown Both Sides" id="Black-Brown Both Sides" data-price="1.30"/>
                    
label name - Black-Brown/White:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Black-Brown/White" id="Black-Brown/White" data-price="1.30"/>
                    
label name - Whitegrain Both Sides:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Whitegrain Both Sides" id="Whitegrain Both Sides" data-price="1.30"/>
                    
label name - Irish Oak Both Sides:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Irish Oak Both Sides" id="Irish Oak Both Sides" data-price="1.80"/>
                    
label name - Smooth Anthracite Grey/White:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Smooth Anthracite Grey/White" id="Smooth Anthracite Grey/White" data-price="1.30"/>
                    
label name - Agate Grey/White:

<input name="colour" type="radio" required="" class="colour form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" data-msg-required="Please select a colour" value="Agate Grey/White" id="Agate Grey/White" data-price="1.30"/>
                    
label name - Clear:

<input name="glass" type="radio" required="" class="clear form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" id="clear" onclick="" data-msg-required="Please select a glass type" value="Clear"/>
                   
                  
label name - Obscure:

<input class="obscure form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" name="glass" is="dmx-radio" type="radio" id="obscure" value="Obscure"/>
                  
label name - Standard A Rated:

<input name="argonglass" type="radio" required="" class="thermal form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" is="dmx-radio" id="arated" onclick="" data-msg-required="Please select an energy rating" value="A Rated"/>
                   
                  
label name - A+ Rated Energy Upgrade:

<input class="aplusrated form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" name="argonglass" is="dmx-radio" type="radio" id="aplusrated" value="A+ Rated"/>
                  
label name - A++ Triple Glazed:

<input class="tripleglazed form-control g-hidden-xs-up g-pos-abs g-top-0 g-left-0" name="argonglass" is="dmx-radio" type="radio" id="tripleglazed" value="A++ Triple Glazed"/>
                  
label name - Toughened Glass:

<input class="toughened g-hidden-xs-up g-pos-abs g-top-0 g-left-0" name="toughenedglass" type="checkbox" id="toughened" is="dmx-checkbox" value="Toughened Glass"/>
                  
                  
label name - Laminated Glass:

<input class="laminated g-hidden-xs-up g-pos-abs g-top-0 g-left-0" name="laminatedglass" type="checkbox" id="laminated" is="dmx-checkbox" value="Laminated Glass"/>
                  
                  
label name - Trickle Vents:

<select class="tricklevents g-ml-10" name="tricklevents" id="tricklevents" is="dmx-select">
                <option data-price="0" value="Not Required">Not Required</option>
                <option data-price="15" value="1">1</option>
                <option data-price="30" value="2">2</option>
                </select>
                
label name - Fit Pack:

<input class="fitpack g-hidden-xs-up g-pos-abs g-top-0 g-left-0" name="fitpack" id="fitpack" type="checkbox" data-price="15" is="dmx-checkbox" value="Yes"/>
                 
                  



"""

    SAMPLE_COMMENT = "White UPVC windows with one fixed light 630 x 600mm (style 1) inc standard cill, A energy rated trickle vent and fit pack Style 1 - 150mm standard cill, white, Clear, A Triple glazed with trickle vents (1) and fit pack Update Apr 24 ce shown prices inc vat  Deduct VAT added/Use URL to access and drop down lists for all styles Note Vents qty in description/comments "

    result = model_generator(SAMPLE_HTML, SAMPLE_COMMENT)
    print("\n--- Generated NagivationStepsModel ---\n")
    print(result)
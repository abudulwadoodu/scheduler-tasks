"""
Agent 3 — Fills the scraper template with site-specific values
and writes the final executable script.
"""

import ast
import textwrap
from templat2 import SCRAPER_TEMPLATE
from string import Template

def script_generator(
    comment_parser_function: str,
    steps: str,
    price_xpath: str,
    pydantic_model : str,
    output_path: str = "scraper_output.py",
) -> str:
    """
    Fill the scraper template with the 3 site-specific inputs.

    Parameters
    ----------
    comment_parser_function : str
        Full source of the parse_comment() function (from Agent 2).
    steps : str
        Python list literal of step dicts (from Agent 1).
    price_xpath : str
        XPath string for the price element.
    output_path : str
        Where to write the final script.

    Returns
    -------
    str
        The generated script source code.
    """

    # Dedent in case the caller passes indented source
    parser_clean = textwrap.dedent(comment_parser_function).strip()
    steps_clean  = textwrap.dedent(steps).strip()
    pydantic_clean = textwrap.dedent(pydantic_model).strip()

    script = Template(SCRAPER_TEMPLATE).safe_substitute(
        price_xpath=price_xpath,
        steps=steps_clean,
        comment_parser_function=parser_clean,
        pydantic_model=pydantic_clean,
    )

    # -------------------------
    # Syntax validation
    # -------------------------
    try:
        ast.parse(script)
    except SyntaxError as e:
        raise SyntaxError(
            f"Agent 3: generated script has a syntax error at line {e.lineno}: {e.msg}\n"
            f"Snippet: {e.text}"
        ) from e

    # -------------------------
    # Write to file
    # -------------------------
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(script)

    print(f"[Agent 3] Script written to: {output_path}")
    return script


# =========================
# QUICK TEST
# =========================
if __name__ == "__main__":

    PYDANTIC_MODEL = """
from typing import Optional
from pydantic import BaseModel, Field
class NagivationStepsModel(BaseModel):
    model_config = {"populate_by_name": True}
    # -- Dimensions --
    Frame_Width_mm: Optional[str] = Field(default=None, alias="Frame Width (mm)")
    Frame_Height_mm: Optional[str] = Field(default=None, alias="Frame Height (mm)")

    # -- Cill Options --
    No: Optional[bool] = Field(default=None, alias="No")
    mm_Stub: Optional[bool] = Field(default=None, alias="85mm Stub")
    Standard_150mm: Optional[bool] = Field(default=None, alias="Standard 150mm")
    mm80: Optional[bool] = Field(default=None, alias="180mm")

    # -- Colour Options --
    White: Optional[bool] = Field(default=None, alias="White")
    Oak_Both_Sides: Optional[bool] = Field(default=None, alias="Oak Both Sides")
    Oak_White: Optional[bool] = Field(default=None, alias="Oak/White")
    Rosewood_Both_Sides: Optional[bool] = Field(default=None, alias="Rosewood Both Sides")
    Rosewood_White: Optional[bool] = Field(default=None, alias="Rosewood/White")
    Anthracite_Grey_Both_Sides: Optional[bool] = Field(default=None, alias="Anthracite Grey Both Sides")
    Anthracite_Grey_White: Optional[bool] = Field(default=None, alias="Anthracite Grey/White")
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
    A_Plus_Rated_Energy_Upgrade: Optional[bool] = Field(default=None, alias="A+ Rated Energy Upgrade")
    A_Plus_Plus_Triple_Glazed: Optional[bool] = Field(default=None, alias="A++ Triple Glazed")

    # -- Glass Upgrades --
    Toughened_Glass: Optional[bool] = Field(default=None, alias="Toughened Glass")
    Laminated_Glass: Optional[bool] = Field(default=None, alias="Laminated Glass")

    # -- Extras --
    Trickle_Vents: str = Field(default="", alias="Trickle Vents")
    Fit_Pack: Optional[bool] = Field(default=None, alias="Fit Pack")"""

    # --- paste Agent 2 output here ---
    PARSER = r"""
import re
def parse_comment(comment: str) -> NagivationStepsModel:
    c = comment.lower()

    # --- Dimensions ---
    dim = re.search(r'(\d+)\s*(?:mm)?\s*[x×]\s*(\d+)\s*(?:mm)?', c)
    width, height = (dim.group(1), dim.group(2)) if dim else (None, None)

    # --- Cill Options ---
    if '180mm' in c or '180 mm' in c:
        selected_cill = 'mm80'
    elif '150mm' in c or '150 mm' in c or 'standard cill' in c or 'standard 150' in c:
        selected_cill = 'Standard_150mm'
    elif '85mm' in c or 'stub' in c:
        selected_cill = 'mm_Stub'
    elif 'no cill' in c or 'without cill' in c:
        selected_cill = 'No'
    else:
        selected_cill = 'Standard_150mm'

    # --- Colour Options ---
    # match-order: most specific first
    colour_match_order = [
        ('smooth anthracite grey/white', 'Smooth_Anthracite_Grey_White'),
        ('smooth anthracite grey / white', 'Smooth_Anthracite_Grey_White'),
        ('agate grey/white', 'Agate_Grey_White'),
        ('agate grey / white', 'Agate_Grey_White'),
        ('anthracite grey both sides', 'Anthracite_Grey_Both_Sides'),
        ('anthracite grey/white', 'Anthracite_Grey_White'),
        ('anthracite grey / white', 'Anthracite_Grey_White'),
        ('anthracite grey', 'Anthracite_Grey_White'),
        ('chartwell/white', 'Chartwell_White'),
        ('chartwell / white', 'Chartwell_White'),
        ('chartwell', 'Chartwell_White'),
        ('black-brown both sides', 'Black_Brown_Both_Sides'),
        ('black-brown/white', 'Black_Brown_White'),
        ('black-brown / white', 'Black_Brown_White'),
        ('black brown both sides', 'Black_Brown_Both_Sides'),
        ('black brown/white', 'Black_Brown_White'),
        ('black-brown', 'Black_Brown_White'),
        ('rosewood both sides', 'Rosewood_Both_Sides'),
        ('rosewood/white', 'Rosewood_White'),
        ('rosewood / white', 'Rosewood_White'),
        ('rosewood', 'Rosewood_White'),
        ('irish oak both sides', 'Irish_Oak_Both_Sides'),
        ('irish oak', 'Irish_Oak_Both_Sides'),
        ('oak both sides', 'Oak_Both_Sides'),
        ('oak/white', 'Oak_White'),
        ('oak / white', 'Oak_White'),
        ('oak', 'Oak_White'),
        ('cream both sides', 'Cream_Both_Sides'),
        ('cream/white', 'Cream_White'),
        ('cream / white', 'Cream_White'),
        ('cream', 'Cream_White'),
        ('whitegrain both sides', 'Whitegrain_Both_Sides'),
        ('whitegrain', 'Whitegrain_Both_Sides'),
        ('white upvc', None),
        ('white', None),
    ]
    # field-name order (for output)
    colour_field_order = [
        'White', 'Oak_Both_Sides', 'Oak_White', 'Rosewood_Both_Sides', 'Rosewood_White',
        'Anthracite_Grey_Both_Sides', 'Anthracite_Grey_White', 'Chartwell_White',
        'Cream_Both_Sides', 'Cream_White', 'Black_Brown_Both_Sides', 'Black_Brown_White',
        'Whitegrain_Both_Sides', 'Irish_Oak_Both_Sides',
        'Smooth_Anthracite_Grey_White', 'Agate_Grey_White',
    ]

    selected_colour = None
    base_white = False
    for pattern, field in colour_match_order:
        if pattern in c:
            if field is None:
                base_white = True
            else:
                selected_colour = field
            break

    # --- Glass Type ---
    if 'obscure' in c:
        selected_glass = 'Obscure'
    else:
        selected_glass = 'Clear'

    # --- Energy Rating ---
    if 'a++' in c or 'triple glazed' in c or 'triple-glazed' in c:
        selected_rating = 'A_Plus_Plus_Triple_Glazed'
    elif 'a+' in c:
        selected_rating = 'A_Plus_Rated_Energy_Upgrade'
    elif 'a rated' in c or 'a-rated' in c or 'a energy' in c:
        selected_rating = 'Standard_A_Rated'
    else:
        selected_rating = 'Standard_A_Rated'

    # --- Glass Upgrades (checkboxes) ---
    toughened = True if 'toughened' in c else None
    laminated = True if 'laminated' in c else None

    # --- Trickle Vents (select) ---
    trickle_options = ['1', '2', '3', '4', '5', '6']
    trickle_vents = ''
    if 'trickle vent' in c or 'trickle vents' in c:
        qty_match = re.search(r'trickle\s+vents?\s*[(\[]?\s*(\d+)\s*[)\]]?|[(\[x×]\s*(\d+)\s*[)\]]?\s*trickle|(\d+)\s*[x×]\s*trickle', c)
        if not qty_match:
            qty_match = re.search(r'vents?\s*[(\[]?\s*(\d+)', c)
        if qty_match:
            qty = next(g for g in qty_match.groups() if g is not None)
            trickle_vents = qty if qty in trickle_options else '1'
        else:
            trickle_vents = '1'

    # --- Fit Pack (checkbox) ---
    fit_pack = True if 'fit pack' in c else None

    # --- Build and return model ---
    return NagivationStepsModel(
        Frame_Width_mm=width,
        Frame_Height_mm=height,
        No=True if selected_cill == 'No' else None,
        mm_Stub=True if selected_cill == 'mm_Stub' else None,
        Standard_150mm=True if selected_cill == 'Standard_150mm' else None,
        mm80=True if selected_cill == 'mm80' else None,
        **{
            field: (True if (not base_white and field == selected_colour) else None)
            for field in colour_field_order
        },
        Clear=True if selected_glass == 'Clear' else None,
        Obscure=True if selected_glass == 'Obscure' else None,
        Standard_A_Rated=True if selected_rating == 'Standard_A_Rated' else None,
        A_Plus_Rated_Energy_Upgrade=True if selected_rating == 'A_Plus_Rated_Energy_Upgrade' else None,
        A_Plus_Plus_Triple_Glazed=True if selected_rating == 'A_Plus_Plus_Triple_Glazed' else None,
        Toughened_Glass=toughened,
        Laminated_Glass=laminated,
        Trickle_Vents=trickle_vents,
        Fit_Pack=fit_pack,
    )
"""

    # --- paste Agent 1 output here ---
    STEPS = """[
    {'label': 'Frame Width (mm)',  'xpath': "//input[@id='framewidth']",              'type': 'text',     'tag': 'input'},
    {'label': 'Frame Height (mm)', 'xpath': "//input[@id='frameheight']",             'type': 'text',     'tag': 'input'},
    {'label': 'No',                'xpath': "//input[@id='cillno']",                  'type': 'radio',    'tag': 'input'},
    {'label': '85mm Stub',         'xpath': "//input[@id='cill85']",                  'type': 'radio',    'tag': 'input'},
    {'label': 'Standard 150mm',    'xpath': "//input[@id='cill150']",                 'type': 'radio',    'tag': 'input'},
    {'label': '180mm',             'xpath': "//input[@id='cill180']",                 'type': 'radio',    'tag': 'input'},
    {'label': 'White',             'xpath': "//input[@id='White']",                   'type': 'radio',    'tag': 'input'},
    {'label': 'Oak Both Sides',    'xpath': "//input[@id='Oak Both Sides']",           'type': 'radio',    'tag': 'input'},
    {'label': 'Oak/White',         'xpath': "//input[@id='Oak/White']",               'type': 'radio',    'tag': 'input'},
    {'label': 'Rosewood Both Sides',       'xpath': "//input[@id='Rosewood Both Sides']",       'type': 'radio', 'tag': 'input'},
    {'label': 'Rosewood/White',            'xpath': "//input[@id='Rosewood/White']",            'type': 'radio', 'tag': 'input'},
    {'label': 'Anthracite Grey Both Sides','xpath': "//input[@id='Anthracite Grey Both Sides']",'type': 'radio', 'tag': 'input'},
    {'label': 'Anthracite Grey/White',     'xpath': "//input[@id='Anthracite Grey/White']",     'type': 'radio', 'tag': 'input'},
    {'label': 'Chartwell/White',           'xpath': "//input[@id='Chartwell/White']",           'type': 'radio', 'tag': 'input'},
    {'label': 'Cream Both Sides',          'xpath': "//input[@id='Cream Both Sides']",          'type': 'radio', 'tag': 'input'},
    {'label': 'Cream/White',               'xpath': "//input[@id='Cream/White']",               'type': 'radio', 'tag': 'input'},
    {'label': 'Black-Brown Both Sides',    'xpath': "//input[@id='Black-Brown Both Sides']",    'type': 'radio', 'tag': 'input'},
    {'label': 'Black-Brown/White',         'xpath': "//input[@id='Black-Brown/White']",         'type': 'radio', 'tag': 'input'},
    {'label': 'Whitegrain Both Sides',     'xpath': "//input[@id='Whitegrain Both Sides']",     'type': 'radio', 'tag': 'input'},
    {'label': 'Irish Oak Both Sides',      'xpath': "//input[@id='Irish Oak Both Sides']",      'type': 'radio', 'tag': 'input'},
    {'label': 'Smooth Anthracite Grey/White', 'xpath': "//input[@id='Smooth Anthracite Grey/White']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Agate Grey/White',          'xpath': "//input[@id='Agate Grey/White']",          'type': 'radio', 'tag': 'input'},
    {'label': 'Clear',             'xpath': "//input[@id='clear']",                   'type': 'radio',    'tag': 'input'},
    {'label': 'Obscure',           'xpath': "//input[@id='obscure']",                 'type': 'radio',    'tag': 'input'},
    {'label': 'Standard A Rated',  'xpath': "//input[@id='arated']",                  'type': 'radio',    'tag': 'input'},
    {'label': 'A++ Triple Glazed', 'xpath': "//input[@id='tripleglazed']",            'type': 'radio',    'tag': 'input'},
    {'label': 'Toughened Glass',   'xpath': "//input[@id='toughened']",               'type': 'checkbox', 'tag': 'input'},
    {'label': 'Laminated Glass',   'xpath': "//input[@id='laminated']",               'type': 'checkbox', 'tag': 'input'},
    {'label': 'Trickle Vents',     'xpath': "//select[@id='tricklevents']",           'type': '',         'tag': 'select'},
    {'label': 'Fit Pack',          'xpath': "//input[@id='fitpack']",                 'type': 'checkbox', 'tag': 'input'},
]"""

    PRICE_XPATH = '//span[contains(@class, "totalpricevisible")]'

    script_generator(
        comment_parser_function=PARSER,
        steps=STEPS,
        price_xpath=PRICE_XPATH,
        pydantic_model = PYDANTIC_MODEL,
        output_path="scraper_output2.py",
    )
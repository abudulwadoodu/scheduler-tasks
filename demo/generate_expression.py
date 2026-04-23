# initialize model

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import os
from take_screenshot import capture_screenshot
load_dotenv()

model = ChatOpenAI(model="gpt-5.2")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # module level, before all functions

# define pydantic model for output

from pydantic import BaseModel
from typing import Optional, Literal, List


class Step2Output(BaseModel):
    status: Literal["ok", "fail"]

    expression: Optional[str]
    """
    Mathematical expression using variable `price`,
    e.g. '{price} * (1000 / 3.85)'
    """

    explanation: Optional[str]
    """
    Short factual justification describing which explicit evidence
    was used to form the expression.
    Must NOT include calculations or algebraic transformations.
    """

    evidence_used: List[str]
    """
    Exact seller-visible texts or table rows used
    (e.g. 'Weight/Metre (Kg): 3.85')
    """
# create structured ouptut model

structured_model = model.with_structured_output(Step2Output)


import ast
import operator as op


# Allowed operators
_ALLOWED_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
}


class MathExpressionError(Exception):
    pass


def evaluate_math_expression(expression: str) -> float:
    """
    Safely evaluate a mathematical expression consisting of
    numbers, + - * / and parentheses.

    Args:
        expression (str): math expression, e.g. "(1000 / 3.85)"

    Returns:
        float: evaluated result

    Raises:
        MathExpressionError: if expression is invalid or unsafe
    """

    try:
        parsed = ast.parse(expression, mode="eval")
        return _eval_node(parsed.body)

    except Exception as e:
        raise MathExpressionError(f"Invalid math expression: {expression}") from e


def _eval_node(node):
    if isinstance(node, ast.Num):  # Python <3.8
        return node.n

    if isinstance(node, ast.Constant):  # Python 3.8+
        if isinstance(node.value, (int, float)):
            return node.value
        raise MathExpressionError("Only numeric constants allowed")

    if isinstance(node, ast.BinOp):
        if type(node.op) not in _ALLOWED_OPERATORS:
            raise MathExpressionError(f"Operator {type(node.op)} not allowed")

        left = _eval_node(node.left)
        right = _eval_node(node.right)

        return _ALLOWED_OPERATORS[type(node.op)](left, right)

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return -_eval_node(node.operand)
        raise MathExpressionError("Unary operator not allowed")

    raise MathExpressionError(f"Unsupported expression element: {type(node)}")

import re
from typing import Dict


def execute_llm_expression(
    raw_expression: str,
    variables: Dict[str, float],
) -> float:
    """
    Execute a math expression produced by the LLM.

    Steps:
    1. Template variables (price -> {price})
    2. Substitute runtime values
    3. Validate expression safety
    4. Evaluate using safe math executor

    Args:
        raw_expression: e.g. "price * (1000 / 0.89)"
        variables: e.g. {"price": 10}

    Returns:
        float result

    Raises:
        ValueError if expression is unsafe or invalid
    """

    # --- Step 1: template variables ---
    for var in variables.keys():
        raw_expression = re.sub(
            rf"\b{var}\b",
            f"{{{var}}}",
            raw_expression
        )

    # --- Step 2: substitute variables ---
    expr = raw_expression
    for key, value in variables.items():
        if not isinstance(value, (int, float)):
            raise ValueError(f"Invalid value for {key}: {value}")
        expr = expr.replace(f"{{{key}}}", str(value))

    # --- Step 3: ensure no unresolved placeholders remain ---
    if re.search(r"\{[a-zA-Z_]+\}", expr):
        raise ValueError(f"Incorrect Math Exp: {expr}")

    # --- Step 4: validate allowed characters only ---
    if not re.fullmatch(r"[0-9\.\+\-\*\/\(\)\s]+", expr):
        raise ValueError(f"Incorrect Math Exp: {expr}")

    # --- Step 5: evaluate using Step-3 calculator ---
    return evaluate_math_expression(expr)

# Version2 :  two systems prompts;switch to prompt that emphasize "Comments" if information cannot be inferred from webpage
  
SYSTEM_PROMPT_SELLER = """You are a pricing conversion engine.

Your task is to generate a MATHEMATICAL EXPRESSION to convert given unit price to target unit price
from the priced quantity unit to the target unit.

You are provided with:
- a screenshot of webpage of a product
- "target_unit"
- a user "comment" might be helpful to derive a MATHEMATICAL EXPRESSION

<INSTRUCTIONS>
- Infer the quanity and given unit of the product from the webpage
- If the given unit and target unit is not same, identify the conversion factor from webpage. For example the qiven quantity is in liter and target quantity in Kg, check for denisty is the specs or more info table
- If the given unit and target unit is same, mathematical experssion is straight forward


STRICT RULES:
- Do NOT assume material properties or typical values.
- Do NOT restate steps.
- Do NOT calculate numeric results.
- Do NOT algebraically rewrite or invert expressions.
- Use ONLY numeric values explicitly visible in the screenshot or evidence.
- Do NOT assume material properties.
- Do NOT invent constants.
- If the required conversion factor is not explicitly visible, return FAIL.

VARIABLE RULES:
- Use the variable name `price` for the price that will be substituted
- All other values must be numeric literals taken directly from the screenshot.

ALLOWED OPERATIONS:
- +  -  *  /
- parentheses ( )


- return a valid math expression with variable "price" can be subtituted in python math evaulator (e.g. `{/{price}/} * (1000 / 3.85)`), OR
- the single word: FAIL

"""


SYSTEM_PROMPT_COMMENT = """You are a pricing conversion engine operating in COMMENT-PRIMARY mode.

The webpage does NOT provide an explicit conversion between the priced unit
and the target unit.

Your task is to generate a MATHEMATICAL EXPRESSION using the user-provided
comment as the PRIMARY source of quantity or conversion information.

You are provided with:
- target_unit
- a user comment

RULES:
- Treat the comment as a claim about how the product is sold.
- Validate that the comment does NOT contradict visible product details
  (dimensions, material type, product category).
- Do NOT assume typical sizes or industry standards.
- If the comment is ambiguous or contradicts product details, return FAIL.
- You may use simple arithmetic implied directly by the comment
  (e.g. "price is for 5m" → divide by 5).

STRICT CONSTRAINTS:
- Do NOT invent numeric values not present in the comment.
- Do NOT calculate final numeric results.
- Do NOT rewrite or invert expressions.
- Use variable `price` only.

OUTPUT:
Return a JSON object matching the schema.
If conversion cannot be safely derived, return FAIL.

Billing accuracy is required."""


# Version2 : 

from langchain_core.messages import HumanMessage, SystemMessage
import asyncio
import base64
import pandas as pd


async def run_step2_with_retry(
    *,
    structured_model,
    encoded_image: str,
    row,
    max_retries: int = 1,
):
    """
    Try seller-evidence prompt first.
    Retry once with comment-primary prompt if needed.
    """

    attempts = [
        ("SCREENSHOT", SYSTEM_PROMPT_SELLER),
        ("COMMENT", SYSTEM_PROMPT_COMMENT),
    ]

    last_error = None

    for attempt_name, system_prompt in attempts[: max_retries + 1]:
        try:
            user_prompt = (
                f"Comment: {row.get('Comments')}\n"
                f"Target Unit: {row.get('TargetUnit')}\n"
                f"Screenshot:"
            )

            human_msg = HumanMessage(
                [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image",
                        "base64": encoded_image,
                        "mime_type": "image/png",
                        "detail": "low",
                    },
                ]
            )

            system_msg = SystemMessage(system_prompt)

            response: Step2Output = await structured_model.ainvoke(
                [system_msg, human_msg]
            )

            response_json = response.model_dump()

            if response.status == "ok" and response.expression:
            
                return response, attempt_name, None

            last_error = f"{attempt_name}_INVALID_OUTPUT"
            

        except Exception as e:
            last_error = f"{attempt_name}_ERROR: {e}"
    

    return response, attempt_name, last_error


async def run_step2_and_3_on_dataset_v2(
    dataset: pd.DataFrame,
    structured_model,
    semaphore_limit: int = 5,
) -> pd.DataFrame:

    semaphore = asyncio.Semaphore(semaphore_limit)

    dataset = dataset.copy()
    dataset["final_unit_price"] = None
    dataset["final_expression"] = None
    dataset["explanation"] = None
    dataset["error"] = None
    dataset["conversion_mode"] = None

    async def process_row(idx: int, row: pd.Series):
        # async with semaphore:
        #     try:
        #         extracted_price = float(row["ExtractedPrice"])
        #         image_path = capture_screenshot(row['URL'])

        #         # ---- encode image ----
        #         with open(image_path, "rb") as f:
        #             encoded_image = base64.b64encode(f.read()).decode("utf-8")
        async with semaphore:
            try:
                extracted_price = float(row["ExtractedPrice"])
                
                # Run sync playwright in a thread executor
                loop = asyncio.get_event_loop()
                image_path = await loop.run_in_executor(None, capture_screenshot, row['URL'])

                # ---- encode image ----
                with open(image_path, "rb") as f:
                    encoded_image = base64.b64encode(f.read()).decode("utf-8")

                # ---- Step 2 (with retry) ----
                response, mode, error = await run_step2_with_retry(
                    structured_model=structured_model,
                    encoded_image=encoded_image,
                    row=row,
                )

                

                if error:
                    dataset.at[idx, "error"] = error
        

                expr = response.expression
                explanation = response.explanation

                response_json = response.model_dump()


                # ---- Step 3 (execution) ----
                try:
                    result = execute_llm_expression(
                        raw_expression=expr,
                        variables={"price": extracted_price},
                    )
                except Exception as exec_error:
                    dataset.at[idx, "error"] = f"EXECUTION_ERROR: {exec_error}"
                    dataset.at[idx, "final_expression"] = expr
                    dataset.at[idx, "explanation"] = explanation
                    return

    
                dataset.at[idx, "final_unit_price"] = result
                dataset.at[idx, "final_expression"] = expr
                dataset.at[idx, "explanation"] = explanation
                dataset.at[idx, "conversion_mode"] = mode

                
            except Exception as fatal_error:
        
                dataset.at[idx, "error"] = f"FATAL_ERROR: {fatal_error}"
                print("error : ",fatal_error)

    tasks = [
        process_row(idx, row)
        for idx, row in dataset.iterrows()
    ]

    await asyncio.gather(*tasks)

    return dataset


if __name__ == "__main__":
    input_path = os.path.join(BASE_DIR, "output", "scenario_1.xlsx")
    output_path = os.path.join(BASE_DIR, "output", "scenario_1_output.xlsx")

    
    dataset = pd.read_excel(input_path)
    output = asyncio.run(run_step2_and_3_on_dataset_v2(
        dataset=dataset[:5],
        structured_model=structured_model,
        semaphore_limit=5,
    ))
    print(output)
    output.to_excel(output_path)
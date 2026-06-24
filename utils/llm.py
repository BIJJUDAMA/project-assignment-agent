"""
LLM utility helpers.
"""


def extract_json_from_response(response_text: str) -> str:
    """
    Strip <think>...</think> blocks and markdown code fences from a model
    response, returning clean text suitable for json.loads().

    Args:
        response_text: Raw text returned by the LLM, which may contain
                       <think> reasoning blocks and/or ```json fences.

    Returns:
        Cleaned string with reasoning blocks and code fences removed.
    """
    response_text = response_text.strip()

    # Strip <think>...</think> reasoning blocks (e.g. from QwQ / DeepSeek models)
    if "<think>" in response_text:
        think_start = response_text.find("<think>")
        think_end = response_text.find("</think>")
        if think_start != -1 and think_end != -1:
            response_text = response_text[:think_start] + response_text[think_end + 8:]

    # Strip leading ```json fence
    if response_text.startswith("```json"):
        response_text = response_text[7:]

    # Strip trailing ``` fence
    if response_text.endswith("```"):
        response_text = response_text[:-3]

    return response_text

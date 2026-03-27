import os
import time
import logging
from google import genai
from google.genai.types import GenerateContentResponse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.getenv("API_KEY"))
model = "gemini-2.5-flash"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def clean_output(text):
    if not text:
        return ""
    for s in ["*", "#", "`"]:
        text = text.replace(s, "")
    return text.strip()


def analyze_code(agent_type, code, guidelines):
    if not code or not code.strip():
        logger.warning(f"{agent_type.upper()}: Empty code — skipping")
        return ""

    prompt = f"""
You are a strict and professional {agent_type} code reviewer.

Return output in EXACT format:

Problem:
<one line problem OR 'No issue found in the code'>

Fix:
<clear fix in max 3 lines in easy language OR 'No fix needed'>

STRICT RULES:
- Only return Problem and Fix
- No Analysis section
- No extra text
- No markdown or symbols
- Be concise

Code:
{code[:1200]}

Context:
{guidelines[:800]}
"""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Running {agent_type.upper()} analysis (attempt {attempt})...")

            response: GenerateContentResponse = client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "temperature": 0.4,
                    "top_p": 0.8,
                    "max_output_tokens": 1000
                }
            )

            if not response:
                raise ValueError("Empty response from model")

            if hasattr(response, "text") and response.text:
                result = clean_output(response.text)
            else:
                result = clean_output(response.candidates[0].content.parts[0].text)

            logger.info(f"{agent_type.upper()} analysis complete")
            return result

        except Exception as e:
            logger.warning(f"{agent_type.upper()} attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"{agent_type.upper()} failed after {MAX_RETRIES} attempts — skipping chunk")
                return ""

    return ""


def security_agent(code, guidelines):
    return analyze_code("security", code, guidelines)


def performance_agent(code, guidelines):
    return analyze_code("performance", code, guidelines)


def style_agent(code, guidelines):
    return analyze_code("style", code, guidelines)

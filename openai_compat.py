import os
import re
import time
import uuid
import logging
import argparse

import requests
from flask import Flask, jsonify, request


app = Flask(__name__)

LOG_FILE = os.path.join(os.path.dirname(__file__), "openai_compat.log")
logger = logging.getLogger("openai_compat")

LIBRETRANSLATE_URL = os.getenv("LIBRETRANSLATE_URL", "http://127.0.0.1:5000").rstrip("/")
SOURCE_LANGUAGE = os.getenv("LIBRETRANSLATE_SOURCE", "auto")
TARGET_LANGUAGE = os.getenv("LIBRETRANSLATE_TARGET", "zh")
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("OPENAI_COMPAT_MODEL", "libretranslate")
TRANSLATION_TEXT_MARKER = "要翻译的文本"
PROMPT_ONLY_MARKERS = (
    "you are a professional translator",
    "translate the following text to simplified chinese",
    "only return the translated text",
    "text to translate:",
    "translation:",
    "你是个专业的翻译家",
    "将以下文字翻译为简化中文",
    "只返回已翻译的文本",
    "要翻译的文本",
    "翻译 :",
    "翻译：",
)
PROMPT_ONLY_TEXTS = {
    "you are a professional translator. translate the following text to simplified chinese. only return the translated text without any explanation or additional information.",
    "你是个专业的翻译家。将以下文字翻译为简化中文。只返回已翻译的文本，而不作任何解释或附加信息。",
    "text to translate:",
    "translation:",
    "要翻译的文本 :",
    "翻译 :",
}


def error_response(message, status=400, error_type="invalid_request_error"):
    return jsonify({"error": {"message": message, "type": error_type}}), status


def configure_logging(mode):
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    if mode == "off":
        root_logger.setLevel(logging.CRITICAL + 1)
        logging.getLogger("werkzeug").setLevel(logging.CRITICAL + 1)
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def check_api_key():
    if not API_KEY:
        return None
    authorization = request.headers.get("Authorization", "")
    if authorization != f"Bearer {API_KEY}":
        return error_response("Invalid API key.", 401, "authentication_error")
    return None


def message_text(messages):
    user_messages = []
    fallback_messages = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in {"system", "user", "assistant"}:
            raise ValueError(f"Unsupported message role: {role}")
        if not isinstance(content, str):
            raise ValueError("Only string message content is supported.")
        if content:
            if role == "user":
                user_messages.append(content)
            elif role == "assistant":
                fallback_messages.append(content)
    if user_messages:
        text = user_messages[-1]
    elif fallback_messages:
        text = fallback_messages[-1]
    else:
        raise ValueError("messages must contain text.")
    text = re.sub(
        r"(?is)^.*?(?:text\s+to\s+translate|要翻译的文本)\s*[:：]\s*(.*?)"
        r"\s*(?:translation|翻译)\s*[:：]\s*$",
        r"\1",
        text,
    )
    marker_index = text.find(TRANSLATION_TEXT_MARKER)
    if marker_index >= 0:
        text = text[marker_index + len(TRANSLATION_TEXT_MARKER):]
    text = text.lstrip(" ：:。\r\n")
    text = re.sub(r"\s*翻译\s*[:：]\s*$", "", text)
    return text.rstrip()


def is_prompt_only(text):
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    if not normalized:
        return True
    if normalized in PROMPT_ONLY_TEXTS:
        return True
    if normalized in {
        marker.lower()
        for marker in PROMPT_ONLY_MARKERS
        if marker.endswith(":") or marker.endswith("：")
    }:
        return True
    chinese_prompt = (
        "你是个专业的翻译家" in normalized
        and "将以下文字翻译为简化中文" in normalized
        and "只返回已翻译的文本" in normalized
    )
    english_prompt = (
        "you are a professional translator" in normalized
        and "translate the following text to simplified chinese" in normalized
        and "only return the translated text" in normalized
    )
    return chinese_prompt or english_prompt


@app.get("/v1/models")
def models():
    auth_error = check_api_key()
    if auth_error:
        return auth_error
    now = int(time.time())
    return jsonify(
        {
            "object": "list",
            "data": [
                {
                    "id": MODEL_NAME,
                    "object": "model",
                    "created": now,
                    "owned_by": "local",
                }
            ],
        }
    )


@app.post("/v1/chat/completions")
def chat_completions():
    request_id = f"chatcmpl-{uuid.uuid4().hex}"
    auth_error = check_api_key()
    if auth_error:
        logger.warning("request_id=%s authentication_failed", request_id)
        return auth_error

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        logger.warning("request_id=%s invalid_json_body", request_id)
        return error_response("Request body must be a JSON object.")
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        logger.warning("request_id=%s invalid_messages", request_id)
        return error_response("messages must be a non-empty array.")
    if body.get("stream") is True:
        logger.warning("request_id=%s unsupported_stream", request_id)
        return error_response("stream=true is not supported by this adapter.")

    try:
        text = message_text(messages)
    except ValueError as exc:
        logger.warning("request_id=%s message_error=%s", request_id, exc)
        return error_response(str(exc))
    if not text:
        logger.warning("request_id=%s empty_text", request_id)
        return error_response("messages must contain text.")

    if is_prompt_only(text):
        translated_text = ""
        logger.info(
            "request_id=%s prompt_only=true input=%r output=%r",
            request_id,
            text,
            translated_text,
        )
    else:
        logger.info("request_id=%s prompt_only=false input=%r", request_id, text)
        try:
            response = requests.post(
                f"{LIBRETRANSLATE_URL}/translate",
                json={
                    "q": text,
                    "source": SOURCE_LANGUAGE,
                    "target": TARGET_LANGUAGE,
                    "format": "text",
                },
                timeout=120,
            )
            response.raise_for_status()
            translated_text = response.json()["translatedText"]
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.exception("request_id=%s upstream_error", request_id)
            return error_response(
                f"LibreTranslate request failed: {exc}",
                502,
                "upstream_error",
            )

    now = int(time.time())
    logger.info(
        "request_id=%s response_content=%r",
        request_id,
        translated_text,
    )
    return jsonify(
        {
            "id": request_id,
            "object": "chat.completion",
            "created": now,
            "model": body.get("model", MODEL_NAME),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": translated_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(text.split()),
                "completion_tokens": len(translated_text.split()),
                "total_tokens": len(text.split()) + len(translated_text.split()),
            },
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--logging",
        choices=("off", "full"),
        default=os.getenv("OPENAI_COMPAT_LOGGING", "full"),
        help="Set logging mode: off or full.",
    )
    args = parser.parse_args()
    configure_logging(args.logging)
    app.run(
        host=os.getenv("OPENAI_COMPAT_HOST", "127.0.0.1"),
        port=int(os.getenv("OPENAI_COMPAT_PORT", "8000")),
    )

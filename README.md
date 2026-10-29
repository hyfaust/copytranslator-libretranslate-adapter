# OpenAI-Compatible LibreTranslate Adapter

[English](README.md) | [简体中文](README_zh.md)

---

> A single-file OpenAI-compatible translation endpoint that lets CopyTranslator use LibreTranslate for local translation.

## Overview

`openai_compat.py` was written for CopyTranslator. It is a single-file Flask application that exposes a running LibreTranslate instance through an OpenAI-style HTTP API, so CopyTranslator can use LibreTranslate for local translation through its OpenAI-compatible API settings.

The adapter accepts OpenAI chat completion requests, extracts the text to translate, forwards it to LibreTranslate, and returns the translated text in an OpenAI chat completion response.

## How It Works

```mermaid
flowchart LR
    Client["CopyTranslator"] -->|"POST /v1/chat/completions"| Adapter["Adapter :8000"]
    Adapter -->|"POST /translate"| LT["LibreTranslate :5000"]
    LT -->|"translatedText"| Adapter
    Adapter -->|"chat.completion"| Client
```

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [CopyTranslator Configuration](#copytranslator-configuration)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Behavior and Limitations](#behavior-and-limitations)
- [Troubleshooting](#troubleshooting)

## Requirements

- Python 3 with the `flask` and `requests` packages.
- A reachable LibreTranslate instance. The default URL is `http://127.0.0.1:5000`.

## Quick Start

Install the dependencies:

```bash
python -m pip install flask requests
```

Start LibreTranslate separately, then start the adapter:

```bash
python openai_compat.py
```

The adapter listens on `127.0.0.1:8000` by default. To disable request logging:

```bash
python openai_compat.py --logging off
```

Configure CopyTranslator's OpenAI-compatible API with:

- **API key:** any value (authentication is disabled by default)
- **Base URL:** `http://127.0.0.1:8000/v1`
- **Model:** `libretranslate`

The adapter translates the text in chat messages to Chinese by default. Set `LIBRETRANSLATE_TARGET` before starting the adapter to change the target language, for example `en` or `ja`.

## CopyTranslator Configuration

Open CopyTranslator's OpenAI-compatible API settings and use:

| Setting | Value |
|---------|-------|
| API key | Any value, unless `OPENAI_API_KEY` is set |
| Base URL | `http://127.0.0.1:8000/v1` |
| Model | `libretranslate` (configurable with `OPENAI_COMPAT_MODEL`) |

CopyTranslator only needs translation, so no other OpenAI capabilities are required.

## Configuration

Environment variables are read when the adapter process starts:

| Variable | Default | Description |
|----------|---------|-------------|
| `LIBRETRANSLATE_URL` | `http://127.0.0.1:5000` | LibreTranslate base URL |
| `LIBRETRANSLATE_SOURCE` | `auto` | Source language sent to LibreTranslate |
| `LIBRETRANSLATE_TARGET` | `zh` | Target language sent to LibreTranslate |
| `OPENAI_API_KEY` | unset | When set, clients must send `Authorization: Bearer <value>` |
| `OPENAI_COMPAT_MODEL` | `libretranslate` | Model ID returned by `/v1/models` and used as the default response model |
| `OPENAI_COMPAT_HOST` | `127.0.0.1` | Adapter bind host |
| `OPENAI_COMPAT_PORT` | `8000` | Adapter bind port |
| `OPENAI_COMPAT_LOGGING` | `full` | `off` disables request logging; `full` logs to the console and `openai_compat.log` |

The adapter also accepts `--logging off` or `--logging full`, which overrides `OPENAI_COMPAT_LOGGING` for that process.

### Optional Authentication

PowerShell:

```powershell
$env:OPENAI_API_KEY = "change-this-secret"
```

POSIX shell:

```bash
export OPENAI_API_KEY="change-this-secret"
```

If `OPENAI_API_KEY` is set, both `/v1/models` and `/v1/chat/completions` require the matching bearer token.

## API Endpoints

### `GET /v1/models`

Returns an OpenAI model list containing the configured model.

### `POST /v1/chat/completions`

Translates the text from the last user message and returns it as an assistant message.

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"libretranslate","messages":[{"role":"user","content":"Hello, world!"}]}'
```

The response follows the OpenAI chat completion shape:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "libretranslate",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "你好，世界！"},
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 2,
    "completion_tokens": 2,
    "total_tokens": 4
  }
}
```

Errors use the OpenAI error shape:

```json
{"error": {"message": "Invalid API key.", "type": "authentication_error"}}
```

## Behavior and Limitations

- The adapter is intended for CopyTranslator's OpenAI-compatible translation integration.
- The adapter translates text; it does not implement language-model generation.
- Tool calls, multimodal content, and streaming responses are not supported.
- `stream: true` is rejected with a `400` error.
- Only string `content` is supported for `system`, `user`, and `assistant` messages.
- The last `user` message is translated; if there is no user message, the last `assistant` message is used.
- Recognized translator prompt templates are treated as prompt-only and return an empty assistant message.
- Upstream LibreTranslate failures return a `502` error with type `upstream_error`.
- Requests to LibreTranslate time out after 120 seconds.
- With the default URLs, the adapter and LibreTranslate both run locally, so translated text does not leave the local machine.

## Troubleshooting

- **Port already in use**: Another process is listening on `8000`. Stop it or set `OPENAI_COMPAT_PORT` to a free port.
- **`401 Invalid API key`**: `OPENAI_API_KEY` is set and the client is not sending the same bearer token.
- **`502 LibreTranslate request failed`**: LibreTranslate is not reachable at `LIBRETRANSLATE_URL`, or the requested language pair is unavailable.
- **Empty translated text**: The request matched a prompt-only translation template. Send only the text to translate.
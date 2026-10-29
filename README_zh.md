# OpenAI 兼容的 LibreTranslate 适配器

[English](README.md) | [简体中文](README_zh.md)

---

> 基于 LibreTranslate 的单文件 OpenAI 兼容翻译端点，用于在 CopyTranslator 中接入 LibreTranslate 进行本地翻译。

## 概述

`openai_compat.py` 专为 CopyTranslator 编写。它是一个单文件 Flask 应用，通过 OpenAI 风格的 HTTP API 对外暴露正在运行的 LibreTranslate 实例，使 CopyTranslator 可以通过其 OpenAI 兼容 API 设置接入 LibreTranslate 进行本地翻译。

适配器接收 OpenAI 聊天补全请求，提取待翻译文本，转发给 LibreTranslate，并以 OpenAI 聊天补全响应的形式返回译文。

## 工作原理

```mermaid
flowchart LR
    Client["CopyTranslator"] -->|"POST /v1/chat/completions"| Adapter["Adapter :8000"]
    Adapter -->|"POST /translate"| LT["LibreTranslate :5000"]
    LT -->|"translatedText"| Adapter
    Adapter -->|"chat.completion"| Client
```

## 目录

- [概述](#概述)
- [工作原理](#工作原理)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [CopyTranslator 配置](#copytranslator-配置)
- [配置项](#配置项)
- [API 端点](#api-端点)
- [行为与限制](#行为与限制)
- [故障排查](#故障排查)

## 环境要求

- Python 3，以及 `flask` 和 `requests` 包。
- 可访问的 LibreTranslate 实例。默认 URL 为 `http://127.0.0.1:5000`。

## 快速开始

安装依赖：

```bash
python -m pip install flask requests
```

单独启动 LibreTranslate，然后启动适配器：

```bash
python openai_compat.py
```

适配器默认监听 `127.0.0.1:8000`。关闭请求日志：

```bash
python openai_compat.py --logging off
```

然后在 CopyTranslator 的 OpenAI 兼容 API 设置中填写：

- **API key：** 任意值（默认关闭认证）
- **Base URL：** `http://127.0.0.1:8000/v1`
- **模型：** `libretranslate`

适配器默认将聊天消息中的文本翻译为中文。启动适配器前设置 `LIBRETRANSLATE_TARGET` 可更改目标语言，例如 `en` 或 `ja`。

## CopyTranslator 配置

打开 CopyTranslator 的 OpenAI 兼容 API 设置并填写：

| 配置项 | 值 |
|--------|----|
| API key | 任意值，除非已设置 `OPENAI_API_KEY` |
| Base URL | `http://127.0.0.1:8000/v1` |
| 模型 | `libretranslate`（可通过 `OPENAI_COMPAT_MODEL` 配置） |

CopyTranslator 只需要翻译能力，不依赖其他 OpenAI 功能。

## 配置项

环境变量在适配器进程启动时读取：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LIBRETRANSLATE_URL` | `http://127.0.0.1:5000` | LibreTranslate 基础 URL |
| `LIBRETRANSLATE_SOURCE` | `auto` | 发送给 LibreTranslate 的源语言 |
| `LIBRETRANSLATE_TARGET` | `zh` | 发送给 LibreTranslate 的目标语言 |
| `OPENAI_API_KEY` | 未设置 | 设置后，客户端必须发送 `Authorization: Bearer <value>` |
| `OPENAI_COMPAT_MODEL` | `libretranslate` | `/v1/models` 返回的模型 ID，同时作为默认响应模型 |
| `OPENAI_COMPAT_HOST` | `127.0.0.1` | 适配器绑定主机 |
| `OPENAI_COMPAT_PORT` | `8000` | 适配器绑定端口 |
| `OPENAI_COMPAT_LOGGING` | `full` | `off` 关闭请求日志；`full` 将日志写入控制台和 `openai_compat.log` |

适配器也接受 `--logging off` 或 `--logging full`，对该进程覆盖 `OPENAI_COMPAT_LOGGING`。

### 可选认证

PowerShell：

```powershell
$env:OPENAI_API_KEY = "change-this-secret"
```

POSIX shell：

```bash
export OPENAI_API_KEY="change-this-secret"
```

若设置了 `OPENAI_API_KEY`，`/v1/models` 和 `/v1/chat/completions` 都要求匹配的 bearer token。

## API 端点

### `GET /v1/models`

返回包含所配置模型的 OpenAI 模型列表。

### `POST /v1/chat/completions`

翻译最后一条用户消息中的文本，并以 assistant 消息返回。

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"libretranslate","messages":[{"role":"user","content":"Hello, world!"}]}'
```

响应遵循 OpenAI 聊天补全结构：

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

错误使用 OpenAI 错误结构：

```json
{"error": {"message": "Invalid API key.", "type": "authentication_error"}}
```

## 行为与限制

- 适配器用于 CopyTranslator 的 OpenAI 兼容翻译接入。
- 适配器只做文本翻译，不实现语言模型生成。
- 不支持工具调用、多模态内容和流式响应。
- `stream: true` 会以 `400` 错误拒绝。
- `system`、`user`、`assistant` 消息仅支持字符串形式的 `content`。
- 翻译最后一条 `user` 消息；若没有用户消息，则使用最后一条 `assistant` 消息。
- 识别到的翻译提示词模板会被视为仅提示词请求，并返回空的 assistant 消息。
- LibreTranslate 上游失败时返回 `502` 错误，类型为 `upstream_error`。
- 发往 LibreTranslate 的请求在 120 秒后超时。
- 使用默认 URL 时，适配器和 LibreTranslate 都运行在本机，译文不会离开本地机器。

## 故障排查

- **端口已被占用**：另一个进程正在监听 `8000`。停止该进程，或将 `OPENAI_COMPAT_PORT` 设为空闲端口。
- **`401 Invalid API key`**：已设置 `OPENAI_API_KEY`，但客户端发送的 bearer token 不匹配。
- **`502 LibreTranslate request failed`**：无法通过 `LIBRETRANSLATE_URL` 访问 LibreTranslate，或所请求的语言对不可用。
- **译文为空**：请求匹配了仅提示词的翻译模板。只发送需要翻译的文本。
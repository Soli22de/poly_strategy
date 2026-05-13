# Windhub / Elysiver Endpoint Format 实验报告（2026-05-13T03:01:05.723361+00:00）

## 1. 模型枚举

### secondary
- `claude-haiku-4-5-20251001` (unknown_or_mid) owned_by=vertex-ai
- `claude-opus-4-1-20250805` (unknown_or_mid) owned_by=vertex-ai
- `claude-opus-4-20250514` (unknown_or_mid) owned_by=vertex-ai
- `claude-opus-4-5-20251101` (unknown_or_mid) owned_by=vertex-ai
- `claude-opus-4-6` (unknown_or_mid) owned_by=vertex-ai
- `claude-opus-4-7` (unknown_or_mid) owned_by=vertex-ai
- `claude-sonnet-4-20250514` (likely_high) owned_by=vertex-ai
- `claude-sonnet-4-5-20250929` (likely_high) owned_by=vertex-ai
- `claude-sonnet-4-6` (likely_high) owned_by=vertex-ai
- `gemini-2.5-flash` (likely_low) owned_by=vertex-ai
- `gemini-2.5-flash-nothinking` (likely_low) owned_by=custom
- `gemini-2.5-pro` (likely_low) owned_by=vertex-ai
- `gemini-3-flash-preview` (likely_low) owned_by=vertex-ai
- `gemini-3-pro-preview` (likely_low) owned_by=vertex-ai
- `gemini-3.1-pro-preview` (likely_low) owned_by=vertex-ai
- `glm-5` (unknown_or_mid) owned_by=zhipu_4v
- `mimo-v2-omni` (likely_low) owned_by=custom
- `mimo-v2-pro` (likely_low) owned_by=custom
- `mimo-v2-tts` (likely_low) owned_by=custom
- `mimo-v2.5` (likely_low) owned_by=custom
- `mimo-v2.5-pro` (likely_low) owned_by=custom
- `mimo-v2.5-tts` (likely_low) owned_by=custom
- `mimo-v2.5-tts-voiceclone` (likely_low) owned_by=custom
- `mimo-v2.5-tts-voicedesign` (likely_low) owned_by=custom

## 2. 实测模型范围

- secondary: `gemini-2.5-flash`, `gemini-2.5-flash-nothinking`, `gemini-2.5-pro`, `gemini-3-flash-preview`, `gemini-3-pro-preview`, `gemini-3.1-pro-preview`, `mimo-v2-omni`, `mimo-v2-pro`, `mimo-v2-tts`, `mimo-v2.5`, `mimo-v2.5-pro`, `mimo-v2.5-tts`, `mimo-v2.5-tts-voiceclone`, `mimo-v2.5-tts-voicedesign`, `claude-haiku-4-5-20251001`, `claude-opus-4-1-20250805`, `claude-opus-4-20250514`, `claude-opus-4-5-20251101`, `claude-opus-4-6`, `claude-opus-4-7`, `glm-5`, `claude-sonnet-4-20250514`, `claude-sonnet-4-5-20250929`, `claude-sonnet-4-6`

## 3. 自动指标对比

| provider | model | format | calls | success | schema | grounding | nonempty | clauses/market | median latency | token in/out | cost class | first error |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| secondary | `claude-haiku-4-5-20251001` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 503: {"error":{"message":"No available channel for model claude-haiku-4-5-20251001 under group gemini (distributor) |
| secondary | `claude-haiku-4-5-20251001` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-haiku-4-5-20251001` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-haiku-4-5-20251001` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 503: {"error":{"message":"No available channel for model claude-haiku-4-5-20251001 under group gemini (distributor) |
| secondary | `claude-haiku-4-5-20251001` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-haiku-4-5-20251001` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-1-20250805` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-1-20250805` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 503: {"error":{"message":"No available channel for model claude-opus-4-1-20250805 under group gemini (distributor)  |
| secondary | `claude-opus-4-1-20250805` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 503: {"error":{"message":"No available channel for model claude-opus-4-1-20250805 under group gemini (distributor)  |
| secondary | `claude-opus-4-1-20250805` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-1-20250805` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-1-20250805` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-20250514` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-20250514` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-20250514` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-20250514` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-20250514` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-20250514` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-5-20251101` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-5-20251101` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 503: {"error":{"message":"No available channel for model claude-opus-4-5-20251101 under group gemini (distributor)  |
| secondary | `claude-opus-4-5-20251101` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-5-20251101` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-5-20251101` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-5-20251101` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-6` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-6` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-6` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-6` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-6` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-6` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-7` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 503: {"error":{"message":"No available channel for model claude-opus-4-7 under group gemini (distributor) (request  |
| secondary | `claude-opus-4-7` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 503: {"error":{"message":"No available channel for model claude-opus-4-7 under group gemini (distributor) (request  |
| secondary | `claude-opus-4-7` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 503: {"error":{"message":"No available channel for model claude-opus-4-7 under group gemini (distributor) (request  |
| secondary | `claude-opus-4-7` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `claude-opus-4-7` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 503: {"error":{"type":"model_not_found","message":"No available channel for model claude-opus-4-7 under group gemin |
| secondary | `claude-opus-4-7` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 500: {"error":{"message":"not implemented (request id: 202605130309208666767698268d9d68RKspt8o)","type":"new_api_er |
| secondary | `claude-sonnet-4-20250514` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 554:  |
| secondary | `claude-sonnet-4-20250514` | `chat_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 13.52s | 578/495 | likely_high |  |
| secondary | `claude-sonnet-4-20250514` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 554:  |
| secondary | `claude-sonnet-4-20250514` | `chat_stream_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 11.27s | 0/0 | likely_high |  |
| secondary | `claude-sonnet-4-20250514` | `messages` | 1 | 1 | 0 | 0 | 0 | 0.0 | 11.04s | 578/491 | likely_high |  |
| secondary | `claude-sonnet-4-20250514` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 500: {"error":{"message":"field messages is required (request id: 202605130311182308586518268d9d6sNvZcalo)","type": |
| secondary | `claude-sonnet-4-5-20250929` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 503: {"error":{"message":"No available channel for model claude-sonnet-4-5-20250929 under group gemini (distributor |
| secondary | `claude-sonnet-4-5-20250929` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 503: {"error":{"message":"No available channel for model claude-sonnet-4-5-20250929 under group gemini (distributor |
| secondary | `claude-sonnet-4-5-20250929` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 503: {"error":{"message":"No available channel for model claude-sonnet-4-5-20250929 under group gemini (distributor |
| secondary | `claude-sonnet-4-5-20250929` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 503: {"error":{"message":"No available channel for model claude-sonnet-4-5-20250929 under group gemini (distributor |
| secondary | `claude-sonnet-4-5-20250929` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 503: {"error":{"type":"model_not_found","message":"No available channel for model claude-sonnet-4-5-20250929 under  |
| secondary | `claude-sonnet-4-5-20250929` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 500: {"error":{"message":"not implemented (request id: 20260513031135635263028268d9d6h0gFECGi)","type":"new_api_err |
| secondary | `claude-sonnet-4-6` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 429:  |
| secondary | `claude-sonnet-4-6` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 429:  |
| secondary | `claude-sonnet-4-6` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 429:  |
| secondary | `claude-sonnet-4-6` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 429:  |
| secondary | `claude-sonnet-4-6` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 503: {"error":{"type":"model_not_found","message":"No available channel for model claude-sonnet-4-6 under group gem |
| secondary | `claude-sonnet-4-6` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 429:  |
| secondary | `gemini-2.5-flash` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 11.99s | 433/1262 | likely_low |  |
| secondary | `gemini-2.5-flash` | `chat_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 13.56s | 433/1796 | likely_low |  |
| secondary | `gemini-2.5-flash` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 554:  |
| secondary | `gemini-2.5-flash` | `chat_stream_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 10.18s | 0/0 | likely_low |  |
| secondary | `gemini-2.5-flash` | `messages` | 1 | 1 | 0 | 0 | 0 | 0.0 | 14.88s | 433/1796 | likely_low |  |
| secondary | `gemini-2.5-flash` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"not implemented (request id: 20260513030215455727098268d9d6qKRw3hb7)","type":"new_api_err |
| secondary | `gemini-2.5-flash-nothinking` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 4.30s | 433/209 | likely_low |  |
| secondary | `gemini-2.5-flash-nothinking` | `chat_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 4.42s | 433/225 | likely_low |  |
| secondary | `gemini-2.5-flash-nothinking` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 554:  |
| secondary | `gemini-2.5-flash-nothinking` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 3.85s | 0/0 | likely_low |  |
| secondary | `gemini-2.5-flash-nothinking` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 3.56s | 433/225 | likely_low |  |
| secondary | `gemini-2.5-flash-nothinking` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"not implemented (request id: 202605130302504086585558268d9d6wSbGbYvH)","type":"new_api_er |
| secondary | `gemini-2.5-pro` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 12.40s | 433/1400 | likely_low |  |
| secondary | `gemini-2.5-pro` | `chat_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 11.88s | 433/1472 | likely_low |  |
| secondary | `gemini-2.5-pro` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 1.0 | 8.18s | 0/0 | likely_low |  |
| secondary | `gemini-2.5-pro` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 554:  |
| secondary | `gemini-2.5-pro` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 13.14s | 433/1187 | likely_low |  |
| secondary | `gemini-2.5-pro` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"not implemented (request id: 202605130303551266466128268d9d6JWsv4Svg)","type":"new_api_er |
| secondary | `gemini-3-flash-preview` | `chat` | 1 | 1 | 1 | 1 | 1 | 1.0 | 14.24s | 433/1622 | likely_low |  |
| secondary | `gemini-3-flash-preview` | `chat_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 12.53s | 433/1472 | likely_low |  |
| secondary | `gemini-3-flash-preview` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 1.0 | 10.48s | 0/0 | likely_low |  |
| secondary | `gemini-3-flash-preview` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 9.16s | 0/0 | likely_low |  |
| secondary | `gemini-3-flash-preview` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 13.43s | 433/1472 | likely_low |  |
| secondary | `gemini-3-flash-preview` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"not implemented (request id: 202605130304577865104248268d9d6Ag2msET7)","type":"new_api_er |
| secondary | `gemini-3-pro-preview` | `chat` | 1 | 1 | 1 | 1 | 1 | 3.0 | 12.34s | 433/1110 | likely_low |  |
| secondary | `gemini-3-pro-preview` | `chat_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 14.42s | 433/1796 | likely_low |  |
| secondary | `gemini-3-pro-preview` | `chat_stream` | 1 | 1 | 0 | 0 | 0 | 0.0 | 11.50s | 0/0 | likely_low |  |
| secondary | `gemini-3-pro-preview` | `chat_stream_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 12.54s | 0/0 | likely_low |  |
| secondary | `gemini-3-pro-preview` | `messages` | 1 | 1 | 0 | 0 | 0 | 0.0 | 15.17s | 433/1796 | likely_low |  |
| secondary | `gemini-3-pro-preview` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"not implemented (request id: 202605130306062899149258268d9d6QQ6Rl7CC)","type":"new_api_er |
| secondary | `gemini-3.1-pro-preview` | `chat` | 1 | 1 | 1 | 1 | 1 | 3.0 | 6.63s | 432/284 | likely_low |  |
| secondary | `gemini-3.1-pro-preview` | `chat_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 5.12s | 432/214 | likely_low |  |
| secondary | `gemini-3.1-pro-preview` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 3.0 | 5.30s | 0/0 | likely_low |  |
| secondary | `gemini-3.1-pro-preview` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 5.34s | 0/0 | likely_low |  |
| secondary | `gemini-3.1-pro-preview` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 5.27s | 432/214 | likely_low |  |
| secondary | `gemini-3.1-pro-preview` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"not implemented (request id: 202605130306364168183918268d9d6lMRSKGHD)","type":"new_api_er |
| secondary | `glm-5` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `glm-5` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `glm-5` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 429:  |
| secondary | `glm-5` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 1.0 | 26.16s | 0/0 | unknown_or_mid |  |
| secondary | `glm-5` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 14.12s | 402/594 | unknown_or_mid |  |
| secondary | `glm-5` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 400: {"error":{"message":"The parameter messages is invalid.","type":"runtime_error","param":"","code":"20024"}} |
| secondary | `mimo-v2-omni` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 554:  |
| secondary | `mimo-v2-omni` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} |
| secondary | `mimo-v2-omni` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} |
| secondary | `mimo-v2-omni` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} |
| secondary | `mimo-v2-omni` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"type":"429","message":"quota exhausted (request id: 202605130307131370508658268d9d6qtFsYZKC)"},"typ |
| secondary | `mimo-v2-omni` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_co |
| secondary | `mimo-v2-pro` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2-pro` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2-pro` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} |
| secondary | `mimo-v2-pro` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2-pro` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"type":"429","message":"quota exhausted (request id: 202605130307245353224128268d9d6WcQzeWNc)"},"typ |
| secondary | `mimo-v2-pro` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2-tts` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2-tts` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} |
| secondary | `mimo-v2-tts` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2-tts` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2-tts` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2-tts` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_co |
| secondary | `mimo-v2.5` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} |
| secondary | `mimo-v2.5` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-pro` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-pro` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-pro` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-pro` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-pro` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-pro` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_co |
| secondary | `mimo-v2.5-tts` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-tts` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-tts` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-tts` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-tts` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-tts` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-tts-voiceclone` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-tts-voiceclone` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-tts-voiceclone` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-tts-voiceclone` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} |
| secondary | `mimo-v2.5-tts-voiceclone` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"type":"429","message":"quota exhausted (request id: 202605130308099953834488268d9d6NiqSDrBE)"},"typ |
| secondary | `mimo-v2.5-tts-voiceclone` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-tts-voicedesign` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} |
| secondary | `mimo-v2.5-tts-voicedesign` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} |
| secondary | `mimo-v2.5-tts-voicedesign` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} |
| secondary | `mimo-v2.5-tts-voicedesign` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-tts-voicedesign` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |
| secondary | `mimo-v2.5-tts-voicedesign` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 429:  |

## 4. 推荐

1. `secondary` / `gemini-2.5-flash-nothinking` / `messages`: median 3.56s, schema 1/1, grounding 1/1, cost_class=likely_low.
2. `secondary` / `gemini-2.5-flash-nothinking` / `chat_stream_plain`: median 3.85s, schema 1/1, grounding 1/1, cost_class=likely_low.
3. `secondary` / `gemini-2.5-flash-nothinking` / `chat`: median 4.30s, schema 1/1, grounding 1/1, cost_class=likely_low.
4. `secondary` / `gemini-2.5-flash-nothinking` / `chat_plain`: median 4.42s, schema 1/1, grounding 1/1, cost_class=likely_low.
5. `secondary` / `gemini-3.1-pro-preview` / `chat_plain`: median 5.12s, schema 1/1, grounding 1/1, cost_class=likely_low.

说明：`cost_class` 是按模型名的保守启发式分类，因为这两个 `/models` 返回没有暴露 pricing 字段；真实价格仍需以服务商后台为准。

## 5. 数据归档

- per-call NDJSON: `data/experiments/2026-05-13/llm-endpoint-format-secondary-all-smoke-v2.ndjson`
- rows: 144

---
*Snapshot: 2026-05-13T03:01:05.723361+00:00*
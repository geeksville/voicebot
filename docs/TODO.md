misc
* fix led brightness
* fix scrolling rate
* remove LEGACY_OVERRIDE_CHARS and related checks - all firmware can now do 512 chars

Great thread https://www.reddit.com/r/homeassistant/s/wl02ow67MK
https://www.reddit.com/r/RockchipNPU/comments/1g3cetq/fast_and_accurate_speechtotext_on_rk3588_with/?share_id=5YA3sA8R8K1hXxF8YJaFh 

What about if I use this device over USB instead of esp32s3?  Can I hook it to my rpi and still take advantage of the built in vad?
Possibly this version reSpeaker USB 4-Mic Array XVF3000 v3.0 | Seeed Studio Wiki https://share.google/SmlZbrjco82vemvfg
Best mic module https://wiki.seeedstudio.com/respeaker_xvf3800_introduction/ has esp32s3 
Orangepi info https://www.reddit.com/r/SBCs/s/LBz8vA3nx5

## ai tips

Over the last year (2025–2026), local speech-to-text (STT) and audio-capable language models have evolved significantly. With a generous **30-second latency budget** on Raspberry Pi 5-class hardware (ideally an **8GB or 16GB RAM** board running 4-bit or 8-bit quantization via `llama.cpp`, `sherpa-onnx`, or `onnxruntime`), you are no longer limited to tiny, robotic models—you can comfortably run high-accuracy transcription, Speech-Augmented Language Models (SALMs), or even end-to-end multimodal audio LLMs.

---

### 1. Pure Speech-to-Text (Fastest & Most Efficient)
If you want a dedicated acoustic/transcription model (either standalone or feeding text into a separate small LLM), these newer models outperform older Whisper variants on ARM CPUs:

* **Moonshine & Moonshine v2 (Useful Sensors)**
  * **Size:** `27M` (Tiny) to `245M–331M` (Base / Streaming Medium).
  * **Why it's great for Pi 5:** Purpose-built for edge hardware like the Raspberry Pi. Unlike Whisper—which pads every audio clip to 30 seconds of compute regardless of length—Moonshine scales compute dynamically with the actual length of your voice command. **Moonshine v2** adds an Ergodic Streaming Encoder for ultra-low-latency chunked recognition.
  * **Pi 5 Latency:** Under **0.5 to 2 seconds** for typical voice commands.
* **NVIDIA Parakeet TDT (`0.6B-v3` & `1.1B`)**
  * **Size:** `600M` (25 European languages) and `1.1B` (English).
  * **Why it's great for Pi 5:** Uses a FastConformer Token-and-Duration Transducer (TDT) architecture that skips blank frames during decoding. It achieves lower Word Error Rates (WER ~6.3%) than Whisper while running significantly faster. Easily deployed on a Pi 5 via **`sherpa-onnx`** (int8 quantized).
  * **Pi 5 Latency:** Roughly **1 to 3 seconds** for a 10-second clip.
* **FunAudioLLM SenseVoice-Small & Fun-ASR-Nano (`0.8B`)**
  * **Size:** `~230M` (SenseVoice-Small) / `800M` (Fun-ASR-Nano, late 2025).
  * **Why it's great for Pi 5:** Non-autoregressive architectures trained on tens of millions of hours of audio. `SenseVoice-Small` runs 5x–15x faster than Whisper-Small on CPU via `sherpa-onnx` and simultaneously outputs **emotion recognition** and **audio event tags** (laughter, coughing, applause) alongside text.
* **Whisper Large-v3-Turbo & Distil-Whisper v3.5**
  * **Size:** `756M` (Distil) / `809M` (Large-v3-Turbo).
  * **Why it's great for Pi 5:** Prunes the Whisper Large-v3 decoder from 32 layers down to 4 (or 2 in Distil), keeping Large-v3 accuracy while running ~6x faster. Quantized to `Q4_K_M` or `Q5_0` in `whisper.cpp`, an 800M model fits in ~600MB of RAM and transcribes a clip on a Pi 5 in **3 to 6 seconds**.

---

### 2. "LLM-Brained" ASR (Speech-Augmented Language Models)
A major structural shift in 2025–2026 was replacing traditional decoders with a small LLM decoder so the transcriber inherently understands context, proper nouns, and formatting, and can summarize or answer questions about the audio directly:

* **NVIDIA Canary-Qwen (`2.5B`)**
  * **Architecture:** FastConformer audio encoder paired directly with a **Qwen3-1.7B** LLM decoder.
  * **Capabilities:** Currently sits at the top of open-source English ASR benchmarks (~5.63% WER) and operates in two modes: **pure transcription mode** or **intelligent analysis/Q&A mode**.
  * **Pi 5 Feasibility:** At 4-bit quantization (~1.6 GB RAM), the 1.7B Qwen decoder generates around 10–15 tokens/sec on a Pi 5, easily completing both recognition and a short response within **8 to 15 seconds**.
* **Alibaba Qwen3-ASR (`1.7B`)**
  * **Architecture:** Released in early 2026, unifying language identification (52 languages), punctuation, and streaming/offline recognition onto a Qwen backbone.

---

### 3. End-to-End Native Audio + Reasoning LLMs
If your goal is to speak to the Pi and have a single model **understand the audio directly and generate a reasoned response** (without an intermediate text transcription step, preserving tone and paralinguistics):

* **Google Gemma 4 (`E2B` & `E4B`) / Gemma 3n (`E2B` & `E4B`)**
  * **Size:** Effective `2B` and `4B` parameter models designed specifically for edge devices.
  * **Why it's great for Pi 5:** Native multimodal input (text, image, and **audio**) with sliding-window attention layers to keep memory low. Quantized in `llama.cpp`, the `E2B` variant uses ~1.5GB–2GB RAM and processes an audio prompt + 100-token reply in **10 to 20 seconds** on a Pi 5.
* **Qwen2.5-Omni (`3B` / `7B`) & Qwen3.5 Small Variants**
  * **Size:** `3B` and `7B` end-to-end multimodal models (Thinker-Talker architecture).
  * **Why it's great for Pi 5:** Takes direct audio input and performs instruction following and reasoning on par with text models. On an 8GB Pi 5, the `3B` (or quantized `7B` at Q4_K_M) will take ~3–6 seconds to encode the audio prompt and ~10–20 seconds to generate a spoken/text answer—fitting right inside your 30-second window.
* **Ultravox (`v0.5` / `v0.6` — `1B` & `3B` variants)**
  * **Architecture:** Pairs a Whisper audio encoder via a lightweight projector directly into **Llama-3.2-1B** or **Llama-3.2-3B** (or Qwen/SmolLM backbones).
  * **Why it's great for Pi 5:** Supported natively in `llama.cpp` multimodal (`llama-mtmd-cli`), letting you feed a `.wav` file straight into the LLM context without running a transcription pass first.

---

### 4. The Pragmatic "Reasoning" Pipeline for Pi 5 (Recommended)
While end-to-end audio LLMs are exciting, the most flexible way to get **actual chain-of-thought ("thinking") reasoning** under 30 seconds on a Pi 5 is a two-stage pipeline:
1. **Stage 1 (1–2 seconds):** Run **Moonshine Base** or **Parakeet-TDT-0.6B** (via `sherpa-onnx`) to turn speech into text almost instantaneously and using minimal RAM (<400MB).
2. **Stage 2 (5–20 seconds):** Pipe that text into a modern 2025/2026 small reasoning LLM running on `llama.cpp` (with `Q4_K_M` quantization):
   * **Qwen3-1.7B or Qwen3-4B** (features built-in `<think>` reasoning toggle—you can cap thinking tokens or toggle them off for simple queries).
   * **DeepSeek-R1-Distill-Qwen-1.5B** (fast chain-of-thought reasoning at ~15–20 tokens/sec on Pi 5).
   * **Phi-4-Mini (3.8B)** or **Llama-3.2-3B** (strong instruction following and tool calling).

## hw options

For a witty local voicebot, the main bottleneck is **RAM capacity and memory bandwidth**—moving from a `1.5B–3B` model up to an `8B–14B` model (`Llama-3.1-8B`, `Qwen3-8B`, `Mistral-Nemo-12B`) drastically improves humor and wordplay.

Here are the best hardware alternatives to the Raspberry Pi 5 in the **$250–$400** range:

### 1. NVIDIA Jetson Orin Nano Super (8GB) — *Best Edge AI + GPIO*
* **Specs:** 6-core ARM CPU + 1024-core Ampere GPU (67 INT8 TOPS), **102 GB/s** memory bandwidth (~6x faster than Pi 5).
* **Pros:** Runs `8B` models at ~15–20 tokens/sec and `3B–4B` at 35+ tokens/sec via CUDA/TensorRT, with millisecond GPU-accelerated STT/TTS and 40-pin GPIO headers.
* **Cons:** 8GB shared LPDDR5 caps you at 4-bit `7B–8B` models.

### 2. Budget x86 Mini PCs (Intel N100/N95 or Ryzen) — *Best Value & High RAM*
* **Specs:** x86_64 CPU, **12GB–32GB RAM**, 500GB+ SSD, case, cooling, and PSU included ($200–$350).
* **Pros:** Standard x86 Ubuntu support (no ARM compilation headaches) and enough RAM to run smarter **12B–14B models** (`Mistral-Nemo-12B`, `Qwen3-14B`) comfortably within your 30s latency window.
* **Cons:** No onboard GPIO pins (requires a USB microcontroller for hardware/LEDs).

### 3. Rockchip RK3588 SBCs (Orange Pi 5 Max / Radxa Rock 5B) — *Best High-RAM ARM Board*
* **Specs:** 8-core ARM CPU + **6 TOPS NPU** + **16GB/32GB LPDDR5 RAM**.
* **Pros:** 2x the CPU cores of the Pi 5, GPIO pins, and an NPU that can offload STT (`sherpa-onnx`) or LLMs (`rkllm`) under 10W.
* **Cons:** Rockchip's NPU software stack requires more tinkering than standard `llama.cpp`.

### 4. Used Apple M1 Mac Mini (8GB/16GB) — *Fastest Silent Appliance (~$250–$320)*
* **Specs:** Apple M1 (8-core GPU + 16-core Neural Engine), **68 GB/s** unified memory bandwidth.
* **Pros:** Dead silent (~5W idle) and Metal acceleration (`mlx-lm` / `llama.cpp`) delivers complete STT + witty LLM replies in **2–4 seconds**.

---

### Quick Pick Guide
* **Need GPIO + fast (2–4s) `8B` replies?** → **Jetson Orin Nano Super**
* **Want the funniest `12B–14B` models out of the box?** → **x86 Mini PC (16GB+ RAM)** or **Used M1 Mac Mini**
* **Want the largest Linux community & lowest entry cost?** → **Raspberry Pi 5 (8GB/16GB)** (5–15s pause for `3B–7B` models)
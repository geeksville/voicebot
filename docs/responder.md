

```markdown
When you ask a standard small corporate-aligned model (like vanilla `Llama-3.2-3B-Instruct` or `Phi-4-mini`) to tell a joke, it will almost always give you the same 5 sterile dad jokes (*"Why don't scientists trust atoms?"*). 

To get **genuine wit, dry sarcasm, absurdism, or clever banter** from a small model (`2B` to `12B`), you want models that were either **trained on creative/conversational datasets** (like the Nous Hermes or Dolphin families, or Google's Gemma 3/4 series, which punch way above their weight in prose style) or **hybrid reasoning models** where the model can spend a few `<think>` tokens brainstorming an original premise before delivering the punchline.

The best small-to-medium models for wit and humor are listed below, grouped by hardware size, with exact **Hugging Face paths** (both raw weights and ready-to-run `GGUF` repos for `llama.cpp` / `Ollama`):

---

### Tier 1: Ultra-Light (`2B` – `4B`) — Fast on a Raspberry Pi 5 (8GB)
These take ~1.5GB to 3GB of RAM in 4-bit (`Q4_K_M`) and reply in **3 to 8 seconds** on a Pi 5.

1. **Hermes 3 (Llama-3.2 3B) — *Best Steerable Personality at 3B***
   * **Why it's witty:** Nous Research fine-tunes specifically for persona adoption, roleplay, and un-lobotomized creative banter without corporate stiffness. If you give it a system prompt like *"You are a dry, sardonic British butler,"* it actually commits to the bit.
   * **Base HF Path:** `NousResearch/Hermes-3-Llama-3.2-3B`
   * **GGUF HF Path:** `NousResearch/Hermes-3-Llama-3.2-3B-GGUF` (or `bartowski/Hermes-3-Llama-3.2-3B-GGUF`)

2. **Gemma 4 E2B / E4B & Gemma 3 4B — *Best Natural Prose & Riffing***
   * **Why it's witty:** Google's Gemma 3 (`4B`) and Gemma 4 (`E2B` / `E4B`) consistently top creative writing leaderboards in the sub-4B class. Plus, `gemma-4-E2B-it` is natively multimodal (can take raw audio input directly).
   * **Base HF Paths:** 
     * `google/gemma-4-E2B-it` (or `google/gemma-3-4b-it`)
   * **GGUF HF Paths:** 
     * `google/gemma-4-E2B-it-qat-q4_0-gguf`
     * `bartowski/google_gemma-3-4b-it-GGUF` (or `unsloth/gemma-3-4b-it-GGUF`)

3. **Qwen3 4B — *Best for "Thought-Out" Original Jokes***
   * **Why it's witty:** With Qwen3's toggleable `<think>` mode, you can instruct it to silently brainstorm 3 absurd metaphors and pick the funniest one before speaking.
   * **Base HF Path:** `Qwen/Qwen3-4B`
   * **GGUF HF Path:** `Qwen/Qwen3-4B-GGUF` (or `unsloth/Qwen3-4B-GGUF`)

---

### Tier 2: Sweet Spot (`8B` – `9B`) — Fits on Pi 5 (8GB/16GB), Orin Nano, or Mini PC
At `Q4_K_M` (~5GB–6GB RAM), an 8B/9B model takes **12–22 seconds** on a Pi 5 (well inside your 30s limit) or **2–4 seconds** on an Orin Nano / Mini PC, with a massive leap in comedic timing:

4. **DeepHermes 3 (Llama-3.1 8B) / Hermes 3 8B — *King of 8B Banter***
   * **Why it's witty:** Combines Nous Research's famous creative/roleplay tuning with optional R1-style reasoning toggles. It understands irony, deadpan humor, and situational callbacks far better than standard Llama-3.1-8B.
   * **Base HF Paths:**
     * `NousResearch/DeepHermes-3-Llama-3-8B-Preview` (with reasoning toggle)
     * `NousResearch/Hermes-3-Llama-3.1-8B` (pure fast chat)
   * **GGUF HF Paths:**
     * `bartowski/DeepHermes-3-Llama-3-8B-Preview-GGUF`
     * `NousResearch/Hermes-3-Llama-3.1-8B-GGUF`

5. **Gemma 2 9B / Gemma 3 12B (or SimPO Creative Tunes)**
   * **Why it's witty:** In blind human creative-writing evaluations, the 9B/12B Gemma architecture is famous for having the least "AI-sounding" voice—it naturally uses punchy phrasing and quirky observations.
   * **Base HF Paths:**
     * `google/gemma-2-9b-it`
     * `princeton-nlp/gemma-2-9b-it-SimPO` (preference-optimized for punchier, more human responses)
   * **GGUF HF Paths:**
     * `bartowski/gemma-2-9b-it-GGUF`
     * `bartowski/gemma-2-9b-it-SimPO-GGUF`

6. **Qwen3 8B**
   * **Why it's witty:** Very strong cultural and wordplay knowledge; great at observational roasts when prompted with a playful persona.
   * **Base HF Path:** `Qwen/Qwen3-8B`
   * **GGUF HF Path:** `Qwen/Qwen3-8B-GGUF`

---

### Tier 3: Heavyweights (`12B`) — For 16GB Pi 5, RK3588, or x86 Mini PC
At ~7.5GB in `Q4_K_M`, these comfortably fit on a 12GB–16GB device and complete a response in ~15–25s on CPU:

7. **Mistral-Nemo-Instruct-2407 (12B) & "Human-Like" / Roleplay Finetunes**
   * **Why it's witty:** Co-developed by Mistral and NVIDIA, `Mistral-Nemo-12B` has been the darling of the local roleplay and creative writing community because it isn't overly preachy and handles dry wit, absurdist humor, and eccentric character voices effortlessly.
   * **Base HF Paths:**
     * `mistralai/Mistral-Nemo-Instruct-2407`
     * `ReadyArt/Forgotten-Safeword-12B` or community creative tunes like `TheDrummer/Rocinante-12B-v1.1`
   * **GGUF HF Paths:**
     * `bartowski/Mistral-Nemo-Instruct-2407-GGUF`
     * `bartowski/Human-Like-Mistral-Nemo-Instruct-2407-GGUF` (specifically tuned to strip out robotic AI phrasing and sound like a witty human texting)

---

### Pro-Tip for Actually Getting Funny Replies from Small Models
Never just prompt a small model with *"Tell me a joke"*—that triggers its memorized training-set dad jokes. Instead, bake a **comedic mechanism** into your system prompt:
> *"You are a witty, slightly dramatic toaster-sized robot living on a desk. Never tell standard knock-knock or pun jokes. Instead, reply to whatever the user says with dry observational humor, absurd over-confident theories, or playful sarcasm in 1 to 2 short sentences."*

Also, set `temperature=0.85` and `min_p=0.05` (instead of default greedy decoding) in `llama.cpp` so the model takes creative leaps in word choice.

```
## llama setup

use 

sudo apt-get install zstd
curl -fsSL https://ollama.com/install.sh | sh
ollama run qwen3:4b

or

git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release

or

cmake -B build
cmake --build build --config Release

# Download and run a model directly from Hugging Face
llama cli -hf ggml-org/Qwen3.5-0.8B-GGUF

# Launch OpenAI-compatible API server
llama serve -hf ggml-org/Qwen3.5-0.8B-GGUF


dc_touchy-pad% build/bin/llama cli -hf ggml-org/Qwen3.5-0.8B-GGUF
Downloading Qwen3.5-0.8B-Q8_0.gguf ───────────────────────────────── 100%


Loading model...  

▄▄ ▄▄
██ ██
██ ██  ▀▀█▄ ███▄███▄  ▀▀█▄    ▄████ ████▄ ████▄
██ ██ ▄█▀██ ██ ██ ██ ▄█▀██    ██    ██ ██ ██ ██
██ ██ ▀█▄██ ██ ██ ██ ▀█▄██ ██ ▀████ ████▀ ████▀
                                    ██    ██
                                    ▀▀    ▀▀

build      : b12096-7071ba378
model      : ggml-org/Qwen3.5-0.8B-GGUF
ftype      : Q8_0
modalities : text

available commands:
  /exit or Ctrl+C     stop or exit
  /regen              regenerate the last response
  /clear              clear the chat history
  /read <file>        add a text file
  /glob <pattern>     add text files using globbing pattern



> hi

[Start thinking]

Thinking Process:

1.  **Analyze the Request:**
    *   Input: "hi"
    *   Intent: Greeting. The user is initiating a conversation by saying "hi".
    *   Context: This is a very simple, direct, and friendly greeting.
    *   Goal: Acknowledge the greeting, maintain a friendly and helpful persona, and invite further conversation.
...

dc_touchy-pad% build/bin/llama cli -hf NousResearch/Hermes-3-Llama-3.1-8B-GGUF  
Downloading Hermes-3-Llama-3.1-8B.Q4_K_M.gguf ────────────────────── 100%


Loading model...  

▄▄ ▄▄
██ ██
██ ██  ▀▀█▄ ███▄███▄  ▀▀█▄    ▄████ ████▄ ████▄
██ ██ ▄█▀██ ██ ██ ██ ▄█▀██    ██    ██ ██ ██ ██
██ ██ ▀█▄██ ██ ██ ██ ▀█▄██ ██ ▀████ ████▀ ████▀
                                    ██    ██
                                    ▀▀    ▀▀

build      : b12096-7071ba378
model      : NousResearch/Hermes-3-Llama-3.1-8B-GGUF
ftype      : Q4_K - Medium
modalities : text

available commands:
  /exit or Ctrl+C     stop or exit
  /regen              regenerate the last response
  /clear              clear the chat history
  /read <file>        add a text file
  /glob <pattern>     add text files using globbing pattern



> are you there?
Yes, I am here and ready to assist you with any questions or tasks you may have. How can I help you today?

[ Prompt: 115.6 t/s | Generation: 22.5 t/s ]
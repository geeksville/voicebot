https://medium.com/@conradot/local-ai-server-on-a-laptop-ollama-qdrant-and-open-webui-on-opensuse-microos-7bc82712b3bc

## ideas from ai

1. Raspberry Pi OS Lite (The Best Overall Choice)
For Ollama and llama.cpp on ARM hardware, standard Debian (which Raspberry Pi OS is built on) has the absolute best compatibility. Pre-compiled binaries work flawlessly and are natively optimized for the Pi's CPU architecture.

How to make it work: You will use the built-in OverlayFS (via raspi-config), but you must use a specific workflow.

The Workflow: Turn off the read-only overlay, connect to Tailscale, install Ollama/llama.cpp, download your models (e.g., ollama pull qwen2.5:3b), and test your code. Once everything works perfectly, turn the read-only overlay back on. The models are safely frozen on the SD card, and any temporary logs Ollama generates while inferencing will be safely thrown away in the RAM overlay.

2. openSUSE MicroOS (The Best Architectural Fit)
MicroOS actually handles the "Model Storage Problem" natively without you having to manually toggle read-only modes on and off.

How it works: MicroOS makes the core operating system strictly read-only, but it automatically mounts user directories (/home and /var) as writable, persistent partitions.

Ollama Support: MicroOS is built heavily around Podman (Docker's rootless alternative). You can easily run Ollama as a Podman container. When Ollama pulls a 4GB model, it gets written to the persistent /var or /home partition (surviving reboots), while the core OS remains untouchable and immune to corruption.

##

If we drop the read-only filesystem constraints, running Ollama on a Raspberry Pi 5 becomes incredibly straightforward because standard Raspberry Pi OS (64-bit) has excellent native support for Ollama's pre-compiled ARM binaries.

Here is the typical best way to set up and run Ollama on a Pi 5, incorporating the ideal hardware, model choices, and API usage:

### 1. The Ideal Hardware Setup

To get usable response times (under 30 seconds) out of a Pi 5, you should ensure you have the following:

* **8GB RAM Board:** This is necessary to hold a 4-bit quantized LLM in memory.


* **Active Cooling & 27W Power Supply:** These are essential for preventing the CPU from thermal throttling during 15–30 second LLM inference bursts.


* **M.2 NVMe SSD HAT (Highly Recommended):** While optional, using an NVMe SSD over the PCIe 2.0 interface allows you to stream large GGUF model weight files into memory much faster than a standard microSD card.



### 2. Standard Installation

Since you don't have to worry about RAM disks or read-only modes, you simply install the standard 64-bit Raspberry Pi OS and run Ollama's official install script:

```bash
curl -fsSL https://ollama.com/install.sh | sh

```

Ollama will run natively as a systemd service, automatically managing the Pi's CPU threads.

### 3. Choosing the Right Models for Pi 5

For a Pi 5, you want "Ultra-Light" Tier 1 models (2B to 4B parameters). In 4-bit quantization (`Q4_K_M`), these models take roughly 1.5GB to 3GB of RAM and can generate a reply in **3 to 8 seconds** on a Pi 5.

The best small models for witty or conversational use include:

* **Hermes 3 (Llama-3.2 3B):** Best for steerable personalities and roleplay.


* **Gemma 4 E2B / E4B & Gemma 3 4B:** Known for natural prose and riffing, consistently topping sub-4B creative writing leaderboards.


* **Qwen3 4B:** Great for "thought-out" original jokes using its reasoning toggle.



### 4. Integration with your Python Script

You can easily connect to Ollama directly on the Pi using the Python script you referenced. In the file named "voicebot", you can use the standard OpenAI client pointing to Ollama's local server:

```python
import requests
from openai import OpenAI

ollama_url = "http://localhost:11434"
model_name = "hf.co/bartowski/Hermes-3-Llama-3.2-3B-GGUF" 

# 1. Ask Ollama to pull the model if it hasn't already
print(f"Ensuring {model_name} is downloaded...")
requests.post(f"{ollama_url}/api/pull", json={"name": model_name})

# 2. Connect to the local API
client = OpenAI(
    base_url=f"{ollama_url}/v1",
    api_key="ollama" 
)

# 3. Request a generation (using a high temperature for creativity)
response = client.chat.completions.create(
    model=model_name,
    temperature=0.85, 
    messages=[
        {
            "role": "system", 
            "content": "You are a witty, slightly dramatic toaster-sized robot living on a desk. Never tell standard knock-knock or pun jokes. Instead, reply to whatever the user says with dry observational humor, absurd over-confident theories, or playful sarcasm in 1 to 2 short sentences."
        },
        {
            "role": "user", 
            "content": "I'm thinking about making a sandwich."
        }
    ]
)

print(response.choices[0].message.content)

```

By running Ollama locally like this, it will automatically drop the model from memory after 5 minutes of inactivity (the default setting), keeping your Pi 5's RAM free for other tasks when not actively responding to voice queries.
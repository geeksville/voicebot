#!/usr/bin/env bash
# launch-funny.sh — run llama.cpp's CLI as the voicebot's "responder", with a
# comedic mechanism baked into the system prompt instead of "tell me a joke".
#
# Why this script exists: per docs/responder.md, a small model asked to "tell me
# a joke" dredges up its memorised training-set dad jokes. Two settings are what
# actually produce wit — (a) a persona/mechanism in the system prompt and (b)
# loosened sampling so word choice takes creative leaps. Both are easy to forget
# when typing the command by hand, so they live here in one place.
#
# Usage:
#   tools/voicebot/launch-funny.sh [extra llama.cpp args...]
#
# Examples:
#   ./launch-funny.sh                                 # default model + persona, interactive chat
#   ./launch-funny.sh --print-command                 # show the resolved command, don't launch
#   ./launch-funny.sh -hf ggml-org/Qwen3.5-0.8B-GGUF   # lighter model, same persona/sampler
#   ./launch-funny.sh -st -p "how do I look today?"   # single shot then exit (good for piping/TTS)
#   ./launch-funny.sh --no-display-prompt             # quieter REPL transcript
#   ./launch-funny.sh --reasoning-budget 0            # skip  thinking on hybrid-reasoning models
#
# Environment overrides:
#   TOUCHY_BOT_MODEL    HF repo to load             (default: NousResearch/Hermes-3-Llama-3.1-8B-GGUF)
#   TOUCHY_BOT_PERSONA  system prompt text          (default: the toaster-sized robot below)
#   TOUCHY_BOT_TEMP     temperature                 (default: 0.85)
#   TOUCHY_BOT_MIN_P    min-p sampling              (default: 0.05)
#   TOUCHY_BOT_CTX      context size in tokens      (default: 4096)
#   TOUCHY_BOT_NGL      GPU layers to offload       (default: 0 = CPU; raise for CUDA/Metal builds)
#   LLAMA_BIN           path to the `llama` binary  (default: <this dir>/llama.cpp/build/bin/llama)
#
# Any argument not listed above is passed straight through to `llama cli`
# (e.g. -ngl, -t, --no-mmproj, --jinja, -co). If you supply your own model
# selector (-hf/-m/...) or persona (-sys/-sysf) or sampler/ctx/ngl flags, the
# defaults here step aside for that flag so nothing is specified twice.
#
# Model notes: NousResearch/Hermes-3-Llama-3.1-8B-GGUF is "king of 8B banter" in
# docs/responder.md. Faster or more steerable options via TOUCHY_BOT_MODEL:
#   NousResearch/Hermes-3-Llama-3.2-3B-GGUF    (2B-4B tier, quick on a Pi 5)
#   Qwen/Qwen3-4B-GGUF                         (thinks, then quips)
#   ggml-org/Qwen3.5-0.8B-GGUF                 (tiny, fast to download)
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

model=${TOUCHY_BOT_MODEL:-NousResearch/Hermes-3-Llama-3.1-8B-GGUF}
temp=${TOUCHY_BOT_TEMP:-0.85}
min_p=${TOUCHY_BOT_MIN_P:-0.05}
ctx=${TOUCHY_BOT_CTX:-4096}
ngl=${TOUCHY_BOT_NGL:-0}
llama_bin=${LLAMA_BIN:-$here/llama.cpp/build/bin/llama}

# The comedic mechanism from docs/responder.md, plus voice-output constraints so
# replies are speakable as-is (no markdown, no lists, no "Sure, here's...").
default_persona="""You are named 'Touchy' - a witty, slightly dramatic toaster-sized playfully eavesdropping robot. 

The input you receive is snippets from a conversation.  

very important: if you don't think you have something funny enough to say, just say NOTFUNNY (we will use that token to skip your reply).
It is better to say NOTFUNNY than to force a weak joke.
If you do think of something funny to say, go ahead and reply with it.

Never tell standard knock-knock or pun jokes. Instead, reply to whatever the user says 
with dry observational humor, absurd over-confident theories, or playful sarcasm 
in 1 to 2 short sentences. 

Your words will appear on a scrolling LED display - don't use emoji.  

Never open with 'Sure' or 'Certainly'."""
persona=${TOUCHY_BOT_PERSONA:-$default_persona}

usage() {
    sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
}

print_only=0
passthrough=()
while [ "$#" -gt 0 ]; do
    case $1 in
        -N|--print-command) print_only=1; shift ;;
        -h|--help|--usage)
            usage
            echo "For llama.cpp's own flag list: $llama_bin cli --help" >&2
            exit 0
            ;;
        --)
            # Everything after `--` goes to llama cli verbatim.
            shift
            passthrough+=("$@")
            break
            ;;
        *)
            passthrough+=("$1")
            shift
            ;;
    esac
done

# Respect any flag the caller already provided, so we never pass it twice.
want_model=1 want_persona=1 want_temp=1 want_min_p=1 want_ctx=1 want_ngl=1
for arg in ${passthrough[@]+"${passthrough[@]}"}; do
    case $arg in
        -hf|-hfr|--hf-repo|-hff|--hf-file|-m|--model|-mu|--model-url) want_model=0 ;;
        -sys|--system-prompt|-sysf|--system-prompt-file)             want_persona=0 ;;
        --temp|--temperature)                                       want_temp=0 ;;
        --min-p)                                                    want_min_p=0 ;;
        -c|--ctx-size)                                              want_ctx=0 ;;
        -ngl|--gpu-layers|--n-gpu-layers)                           want_ngl=0 ;;
    esac
done

cmd=("$llama_bin" cli)
if (( want_model ));   then cmd+=(-hf "$model");     fi
if (( want_persona )); then cmd+=(-sys "$persona");  fi
if (( want_temp ));    then cmd+=(--temp "$temp");   fi
if (( want_min_p ));   then cmd+=(--min-p "$min_p"); fi
if (( want_ctx ));     then cmd+=(-c "$ctx");        fi
if (( want_ngl ));     then cmd+=(-ngl "$ngl");      fi
cmd+=(${passthrough[@]+"${passthrough[@]}"})

if (( print_only )); then
    printf '%q ' "${cmd[@]}"
    printf '\n'
    exit 0
fi

if [ ! -x "$llama_bin" ]; then
    {
        echo "error: llama.cpp launcher not found at $llama_bin" >&2
        echo "build it first, then re-run this script:" >&2
        echo "  cd $here/llama.cpp" >&2
        echo "  cmake -B build            # add -DGGML_CUDA=ON for NVIDIA GPUs" >&2
        echo "  cmake --build build --config Release" >&2
        echo "or point LLAMA_BIN at an existing build." >&2
    } >&2
    exit 1
fi

{
    echo "launch-funny: model   = $model"
    echo "launch-funny: sampler = temp=$temp min-p=$min_p ctx=$ctx ngl=$ngl"
    echo "launch-funny: persona = ${persona:0:96}..."
    echo "launch-funny: starting llama.cpp CLI — /exit or Ctrl+C to quit"
} >&2

# exec so signals (Ctrl+C) and the TTY belong to llama, not to this wrapper.
exec "${cmd[@]}"

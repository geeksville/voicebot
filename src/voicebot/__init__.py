"""voicebot — witty one-liners about overheard conversation, via a remote LLM.

This is the "responder" half of the parent repo's creep3r art project: it takes
a snippet of overheard conversation and asks a small LLM (served remotely by
Ollama) for a witty reply, or the sentinel ``NOTFUNNY`` when it has nothing
worth saying. See ``docs/plans/initial.md``.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]

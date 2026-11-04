
## microphone input

xvf3800 — Seeed Studio **reSpeaker XVF3800 USB 4-Mic Array**.

* Four PDM MEMS mics in a circle + an XMOS **XVF3800** DSP, so the *capture*
  stream is already processed: AEC, multi-beamforming, de-reverberation, dynamic
  noise suppression, 60 dB AGC, 360° capture to ~5 m.
* **Only the audio stream is used by voicebot.** The array also does VAD and DoA,
  but those ride a separate vendor/I²C *control* interface (the reSpeaker console
  app, the LED ring, the mute button) — they are **not** a field in the USB
  audio. So `voicebot listen` runs **host-side VAD** (Moonshine's), which keeps
  the code identical on any UAC mic.
* USB-Audio-Class device. Seen by PortAudio (inside the devcontainer) as
  `reSpeaker XVF3800 4-Mic Array: USB Audio (hw:2,0)`, **2 input channels,
  16 kHz** — `voicebot` selects it by the `respeaker` name hint and captures
  mono (16 kHz is what the STT models want; the library resamples if a unit
  differs).
* Dev-container wiring (bind `/dev/snd`, `PULSE_SERVER`→host PipeWire, ALSA +
  PortAudio libs) is in the parent repo's `.devcontainer/`; see its memory bank,
  *Dev container: host devices & audio*.

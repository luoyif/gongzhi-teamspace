# Models, Skills, MCP, ASR

After login, configure model vendor address, model ID and private key in the workspace settings. Keep external API credentials on the backend only.

Agent employee configuration includes system prompts, role, model, skill bundle, MCP connections, internal plugins, context policy and run limits. @Agent is explicit; human-to-human chat remains normal chat. Skill packages may contain code and should be reviewed before being enabled.

Optional speech input uses FunAudioLLM/SenseVoiceSmall through SiliconFlow. The browser records microphone audio, converts it into 16kHz mono WAV and sends via authenticated same-origin POST to the backend. Recognition returns text into the input field and DOES NOT press Send, run agents, or save audio to knowledge. It may incur vendor charges.

Private setup on the WSL/Linux host:

    mkdir -p data/credentials
    chmod 700 data/credentials
    # create data/credentials/siliconflow-asr.key with your actual key
    chmod 600 data/credentials/siliconflow-asr.key

No real API key is shipped, including in examples. Voice capture requires HTTPS/localhost and browser microphone permission. Default limits: 120 seconds, 8 MiB and per-user rate limiting.

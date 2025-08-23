Ollama로 구축된 모델에 Prompt를 입력하면 TTS를 생성하고 3D 캐릭터가 LipSync로 대답해주는 간단한 데모이다.
1. 모든 시스템은 로컬에 구축해서 동작
2. 클라이언트는 유니티 6.2 버전 사용
3. 로컬 LLM 구축은 Ollama를 사용 (모델은 Bllossom을 사용 https://huggingface.co/MLP-KTLim/llama-3-Korean-Bllossom-8B-gguf-Q4_K_M)
4. TTS 기능은 MeloTTS를 사용 (https://github.com/myshell-ai/MeloTTS)
5. 유니티와 LLM, TTS 기능과의 통신은 FastAPI 사용
6. 유니티의 LipSync 기능은 uLipSync 사용 (https://github.com/hecomi/uLipSync)

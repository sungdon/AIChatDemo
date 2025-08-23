Ollama로 구축된 모델에 Prompt를 입력하면 3D 캐릭터가 TTS를 통해서 LipSync로 대답해주는 간단한 데모이다.
1. 모든 시스템 동작은 로컬에 구성된 시스템을 이용
2. 클라이언트는 유니티 6.2 버전 사용
3. Prompt를 입력 받고 답변 Text를 생성하는 AI 기능은 Ollama를 사용 (모델은 Bllossom을 사용 https://huggingface.co/MLP-KTLim/llama-3-Korean-Bllossom-8B-gguf-Q4_K_M)
4. TTS 기능은 MeloTTS를 사용 (https://github.com/myshell-ai/MeloTTS)
5. 유니티와 AI, TTS 기능과의 통신은 FastAPI 사용
6. 유니티의 LipSync 기능은 uLipSync 사용 (https://github.com/hecomi/uLipSync)

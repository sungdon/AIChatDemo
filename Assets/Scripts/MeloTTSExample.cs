using System;
using System.Collections;
using System.Text;
using TMPro;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

[Serializable]
public class FastAPITTSRequest
{
    public string text;
    public float speed = 1.0f;
}

[Serializable]
public class FastAPIChatTTSRequest
{
    public string prompt;
    public string model = "llama-3-Korean-Bllossom";
    public float speed = 1.0f;
}

[Serializable]
public class FastAPITTSResponse
{
    public string text_response;
    public string audio_url;
    public bool success;
    public string error;
}

[Serializable]
public class FastAPIHealthResponse
{
    public string status;
    public string service;
    public bool model_loaded;
}

public class MeloTTSExample : MonoBehaviour
{
    [Header("FastAPI 서버 설정")]
    public string fastApiServerUrl = "http://localhost:5000";
    
    [Header("오디오 설정")]
    public AudioSource audioSource;
    public bool autoPlayAudio = true;
    
    [Header("오류 처리")]
    public int maxRetries = 3;
    public float retryDelay = 1.0f;

    [Header("UI Component")]
    [SerializeField] private TMP_InputField inputField;
    [SerializeField] private Button submitButton;

    [Header("테스트")]
    [TextArea(3, 5)]
    public string testText = "안녕하세요! 개선된 FastAPI TTS 서버 테스트입니다.";
    
    public event System.Action<string> OnTTSCompleted;
    public event System.Action<string> OnTTSError;

    private void Awake()
    {
        submitButton.onClick.AddListener(() =>
        {
            StartCoroutine(ChatTTSCoroutine(inputField.text, "llama-3-Korean-Bllossom", 1.0f));
        });
    }

    private void Start()
    {
        InitializeAudioSource();
        StartCoroutine(CheckServerHealth());
    }

    private void InitializeAudioSource()
    {
        if (audioSource == null)
        {
            audioSource = GetComponent<AudioSource>();
            if (audioSource == null)
            {
                audioSource = gameObject.AddComponent<AudioSource>();
            }
        }
    }

    private IEnumerator CheckServerHealth()
    {
        using (UnityWebRequest request = UnityWebRequest.Get($"{fastApiServerUrl}/health"))
        {
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                try
                {
                    FastAPIHealthResponse health = JsonUtility.FromJson<FastAPIHealthResponse>(request.downloadHandler.text);
                    Debug.Log($"서버 상태: {health.status}, 모델 로드됨: {health.model_loaded}");
                    
                    if (!health.model_loaded)
                    {
                        Debug.LogWarning("TTS 모델이 로드되지 않았습니다!");
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"서버 상태 확인 실패: {e.Message}");
                }
            }
            else
            {
                Debug.LogError($"서버 연결 실패: {request.error}");
            }
        }
    }

    public void GenerateAndPlayTTS(string text, float speed = 1.0f)
    {
        StartCoroutine(GenerateTTSWithRetry(text, speed));
    }

    private IEnumerator GenerateTTSWithRetry(string text, float speed)
    {
        for (int attempt = 0; attempt < maxRetries; attempt++)
        {
            yield return StartCoroutine(GenerateTTSCoroutine(text, speed));
            
            if (audioSource.clip != null) // 성공
                break;
                
            if (attempt < maxRetries - 1)
            {
                Debug.LogWarning($"TTS 생성 재시도 {attempt + 1}/{maxRetries}");
                yield return new WaitForSeconds(retryDelay);
            }
        }
    }

    private IEnumerator GenerateTTSCoroutine(string text, float speed)
    {
        FastAPITTSRequest requestData = new FastAPITTSRequest
        {
            text = text,
            speed = speed
        };
        
        string jsonData = JsonUtility.ToJson(requestData);
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonData);
        
        using (UnityWebRequest request = new UnityWebRequest($"{fastApiServerUrl}/tts", "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.timeout = 30; // 30초 타임아웃
            
            yield return request.SendWebRequest();
            if (request.result == UnityWebRequest.Result.Success)
            {
                try
                {
                    FastAPITTSResponse response = JsonUtility.FromJson<FastAPITTSResponse>(request.downloadHandler.text);
                    
                    if (response.success && !string.IsNullOrEmpty(response.audio_url))
                    {
                        StartCoroutine(DownloadAndPlayAudio(response.audio_url));
                        OnTTSCompleted?.Invoke("TTS 생성 완료");
                    }
                    else
                    {
                        string errorMsg = $"TTS 생성 실패: {response.error}";
                        Debug.LogError(errorMsg);
                        OnTTSError?.Invoke(errorMsg);
                    }
                }
                catch (Exception e)
                {
                    string errorMsg = $"응답 파싱 오류: {e.Message}";
                    Debug.LogError(errorMsg);
                    OnTTSError?.Invoke(errorMsg);
                }
            }
            else
            {
                string errorMsg = $"HTTP 요청 실패: {request.error}";
                Debug.LogError(errorMsg);
                OnTTSError?.Invoke(errorMsg);
            }
        }
    }

    private IEnumerator ChatTTSCoroutine(string prompt, string model, float speed)
    {
        FastAPIChatTTSRequest requestData = new FastAPIChatTTSRequest
        {
            prompt = prompt,
            model = model,
            speed = speed
        };
        
        string jsonData = JsonUtility.ToJson(requestData);
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonData);
        
        using (UnityWebRequest request = new UnityWebRequest($"{fastApiServerUrl}/chat_tts", "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.timeout = 60; // 채팅은 더 긴 타임아웃
            
            yield return request.SendWebRequest();
            if (request.result == UnityWebRequest.Result.Success)
            {
                try
                {
                    FastAPITTSResponse response = JsonUtility.FromJson<FastAPITTSResponse>(request.downloadHandler.text);
                    
                    if (response.success)
                    {
                        Debug.Log($"Ollama 응답: {response.text_response}");
                        
                        if (!string.IsNullOrEmpty(response.audio_url))
                        {
                            StartCoroutine(DownloadAndPlayAudio(response.audio_url));
                            OnTTSCompleted?.Invoke(response.text_response);
                        }
                    }
                    else
                    {
                        string errorMsg = $"채팅 TTS 실패: {response.error}";
                        Debug.LogError(errorMsg);
                        OnTTSError?.Invoke(errorMsg);
                    }
                }
                catch (Exception e)
                {
                    string errorMsg = $"응답 파싱 오류: {e.Message}";
                    Debug.LogError(errorMsg);
                    OnTTSError?.Invoke(errorMsg);
                }
            }
            else
            {
                string errorMsg = $"HTTP 요청 실패: {request.error}";
                Debug.LogError(errorMsg);
                OnTTSError?.Invoke(errorMsg);
            }
        }
    }

    private IEnumerator DownloadAndPlayAudio(string audioUrl)
    {
        string fullUrl = $"{fastApiServerUrl}{audioUrl}";
        
        using (UnityWebRequest audioRequest = UnityWebRequestMultimedia.GetAudioClip(fullUrl, AudioType.WAV))
        {
            // 스트리밍 활성화
            ((DownloadHandlerAudioClip)audioRequest.downloadHandler).streamAudio = true;
            audioRequest.timeout = 15; // 오디오 다운로드 타임아웃
            
            yield return audioRequest.SendWebRequest();
            if (audioRequest.result == UnityWebRequest.Result.Success)
            {
                AudioClip audioClip = DownloadHandlerAudioClip.GetContent(audioRequest);
                
                if (audioClip != null)
                {
                    audioSource.clip = audioClip;
                    
                    if (autoPlayAudio)
                    {
                        audioSource.Play();
                        Debug.Log("TTS 음성 재생 시작");
                    }
                }
                else
                {
                    string errorMsg = "오디오 클립 생성 실패";
                    Debug.LogError(errorMsg);
                    OnTTSError?.Invoke(errorMsg);
                }
            }
            else
            {
                string errorMsg = $"오디오 다운로드 실패: {audioRequest.error}";
                Debug.LogError(errorMsg);
                OnTTSError?.Invoke(errorMsg);
            }
        }
    }

    [ContextMenu("Test TTS")]
    public void TestTTS()
    {
        GenerateAndPlayTTS(testText);
    }
}

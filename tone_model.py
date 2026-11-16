import os
import subprocess
import threading
import numpy as np

REPO = "ghkdqhals1/emotion-ser-w2v2"
LABELS = ["angry", "anxious", "happy", "neutral", "sad"]
KOR = {"angry": "분노", "anxious": "불안", "happy": "행복", "neutral": "중립", "sad": "슬픔"}
SR = 16000
CHUNK = SR * 6      # 학습 때처럼 6초 단위로 자름
MAX_CHUNKS = 10     # 너무 긴 녹음은 앞 60초까지만

_model = None
_extractor = None
_lock = threading.Lock()


def _load():
    # 처음 필요할 때 한 번만 모델을 불러옴
    global _model, _extractor
    with _lock:
        if _model is None:
            import torch
            from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2FeatureExtractor
            token = os.getenv("HF_TOKEN")
            _extractor = Wav2Vec2FeatureExtractor.from_pretrained(REPO, token=token)
            m = Wav2Vec2ForSequenceClassification.from_pretrained(
                REPO, token=token, torch_dtype=torch.float32
            )
            m.eval()
            _model = m
    return _model, _extractor


def _decode(path):
    # 어떤 형식이든 16kHz 모노 숫자 배열로 변환
    import imageio_ffmpeg
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    out = subprocess.run(
        [exe, "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
        capture_output=True, check=True, timeout=60,
    ).stdout
    return np.frombuffer(out, dtype=np.float32)


def analyze_tone(path):
    # 실패하면 None을 돌려줌 (그래도 일기 저장은 계속되게)
    try:
        import torch
        audio = _decode(path)
        if len(audio) < SR // 2:
            return None
        model, fe = _load()
        chunks = [audio[i:i + CHUNK] for i in range(0, len(audio), CHUNK)]
        if len(chunks) > 1 and len(chunks[-1]) < SR:
            chunks = chunks[:-1]
        chunks = chunks[:MAX_CHUNKS]
        probs = []
        with torch.no_grad():
            for c in chunks:
                inp = fe(c, sampling_rate=SR, return_tensors="pt")
                logits = model(**inp).logits
                probs.append(torch.softmax(logits, dim=-1)[0].numpy())
        p = np.mean(probs, axis=0)
        d = {l: round(float(x), 3) for l, x in zip(LABELS, p)}
        return {"probs": d, "top": max(d, key=d.get)}
    except Exception as e:
        print("톤 분석 실패:", e)
        return None


def tone_hint_text(entries):
    # 하루치 기록의 톤 결과를 평균 내서 Claude에게 줄 문장으로 만듦
    tones = [e.get("voice_tone") for e in entries if e.get("voice_tone")]
    if not tones:
        return ""
    avg = {l: float(np.mean([t["probs"][l] for t in tones])) for l in LABELS}
    top3 = sorted(avg.items(), key=lambda x: -x[1])[:3]
    s = ", ".join(f"{KOR[l]} {round(v * 100)}%" for l, v in top3)
    return f"목소리 톤 분석 결과(보조 참고용, 하루 평균): {s}"
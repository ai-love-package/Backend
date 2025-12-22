# main.py
import os
import base64
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import httpx
from dotenv import load_dotenv
import tempfile
import oss2
import uuid
import dashscope

load_dotenv()

app = FastAPI(title="AI 虚拟恋人 - 后端大脑")

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    raise RuntimeError("请在 .env 中设置 DASHSCOPE_API_KEY")


# === 1. 工具函数：上传音频到临时公网地址（使用 OSS）===
def upload_to_oss(audio_data: bytes) -> str:
    """上传音频到阿里云 OSS，返回公网可访问 URL（用于 DashScope 多模态接口）"""
    auth = oss2.Auth(
        os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    )
    bucket = oss2.Bucket(
        auth,
        'https://oss-cn-shanghai.aliyuncs.com',  # ✅ 和 Bucket 地域一致
        'ai-lover-audio'
    )
    key = f"audio/{uuid.uuid4().hex}.wav"
    bucket.put_object(key, audio_data)
    # 返回公网可读 URL（非 oss:// 协议！）
    public_url = f"https://ai-lover-audio.oss-cn-beijing.aliyuncs.com/{key}"
    print(f"📤 OSS 上传成功: {public_url}")
    return public_url


# === 2. ASR: 语音转文字（使用 paraformer-realtime-v1 + file_url）===
async def speech_to_text(audio_data: bytes) -> str:
    """
    使用 DashScope 的 qwen3-asr-flash 模型进行语音识别
    通过 MultiModalConversation 接口，传入音频 URL
    """
    # 1. 上传音频到 OSS（必须是公网可访问 URL）
    audio_url = upload_to_oss(audio_data)

    # 2. 构造多模态消息
    messages = [
        {
            "role": "system",
            "content": [{"text": ""}]  # 可留空或添加自定义指令
        },
        {
            "role": "user",
            "content": [{"audio": audio_url}]
        }
    ]

    # 3. 调用 DashScope 多模态 ASR
    try:
        response = dashscope.MultiModalConversation.call(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model="qwen3-asr-flash",
            messages=messages
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DashScope ASR 调用失败: {str(e)}")

    # 4. 解析响应
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"DashScope 返回错误: {response}")

    try:
        # 提取 ASR 文本结果
        text = response.output.choices[0].message.content[0].text.strip()
        return text
    except (KeyError, IndexError, AttributeError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"无法解析 ASR 结果: {e}, 原始响应: {response}"
        )

# === 3. LLM: Qwen 对话生成 ===
async def generate_reply(user_input: str) -> str:
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "qwen-max",
        "input": {
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个温柔、可爱的虚拟恋人，说话带点撒娇和关心，用简短自然的中文回复。",
                },
                {"role": "user", "content": user_input},
            ]
        },
        "parameters": {"result_format": "message"},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Qwen 生成失败: {resp.text}")
        data = resp.json()
        try:
            reply = data["output"]["choices"][0]["message"]["content"].strip()
            return reply
        except (KeyError, IndexError):
            raise HTTPException(status_code=500, detail="Qwen 未返回有效回复")


# === 4. TTS: 文字转语音（使用 qwen-tts）===
async def text_to_speech(text: str) -> str:
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "qwen-tts",
        "input": {
            "text": text,
            "voice": "Cherry"  # 可选: Cherry, Zoe, etc.
        }
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"TTS 失败: {resp.text}")
        data = resp.json()
        try:
            output = data.get("output", {})
            audio = output.get("audio", {})
            audio_url = audio.get("url")
            if audio_url:
                return audio_url
            # 如果返回 base64 data（某些情况）
            audio_data = audio.get("data")
            if audio_data:
                audio_bytes = base64.b64decode(audio_data)
                with open("output.wav", "wb") as f:
                    f.write(audio_bytes)
                return "/output.wav"  # 注意：这需要你提供静态文件服务
            raise HTTPException(status_code=500, detail=f"TTS 未返回音频: {data}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"TTS 解析失败: {str(e)}")


# === 5. 主接口 ===
@app.post("/chat")
async def chat_with_lover(audio: UploadFile = File(...)):
    try:
        if audio.content_type not in ["audio/wav", "audio/x-wav"]:
            raise HTTPException(status_code=400, detail="仅支持 WAV 格式音频")

        audio_bytes = await audio.read()
        print(f"✅ 收到音频，大小: {len(audio_bytes)} 字节")

        # 1. ASR
        user_text = await speech_to_text(audio_bytes)
        print(f"🗣️ 用户说: {user_text}")

        # 2. LLM
        reply_text = await generate_reply(user_text)
        print(f"💬 AI回复: {reply_text}")

        # 3. TTS
        reply_audio_url = await text_to_speech(reply_text)
        print(f"🔊 回复语音URL: {reply_audio_url}")

        return JSONResponse({
            "user_text": user_text,
            "reply_text": reply_text,
            "reply_audio_url": reply_audio_url,
        })
    except Exception as e:
        print(f"❌ 发生错误: {repr(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def health_check():
    return {"status": "AI 虚拟恋人后端运行中 ❤️"}
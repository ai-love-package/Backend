## 环境变量配置

1. 复制 `.env.example` 为 `.env`：
   ```bash
   cp .env.example .env
2.填入你自己的密钥：
DASHSCOPE_API_KEY: 从 DashScope 控制台 获取
ALIBABA_CLOUD_ACCESS_KEY_ID/SECRET: 从 RAM 控制台 创建并授权 AliyunOSSFullAccess
确保 .env 不被提交到 Git！
3.测试命令
http://localhost:8000 → 查看配置是否加载
http://localhost:8000/docs → 测试 /chat 接口（需上传 WAV 文件）
终端命令：
.\venv\Scripts\Activate.ps1进入虚拟环境
uvicorn main:app --reload启动
const express = require('express');
const cors = require('cors');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');

const app = express();
const PORT = 5000;

// CORS 설정
app.use(cors());

// Static files 서빙
app.use(express.static('public'));

// ToneBridge Backend API 프록시 (8000번 → /api/*)
app.use('/api', createProxyMiddleware({
  target: 'http://localhost:8000',
  changeOrigin: true,
  logLevel: 'info',
  onProxyReq: (proxyReq, req, res) => {
    console.log(`🔄 API Proxy: ${req.method} ${req.originalUrl} → http://localhost:8000${req.url}`);
  }
}));

// ToneBridge Static files 프록시 (/static/*)
app.use('/static', createProxyMiddleware({
  target: 'http://localhost:8000',
  changeOrigin: true,
  logLevel: 'info'
}));

// 메인 페이지 - ToneBridge 앱 임베드
app.get('/', (req, res) => {
  res.send(`
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ToneBridge Voice Analysis - Client</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .header {
            text-align: center;
            margin-bottom: 20px;
            padding: 20px;
            background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
            color: white;
            border-radius: 8px;
        }
        .service-frame {
            width: 100%;
            height: 800px;
            border: none;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .status {
            text-align: center;
            padding: 10px;
            margin-bottom: 20px;
            background: #e8f5e8;
            border-radius: 6px;
            color: #2d5e2d;
        }
        @media (max-width: 768px) {
            body { padding: 10px; }
            .service-frame { height: 600px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 ToneBridge Voice Analysis</h1>
            <p>한국어 음성 분석 및 발음 학습 플랫폼</p>
            <small>마이크로서비스 아키텍처 | Frontend: 5000 | Backend API: 8000</small>
        </div>
        
        <div class="status">
            ✅ 서비스 연결됨 | API: localhost:8000 | Client: localhost:5000
        </div>
        
        <iframe 
            src="/tonebridge-app" 
            class="service-frame"
            title="ToneBridge Voice Analysis App">
        </iframe>
    </div>

    <script>
        // 서비스 상태 모니터링
        const checkServiceStatus = async () => {
            try {
                const response = await fetch('/api/reference_files');
                const data = await response.json();
                console.log('✅ ToneBridge Backend Service: 연결됨', data);
            } catch (error) {
                console.error('❌ ToneBridge Backend Service: 연결 실패', error);
            }
        };
        
        // 페이지 로드 시 서비스 상태 확인
        checkServiceStatus();
        
        // 5초마다 헬스체크
        setInterval(checkServiceStatus, 5000);
    </script>
</body>
</html>
  `);
});

// ToneBridge 앱 페이지 제공 
app.get('/tonebridge-app', (req, res) => {
  res.redirect('http://localhost:8000/');
});

// 서버 시작
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 ToneBridge Client Server running on http://localhost:${PORT}`);
  console.log(`📡 Proxying API calls to Backend: http://localhost:8000`);
  console.log(`🎯 ToneBridge App: http://localhost:${PORT}/tonebridge-app`);
});
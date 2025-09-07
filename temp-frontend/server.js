const express = require('express');
const cors = require('cors');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');

const app = express();
const PORT = 5000;

// CORS 설정
app.use(cors());

// Favicon 요청 무시 (프록시 서버에서는 불필요)
app.get('/favicon.ico', (req, res) => {
  res.status(204).end();
});

// 🎯 캐시 방지 헤더 추가 (중요!)
app.use((req, res, next) => {
    res.set({
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    });
    next();
});

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

// FastAPI Docs 프록시 (/docs, /redoc)
app.use('/docs', createProxyMiddleware({
  target: 'http://localhost:8000',
  changeOrigin: true,
  logLevel: 'info'
}));

app.use('/redoc', createProxyMiddleware({
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
        .actions {
            text-align: center;
            margin-bottom: 20px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 2px dashed #dee2e6;
        }
        .btn {
            display: inline-block;
            padding: 12px 24px;
            margin: 0 10px;
            background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(255, 107, 53, 0.3);
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(255, 107, 53, 0.4);
        }
        .btn-secondary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        .btn-secondary:hover {
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
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
        
        <div class="actions">
            <h3 style="margin-bottom: 15px; color: #495057;">🚀 ToneBridge 앱 실행</h3>
            <a href="javascript:openToneBridge()" class="btn">
                🎯 새 창에서 열기
            </a>
            <a href="/docs" target="_blank" class="btn btn-secondary">
                🔧 Backend API 문서
            </a>
            <button onclick="toggleIframe()" class="btn btn-secondary">
                📱 임베드 토글
            </button>
        </div>
        
        <iframe 
            id="tonebridge-frame"
            src="/tonebridge-app" 
            class="service-frame"
            title="ToneBridge Voice Analysis App"
            style="display: block;">
        </iframe>
    </div>

    <script>
        // 서비스 상태 모니터링 (한 번만 실행)
        const checkServiceStatus = async () => {
            try {
                const response = await fetch('/api/reference_files');
                const data = await response.json();
                console.log('✅ ToneBridge Backend Service: 연결됨 (초기 체크)');
            } catch (error) {
                console.error('❌ ToneBridge Backend Service: 연결 실패', error);
            }
        };
        
        // 페이지 로드 시 서비스 상태 확인 (한 번만)
        checkServiceStatus();
        
        // iframe 토글 기능
        window.toggleIframe = function() {
            const frame = document.getElementById('tonebridge-frame');
            if (frame.style.display === 'none') {
                frame.style.display = 'block';
            } else {
                frame.style.display = 'none';
            }
        };
        
        // ToneBridge 앱을 새 창에서 열기 (프록시를 통해)
        window.openToneBridge = function() {
            // 현재 주소에서 새 창으로 앱 열기
            const baseUrl = window.location.origin;
            const newWindow = window.open(\`\${baseUrl}/tonebridge-app\`, '_blank', 'width=1200,height=800');
            if (!newWindow) {
                alert('팝업이 차단되었습니다. 브라우저 설정에서 팝업을 허용해주세요.');
            }
        };
    </script>
</body>
</html>
  `);
});

// ToneBridge 앱 페이지 프록시
app.use('/tonebridge-app', createProxyMiddleware({
  target: 'http://localhost:8000',
  changeOrigin: true,
  pathRewrite: {
    '^/tonebridge-app': '' // /tonebridge-app를 제거하고 백엔드 루트로 전달
  },
  logLevel: 'info'
}));

// 서버 시작
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 ToneBridge Client Server running on http://localhost:${PORT}`);
  console.log(`📡 Proxying API calls to Backend: http://localhost:8000`);
  console.log(`🎯 ToneBridge App: http://localhost:${PORT}/tonebridge-app`);
});
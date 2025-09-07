import React from 'react';
import SurveyForm from '../components/SurveyForm';

const SurveyPage: React.FC = () => {
  return (
    <div className="container-fluid">
      {/* 🎯 네비게이션 헤더 */}
      <div className="row mb-4">
        <div className="col-12">
          <nav className="navbar navbar-expand-lg navbar-light bg-light rounded">
            <div className="container-fluid">
              <a 
                className="navbar-brand fw-bold text-primary" 
                href="/tonebridge-app"
              >
                <i className="fas fa-microphone-alt me-2"></i>
                ToneBridge
              </a>
              <div className="navbar-nav">
                <a 
                  className="nav-link" 
                  href="/tonebridge-app"
                >
                  <i className="fas fa-chart-line me-1"></i>
                  음성 분석
                </a>
                <span className="nav-link active fw-bold text-primary">
                  <i className="fas fa-clipboard-list me-1"></i>
                  사용자 설문
                </span>
              </div>
            </div>
          </nav>
        </div>
      </div>

      {/* 🎯 페이지 제목 */}
      <div className="row mb-4">
        <div className="col-12">
          <div className="text-center">
            <h1 className="display-4 fw-bold text-primary mb-3">
              <i className="fas fa-clipboard-list me-3"></i>
              사용자 설문
            </h1>
            <p className="lead text-muted mb-4">
              ToneBridge 음성 분석 서비스 개선을 위한 사용자 의견 수집
            </p>
            <div className="alert alert-info d-inline-block">
              <i className="fas fa-info-circle me-2"></i>
              <strong>소요시간:</strong> 약 3-5분 | <strong>응답 방식:</strong> 선택형 + 주관식
            </div>
          </div>
        </div>
      </div>

      {/* 🎯 설문 양식 */}
      <div className="row justify-content-center">
        <div className="col-lg-8 col-xl-6">
          <SurveyForm />
        </div>
      </div>

      {/* 🎯 하단 안내 */}
      <div className="row mt-5">
        <div className="col-12">
          <div className="alert alert-light text-center">
            <h6 className="fw-bold mb-2">개인정보 보호 안내</h6>
            <small className="text-muted">
              수집된 정보는 서비스 개선 목적으로만 사용되며, 개인정보는 안전하게 보호됩니다.
              <br />
              설문 응답은 언제든지 수정하거나 삭제할 수 있습니다.
            </small>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SurveyPage;
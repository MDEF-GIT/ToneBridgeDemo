import React from 'react';

interface SurveyData {
  [key: string]: string | string[];
}

interface SurveyFormProps {
  onSubmit?: (data: SurveyData) => void;
  className?: string;
}

const SurveyForm: React.FC<SurveyFormProps> = ({ onSubmit, className = '' }) => {
  const [formData, setFormData] = React.useState<SurveyData>({});
  const [isSubmitted, setIsSubmitted] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(false);
  const [showLossAge, setShowLossAge] = React.useState(false);

  // 🎯 자동 저장 (draft) 기능
  const saveDraft = React.useCallback(() => {
    try {
      localStorage.setItem('tonebridge_survey_draft', JSON.stringify(formData));
      console.log('📝 설문 임시저장 완료');
    } catch (e) {
      console.warn('임시저장 실패:', e);
    }
  }, [formData]);

  // 🎯 자동 저장 타이머
  React.useEffect(() => {
    const timer = setTimeout(saveDraft, 2000);
    return () => clearTimeout(timer);
  }, [formData, saveDraft]);

  // 🎯 초기 데이터 로드 (임시저장된 데이터)
  React.useEffect(() => {
    try {
      const draft = localStorage.getItem('tonebridge_survey_draft');
      if (draft) {
        const draftData = JSON.parse(draft);
        setFormData(draftData);
        console.log('📁 임시저장된 설문 데이터 로드됨');
      }
    } catch (e) {
      console.warn('임시저장 데이터 로드 실패:', e);
    }
  }, []);

  // 🎯 입력 값 변경 처리
  const handleInputChange = (name: string, value: string | string[]) => {
    setFormData(prev => ({ ...prev, [name]: value }));

    // 🎯 조건부 필드 표시/숨김
    if (name === 'hearing_loss_time') {
      setShowLossAge(value === 'postlingual');
    }
  };

  // 🎯 체크박스 제한 검증 (최대 3개)
  const handleCheckboxChange = (name: string, value: string, checked: boolean) => {
    const currentValues = (formData[name] as string[]) || [];
    
    if (checked) {
      if (currentValues.length >= 3) {
        alert('최대 3개까지만 선택할 수 있습니다.');
        return;
      }
      handleInputChange(name, [...currentValues, value]);
    } else {
      handleInputChange(name, currentValues.filter(v => v !== value));
    }
  };

  // 🎯 폼 제출 처리
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      // 메타데이터 추가
      const submitData = {
        ...formData,
        submitted_at: new Date().toISOString(),
        user_agent: navigator.userAgent,
        language: navigator.language
      };

      // API 호출
      const response = await fetch('/api/save_survey', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(submitData)
      });

      if (response.ok) {
        setIsSubmitted(true);
        // 임시저장 데이터 삭제
        localStorage.removeItem('tonebridge_survey_draft');
        // 상단으로 스크롤
        window.scrollTo({ top: 0, behavior: 'smooth' });
        onSubmit?.(submitData);
        console.log('✅ 설문 제출 완료');
      } else {
        throw new Error('서버 오류가 발생했습니다.');
      }
    } catch (error) {
      console.error('설문 제출 오류:', error);
      alert('설문 제출 중 오류가 발생했습니다. 다시 시도해 주세요.');
    } finally {
      setIsLoading(false);
    }
  };

  // 🎯 범위 입력 값 표시 컴포넌트
  const RangeInput: React.FC<{ 
    name: string; 
    label: string; 
    min: number; 
    max: number; 
    step?: number;
    value?: number;
  }> = ({ name, label, min, max, step = 1, value = 5 }) => {
    const currentValue = (formData[name] as string) || value.toString();
    
    return (
      <div className="mb-3">
        <label className="form-label">{label}</label>
        <input
          type="range"
          className="form-range"
          name={name}
          min={min}
          max={max}
          step={step}
          value={currentValue}
          onChange={(e) => handleInputChange(name, e.target.value)}
        />
        <div className="text-center mt-1 small text-muted">
          현재 값: {currentValue}
        </div>
      </div>
    );
  };

  if (isSubmitted) {
    return (
      <div className="alert alert-success text-center" id="thankYouMessage">
        <h4>📋 설문 참여 감사합니다!</h4>
        <p>귀하의 소중한 의견이 ToneBridge 개선에 큰 도움이 됩니다.</p>
        <hr />
        <p className="mb-0">
          <small>제출된 데이터는 연구 목적으로만 사용되며, 개인정보는 안전하게 보호됩니다.</small>
        </p>
      </div>
    );
  }

  return (
    <div className={`survey-section ${className}`}>
      <div className="card">
        <div className="card-header">
          <h5 className="mb-0">
            <i className="fas fa-clipboard-list me-2"></i>
            ToneBridge 사용자 설문조사
          </h5>
        </div>
        <div className="card-body">
          <form onSubmit={handleSubmit} noValidate>
            {/* 기본 정보 */}
            <div className="row mb-4">
              <div className="col-md-6">
                <label className="form-label">나이</label>
                <input
                  type="number"
                  className="form-control"
                  name="age"
                  min="18"
                  max="100"
                  value={(formData.age as string) || ''}
                  onChange={(e) => handleInputChange('age', e.target.value)}
                  required
                />
              </div>
              <div className="col-md-6">
                <label className="form-label">성별</label>
                <select
                  className="form-select"
                  name="gender"
                  value={(formData.gender as string) || ''}
                  onChange={(e) => handleInputChange('gender', e.target.value)}
                  required
                >
                  <option value="">선택하세요</option>
                  <option value="male">남성</option>
                  <option value="female">여성</option>
                  <option value="other">기타</option>
                </select>
              </div>
            </div>

            {/* 청력 손실 정보 */}
            <div className="mb-4">
              <label className="form-label">청력 손실 시기</label>
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="radio"
                  name="hearing_loss_time"
                  value="prelingual"
                  checked={(formData.hearing_loss_time as string) === 'prelingual'}
                  onChange={(e) => handleInputChange('hearing_loss_time', e.target.value)}
                />
                <label className="form-check-label">
                  언어 습득 이전 (3세 이전)
                </label>
              </div>
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="radio"
                  name="hearing_loss_time"
                  value="postlingual"
                  checked={(formData.hearing_loss_time as string) === 'postlingual'}
                  onChange={(e) => handleInputChange('hearing_loss_time', e.target.value)}
                />
                <label className="form-check-label">
                  언어 습득 이후 (3세 이후)
                </label>
              </div>
            </div>

            {/* 조건부 필드: 청력 손실 나이 */}
            {showLossAge && (
              <div className="mb-4">
                <label className="form-label">청력 손실 나이</label>
                <input
                  type="number"
                  className="form-control"
                  name="loss_age"
                  min="3"
                  max="100"
                  value={(formData.loss_age as string) || ''}
                  onChange={(e) => handleInputChange('loss_age', e.target.value)}
                  required={showLossAge}
                />
              </div>
            )}

            {/* 한국어 배경 */}
            <div className="mb-4">
              <label className="form-label">한국어 배경</label>
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="radio"
                  name="korean_background"
                  value="native"
                  checked={(formData.korean_background as string) === 'native'}
                  onChange={(e) => handleInputChange('korean_background', e.target.value)}
                />
                <label className="form-check-label">모국어</label>
              </div>
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="radio"
                  name="korean_background"
                  value="second_language"
                  checked={(formData.korean_background as string) === 'second_language'}
                  onChange={(e) => handleInputChange('korean_background', e.target.value)}
                />
                <label className="form-check-label">제2언어</label>
              </div>
            </div>

            {/* 개선 영역 (최대 3개) */}
            <div className="mb-4">
              <label className="form-label">개선하고 싶은 영역 (최대 3개)</label>
              {[
                { value: 'pitch', label: '음높이 조절' },
                { value: 'rhythm', label: '리듬 및 속도' },
                { value: 'pronunciation', label: '발음 정확도' },
                { value: 'intonation', label: '억양 패턴' },
                { value: 'volume', label: '음량 조절' },
                { value: 'clarity', label: '명료도' }
              ].map(({ value, label }) => (
                <div key={value} className="form-check">
                  <input
                    className="form-check-input"
                    type="checkbox"
                    name="improvement_areas"
                    value={value}
                    checked={((formData.improvement_areas as string[]) || []).includes(value)}
                    onChange={(e) => handleCheckboxChange('improvement_areas', value, e.target.checked)}
                  />
                  <label className="form-check-label">{label}</label>
                </div>
              ))}
            </div>

            {/* 만족도 범위 입력 */}
            <RangeInput
              name="satisfaction"
              label="ToneBridge 전반적 만족도 (1-10)"
              min={1}
              max={10}
              value={5}
            />

            <RangeInput
              name="ease_of_use"
              label="사용 편의성 (1-10)"
              min={1}
              max={10}
              value={5}
            />

            {/* 제출 버튼 */}
            <div className="text-center">
              <button
                type="submit"
                className={`btn btn-primary btn-lg ${isLoading ? 'loading' : ''}`}
                disabled={isLoading}
              >
                {isLoading ? '제출 중...' : '설문 제출하기'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default SurveyForm;
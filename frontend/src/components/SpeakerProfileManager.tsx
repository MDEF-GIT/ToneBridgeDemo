import React, { useState, useEffect, useRef, useCallback } from "react";
import { useSpeakerProfile } from "../hooks/useSpeakerProfile";
import { useAdaptiveReference } from "../hooks/useAdaptiveReference";

interface SpeakerProfileManagerProps {
  onReferenceFrequencyChange?: (newReference: number) => void;
  currentFrequency?: number;
}

type RecordingType = "range" | "vowel-a" | "vowel-i" | "vowel-u";

export const SpeakerProfileManager: React.FC<SpeakerProfileManagerProps> = ({
  onReferenceFrequencyChange,
  currentFrequency,
}) => {
  const {
    profile,
    isLoading,
    error,
    measureVoiceRange,
    analyzeVowel,
    calculateOptimalReference,
    createProfile,
    saveProfile,
    loadProfile,
    clearProfile,
    getMeasurementProgress,
    hasVoiceRange,
    hasAllVowels,
    hasOptimalReference,
    currentReference,
  } = useSpeakerProfile();

  const adaptiveHook = useAdaptiveReference();
  const {
    currentReference: adaptiveReference,
    isAdaptive,
    setAdaptiveMode,
    addPitchData,
    getStatistics,
    getTrend,
    adjustmentFactor,
    setAdjustmentFactor,
  } = adaptiveHook;

  const [activeTab, setActiveTab] = useState<
    "profile" | "measurement" | "adaptive"
  >("profile");
  const [userId, setUserId] = useState("");
  const [recordingType, setRecordingType] = useState<RecordingType | null>(
    null,
  );
  const [isRecording, setIsRecording] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const [microphonePermission, setMicrophonePermission] = useState<
    "granted" | "denied" | "prompt" | "unknown"
  >("unknown");

  // 타이머 정리를 위한 ref
  const recordingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  // 권한 체크
  useEffect(() => {
    const checkMicrophonePermission = async () => {
      try {
        const result = await navigator.permissions.query({
          name: "microphone" as PermissionName,
        });
        setMicrophonePermission(result.state);

        result.onchange = () => {
          setMicrophonePermission(result.state);
        };
      } catch (error) {
        console.warn("권한 체크 실패:", error);
      }
    };

    checkMicrophonePermission();
  }, []);

  // 컴포넌트 마운트 시 프로필 로드 시도
  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  // 기준 주파수 변경 시 부모 컴포넌트에 알림
  useEffect(() => {
    const reference = isAdaptive ? adaptiveReference : currentReference;
    if (onReferenceFrequencyChange && reference > 0) {
      onReferenceFrequencyChange(reference);
    }
  }, [
    currentReference,
    adaptiveReference,
    isAdaptive,
    onReferenceFrequencyChange,
  ]);

  // 실시간 피치 데이터 추가 (적응형 모드일 때)
  useEffect(() => {
    if (isAdaptive && currentFrequency && currentFrequency > 0) {
      addPitchData(currentFrequency, 0.8, "normal");
    }
  }, [currentFrequency, isAdaptive, addPitchData]);

  // 컴포넌트 언마운트 시 정리
  useEffect(() => {
    return () => {
      if (recordingTimeoutRef.current) {
        clearTimeout(recordingTimeoutRef.current);
      }
      if (
        mediaRecorderRef.current &&
        mediaRecorderRef.current.state === "recording"
      ) {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const progress = getMeasurementProgress();
  const stats = getStatistics();
  const trend = getTrend();

  // 🎤 녹음 시작 (개선된 버전)
  const startRecording = useCallback(
    async (type: RecordingType) => {
      if (microphonePermission === "denied") {
        setRecordingError(
          "마이크 권한이 거부되었습니다. 브라우저 설정에서 권한을 허용해주세요.",
        );
        return;
      }

      setRecordingType(type);
      setIsRecording(true);
      setRecordingError(null);

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            sampleRate: 44100,
          },
        });

        const mediaRecorder = new MediaRecorder(stream, {
          mimeType: "audio/webm",
        });
        mediaRecorderRef.current = mediaRecorder;

        const audioChunks: Blob[] = [];

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            audioChunks.push(event.data);
          }
        };

        mediaRecorder.onstop = async () => {
          try {
            const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
            const audioFile = new File(
              [audioBlob],
              `${type}-${Date.now()}.webm`,
              {
                type: "audio/webm",
              },
            );

            // 분석 실행
            if (type === "range") {
              await measureVoiceRange(audioFile);
            } else if (type.startsWith("vowel-")) {
              const vowelType = type.split("-")[1] as "a" | "i" | "u";
              await analyzeVowel(audioFile, vowelType);
            }
          } catch (analysisError) {
            console.error("음성 분석 실패:", analysisError);
            setRecordingError("음성 분석에 실패했습니다. 다시 시도해주세요.");
          }

          setIsRecording(false);
          setRecordingType(null);

          // 스트림 정리
          stream.getTracks().forEach((track) => track.stop());
          mediaRecorderRef.current = null;
        };

        mediaRecorder.onerror = (event) => {
          console.error("녹음 오류:", event);
          setRecordingError("녹음 중 오류가 발생했습니다.");
          setIsRecording(false);
          setRecordingType(null);
        };

        mediaRecorder.start();

        // 자동 정지 (10초 후)
        recordingTimeoutRef.current = setTimeout(() => {
          if (mediaRecorder.state === "recording") {
            mediaRecorder.stop();
          }
        }, 10000);
      } catch (err) {
        console.error("녹음 시작 실패:", err);
        let errorMessage = "녹음을 시작할 수 없습니다.";

        if (err instanceof Error) {
          if (err.name === "NotAllowedError") {
            errorMessage =
              "마이크 권한이 필요합니다. 브라우저에서 권한을 허용해주세요.";
            setMicrophonePermission("denied");
          } else if (err.name === "NotFoundError") {
            errorMessage =
              "마이크를 찾을 수 없습니다. 마이크가 연결되어 있는지 확인해주세요.";
          }
        }

        setRecordingError(errorMessage);
        setIsRecording(false);
        setRecordingType(null);
      }
    },
    [microphonePermission, measureVoiceRange, analyzeVowel],
  );

  // 🎤 녹음 정지
  const stopRecording = useCallback(() => {
    if (recordingTimeoutRef.current) {
      clearTimeout(recordingTimeoutRef.current);
      recordingTimeoutRef.current = null;
    }

    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "recording"
    ) {
      mediaRecorderRef.current.stop();
    }

    setIsRecording(false);
    setRecordingType(null);
  }, []);

  // 프로필 생성 핸들러
  const handleCreateProfile = async () => {
    if (!userId.trim()) return;

    try {
      await createProfile(userId.trim());
      setActiveTab("measurement"); // 생성 후 측정 탭으로 이동
    } catch (error) {
      console.error("프로필 생성 실패:", error);
    }
  };

  return (
    <div className="card mt-4">
      <div className="card-header">
        <h5 className="mb-0">
          <i className="fas fa-user-circle me-2"></i>
          화자별 맞춤 기준 주파수 설정
        </h5>

        {/* 탭 네비게이션 */}
        <ul className="nav nav-tabs mt-3" role="tablist">
          <li className="nav-item">
            <button
              className={`nav-link ${activeTab === "profile" ? "active" : ""}`}
              onClick={() => setActiveTab("profile")}
              aria-label="프로on� 관리 탭"
            >
              <i className="fas fa-user me-1"></i>프로필
            </button>
          </li>
          <li className="nav-item">
            <button
              className={`nav-link ${activeTab === "measurement" ? "active" : ""}`}
              onClick={() => setActiveTab("measurement")}
              aria-label="음성 측정 탭"
            >
              <i className="fas fa-microphone me-1"></i>측정
            </button>
          </li>
          <li className="nav-item">
            <button
              className={`nav-link ${activeTab === "adaptive" ? "active" : ""}`}
              onClick={() => setActiveTab("adaptive")}
              aria-label="적응형 설정 탭"
            >
              <i className="fas fa-brain me-1"></i>적응형
            </button>
          </li>
        </ul>
      </div>

      <div className="card-body">
        {/* 권한 경고 */}
        {microphonePermission === "denied" && (
          <div className="alert alert-warning">
            <i className="fas fa-microphone-slash me-2"></i>
            마이크 권한이 거부되었습니다. 음성 측정을 위해 브라우저 설정에서
            마이크 권한을 허용해주세요.
          </div>
        )}

        {/* 녹음 오류 표시 */}
        {recordingError && (
          <div className="alert alert-danger alert-dismissible">
            <i className="fas fa-exclamation-triangle me-2"></i>
            {recordingError}
            <button
              type="button"
              className="btn-close"
              onClick={() => setRecordingError(null)}
              aria-label="오류 메시지 닫기"
            ></button>
          </div>
        )}

        {/* 프로필 탭 */}
        {activeTab === "profile" && (
          <div>
            {!profile ? (
              <div className="text-center py-4">
                <i className="fas fa-user-plus fa-3x text-muted mb-3"></i>
                <h6>새 화자 프로필 생성</h6>
                <div className="row justify-content-center">
                  <div className="col-md-6">
                    <div className="input-group mb-3">
                      <span className="input-group-text">
                        <i className="fas fa-id-badge"></i>
                      </span>
                      <input
                        type="text"
                        className="form-control"
                        placeholder="사용자 ID 입력"
                        value={userId}
                        onChange={(e) => setUserId(e.target.value)}
                        onKeyPress={(e) =>
                          e.key === "Enter" && handleCreateProfile()
                        }
                        aria-label="사용자 ID"
                      />
                    </div>
                    <button
                      className="btn btn-primary"
                      onClick={handleCreateProfile}
                      disabled={!userId.trim() || isLoading}
                    >
                      {isLoading ? (
                        <>
                          <i className="fas fa-spinner fa-spin me-1"></i>
                          생성 중...
                        </>
                      ) : (
                        <>
                          <i className="fas fa-plus me-1"></i>
                          프로필 생성
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div>
                {/* 프로필 정보 표시 */}
                <div className="row mb-4">
                  <div className="col-md-6">
                    <div className="card border-primary">
                      <div className="card-body">
                        <h6 className="card-title">
                          <i className="fas fa-user me-2"></i>
                          {profile.userId}
                        </h6>
                        <p className="card-text">
                          <strong>개인 기준 주파수:</strong>{" "}
                          {profile.personalReference?.toFixed(1) || "N/A"}Hz
                          <br />
                          <strong>신뢰도:</strong>{" "}
                          {((profile.confidence || 0) * 100).toFixed(1)}%<br />
                          <strong>마지막 측정:</strong>{" "}
                          {profile.lastMeasurement
                            ? new Date(
                                profile.lastMeasurement,
                              ).toLocaleDateString()
                            : "N/A"}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="col-md-6">
                    <div className="card border-info">
                      <div className="card-body">
                        <h6 className="card-title">
                          <i className="fas fa-chart-line me-2"></i>
                          측정 진행률
                        </h6>
                        <div className="progress mb-2">
                          <div
                            className="progress-bar"
                            style={{ width: `${progress?.percentage || 0}%` }}
                            role="progressbar"
                            aria-valuemin={0}
                            aria-valuemax={100}
                            aria-valuenow={progress?.percentage || 0}
                          >
                            {progress?.percentage || 0}%
                          </div>
                        </div>
                        <small className="text-muted">
                          {progress?.completed || 0}/{progress?.total || 0} 항목
                          완료
                        </small>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 프로필 관리 버튼 */}
                <div className="d-flex gap-2 flex-wrap">
                  <button
                    className="btn btn-success"
                    onClick={saveProfile}
                    disabled={isLoading}
                  >
                    <i className="fas fa-save me-1"></i>저장
                  </button>
                  <button
                    className="btn btn-info"
                    onClick={loadProfile}
                    disabled={isLoading}
                  >
                    <i className="fas fa-upload me-1"></i>불러오기
                  </button>
                  <button
                    className="btn btn-warning"
                    onClick={clearProfile}
                    disabled={isLoading}
                  >
                    <i className="fas fa-trash me-1"></i>초기화
                  </button>
                  {hasVoiceRange && hasAllVowels && (
                    <button
                      className="btn btn-primary"
                      onClick={() => calculateOptimalReference()}
                      disabled={isLoading}
                    >
                      <i className="fas fa-calculator me-1"></i>
                      {isLoading ? "계산 중..." : "최적 기준점 계산"}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 측정 탭 */}
        {activeTab === "measurement" && (
          <div>
            {!profile ? (
              <div className="text-center py-4">
                <i className="fas fa-user-slash fa-3x text-muted mb-3"></i>
                <h6>프로필이 필요합니다</h6>
                <p className="text-muted">
                  음성 측정을 위해서는 먼저 프로필을 생성해주세요.
                </p>
                <button
                  className="btn btn-primary"
                  onClick={() => setActiveTab("profile")}
                >
                  프로필 생성하기
                </button>
              </div>
            ) : (
              <div className="row">
                {/* 음역대 측정 */}
                <div className="col-md-6 mb-3">
                  <div className="card border-warning">
                    <div className="card-header">
                      <h6 className="mb-0">
                        <i className="fas fa-music me-2"></i>음역대 측정
                      </h6>
                    </div>
                    <div className="card-body">
                      <p className="small">
                        최저음과 최고음을 측정하여 기하평균을 계산합니다.
                      </p>
                      <p className="text-muted">
                        <strong>안내:</strong> 가장 낮은 "음~" 소리와 가장 높은
                        "음~" 소리를 각각 3초씩 내주세요.
                      </p>

                      {hasVoiceRange && profile?.voiceRange && (
                        <div className="alert alert-success">
                          <small>
                            <strong>측정 완료:</strong>
                            <br />
                            최저음: {profile.voiceRange.min_frequency || 0}Hz
                            <br />
                            최고음: {profile.voiceRange.max_frequency || 0}Hz
                            <br />
                            기하평균: {profile.voiceRange.geometric_mean || 0}Hz
                          </small>
                        </div>
                      )}

                      <button
                        className={`btn ${hasVoiceRange ? "btn-outline-warning" : "btn-warning"} w-100`}
                        onClick={() => startRecording("range")}
                        disabled={
                          isRecording ||
                          isLoading ||
                          microphonePermission === "denied"
                        }
                      >
                        {isRecording && recordingType === "range" ? (
                          <>
                            <i className="fas fa-stop me-1"></i>측정 중...
                            (10초)
                          </>
                        ) : (
                          <>
                            <i className="fas fa-microphone me-1"></i>
                            {hasVoiceRange ? "재측정" : "음역대 측정"}
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* 모음별 분석 */}
                <div className="col-md-6 mb-3">
                  <div className="card border-info">
                    <div className="card-header">
                      <h6 className="mb-0">
                        <i className="fas fa-comment me-2"></i>모음별 분석
                      </h6>
                    </div>
                    <div className="card-body">
                      <p className="small">
                        각 모음의 주파수 특성을 분석합니다.
                      </p>

                      <div className="row">
                        {[
                          {
                            vowel: "a" as const,
                            label: "아",
                            color: "primary",
                          },
                          {
                            vowel: "i" as const,
                            label: "이",
                            color: "success",
                          },
                          { vowel: "u" as const, label: "우", color: "danger" },
                        ].map(({ vowel, label, color }) => {
                          const vowelAnalysis = profile?.vowelAnalysis || [];
                          const hasVowel = vowelAnalysis.some(
                            (v) => v?.vowel_type === vowel,
                          );
                          const vowelData = vowelAnalysis.find(
                            (v) => v?.vowel_type === vowel,
                          );

                          return (
                            <div key={vowel} className="col-4 mb-2">
                              <button
                                className={`btn btn-outline-${color} btn-sm w-100`}
                                onClick={() => startRecording(`vowel-${vowel}`)}
                                disabled={
                                  isRecording ||
                                  isLoading ||
                                  microphonePermission === "denied"
                                }
                                aria-label={`${label} 모음 측정`}
                              >
                                {isRecording &&
                                recordingType === `vowel-${vowel}` ? (
                                  <i className="fas fa-circle-notch fa-spin"></i>
                                ) : (
                                  <>
                                    {hasVowel && (
                                      <i className="fas fa-check me-1"></i>
                                    )}
                                    /{label}/
                                  </>
                                )}
                              </button>
                              {hasVowel && vowelData?.fundamental_frequency && (
                                <div className="text-center mt-1">
                                  <small className="text-muted">
                                    {vowelData.fundamental_frequency.toFixed(1)}
                                    Hz
                                  </small>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>

                      <div className="text-center mt-2">
                        <small className="text-muted">
                          {profile?.vowelAnalysis?.length || 0}/3 모음 완료
                        </small>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 적응형 탭 */}
        {activeTab === "adaptive" && (
          <div>
            <div className="row">
              <div className="col-md-6">
                <div className="card border-primary">
                  <div className="card-header">
                    <h6 className="mb-0">
                      <i className="fas fa-cogs me-2"></i>적응형 설정
                    </h6>
                  </div>
                  <div className="card-body">
                    <div className="form-check form-switch mb-3">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        id="adaptiveSwitch"
                        checked={isAdaptive || false}
                        onChange={(e) => setAdaptiveMode?.(e.target.checked)}
                      />
                      <label
                        className="form-check-label"
                        htmlFor="adaptiveSwitch"
                      >
                        실시간 적응형 조정 활성화
                      </label>
                    </div>

                    <div className="mb-3">
                      <label className="form-label" htmlFor="adjustmentRange">
                        조정 강도: {(adjustmentFactor || 0.1).toFixed(2)}
                      </label>
                      <input
                        id="adjustmentRange"
                        type="range"
                        className="form-range"
                        min="0.01"
                        max="0.5"
                        step="0.01"
                        value={adjustmentFactor || 0.1}
                        onChange={(e) =>
                          setAdjustmentFactor?.(parseFloat(e.target.value))
                        }
                        aria-label="적응형 조정 강도"
                      />
                      <small className="text-muted">
                        낮을수록 보수적, 높을수록 민감하게 조정
                      </small>
                    </div>

                    <div className="alert alert-info">
                      <strong>현재 기준 주파수:</strong>
                      <br />
                      {isAdaptive
                        ? (adaptiveReference || 0).toFixed(1)
                        : (currentReference || 0).toFixed(1)}
                      Hz
                      {isAdaptive && (
                        <small className="text-success"> (적응형)</small>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="col-md-6">
                <div className="card border-success">
                  <div className="card-header">
                    <h6 className="mb-0">
                      <i className="fas fa-chart-bar me-2"></i>실시간 통계
                    </h6>
                  </div>
                  <div className="card-body">
                    <div className="row text-center">
                      <div className="col-4">
                        <div className="h6 text-primary">
                          {stats?.count || 0}
                        </div>
                        <small className="text-muted">샘플 수</small>
                      </div>
                      <div className="col-4">
                        <div className="h6 text-success">
                          {stats?.mean || 0}Hz
                        </div>
                        <small className="text-muted">평균</small>
                      </div>
                      <div className="col-4">
                        <div className="h6 text-warning">
                          {(stats?.stability || 0).toFixed(2)}
                        </div>
                        <small className="text-muted">안정성</small>
                      </div>
                    </div>

                    <hr />

                    <div className="text-center">
                      <span
                        className={`badge ${
                          trend === "rising"
                            ? "bg-success"
                            : trend === "falling"
                              ? "bg-danger"
                              : trend === "stable"
                                ? "bg-primary"
                                : "bg-secondary"
                        }`}
                      >
                        {trend === "rising" && (
                          <>
                            <i className="fas fa-arrow-up me-1"></i>상승 트렌드
                          </>
                        )}
                        {trend === "falling" && (
                          <>
                            <i className="fas fa-arrow-down me-1"></i>하락
                            트렌드
                          </>
                        )}
                        {trend === "stable" && (
                          <>
                            <i className="fas fa-minus me-1"></i>안정
                          </>
                        )}
                        {(!trend || trend === "insufficient_data") && (
                          <>
                            <i className="fas fa-question me-1"></i>데이터 부족
                          </>
                        )}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 전역 에러 표시 */}
        {error && (
          <div className="alert alert-danger mt-3">
            <i className="fas fa-exclamation-triangle me-2"></i>
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

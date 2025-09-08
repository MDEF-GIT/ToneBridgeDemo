import React, { useState, useRef, useEffect, useCallback } from "react";
import { YINPitchDetector, PitchResult } from '../utils/pitchAnalysis';
import { AudioPlaybackController } from '../utils/audioUtils';

interface AudioRecordingState {
  isRecording: boolean;
  audioStream: MediaStream | null;
  audioContext: AudioContext | null;
  analyser: AnalyserNode | null;
  error: string | null;
  recordedBlob: Blob | null;
  isPlayingRecorded: boolean;
  // 🎯 새로운 고급 피치 분석 상태
  advancedPitchData: PitchResult[];
  currentPitchConfidence: number;
  // 🎯 자동 처리 결과
  autoProcessResult: any | null;
}

export const useAudioRecording = (learnerInfo?: {name: string, gender: string, ageGroup: string}, selectedFile?: string) => {
  const [state, setState] = useState<AudioRecordingState>({
    isRecording: false,
    audioStream: null,
    audioContext: null,
    analyser: null,
    error: null,
    recordedBlob: null,
    isPlayingRecorded: false,
    // 🎯 새로운 고급 피치 분석 상태
    advancedPitchData: [],
    currentPitchConfidence: 0,
    // 🎯 자동 처리 결과
    autoProcessResult: null,
  });

  const animationFrameRef = useRef<number | undefined>(undefined);
  const onPitchDataRef = useRef<
    ((frequency: number, timestamp: number) => void) | null
  >(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordedAudioRef = useRef<HTMLAudioElement | null>(null);
  
  // 🎯 최신 값을 참조하기 위한 ref들
  const learnerInfoRef = useRef(learnerInfo);
  const selectedFileRef = useRef(selectedFile);
  
  // 🎯 새로운 고급 피치 분석 엔진
  const yinDetectorRef = useRef<YINPitchDetector | null>(null);
  const audioPlaybackRef = useRef<AudioPlaybackController>(new AudioPlaybackController());
  
  // 🎯 ref 값 업데이트
  useEffect(() => {
    learnerInfoRef.current = learnerInfo;
    selectedFileRef.current = selectedFile;
  }, [learnerInfo, selectedFile]);

  // 🎯 상태 변화 추적 로그
  useEffect(() => {
    console.log('🎯 [STEP 3] Hook 상태 변화 감지:', {
      'state.isPlayingRecorded': state.isPlayingRecorded,
      'state.recordedBlob': !!state.recordedBlob,
      'recordedAudioRef.current': !!recordedAudioRef.current
    });
  }, [state.isPlayingRecorded, state.recordedBlob]);

  const startRecording = useCallback(async () => {
    try {
      // 🚨 녹음 시작 전 필수 정보 체크 (최신 ref 값 사용)
      const currentLearnerInfo = learnerInfoRef.current;
      const currentSelectedFile = selectedFileRef.current;
      
      if (!currentLearnerInfo || !currentLearnerInfo.name || !currentLearnerInfo.gender) {
        alert("⚠️ 학습자 정보를 먼저 입력해주세요!\n\n- 이름과 성별은 필수 입력 사항입니다.");
        return;
      }
      
      if (!currentSelectedFile) {
        alert("⚠️ 연습문장을 먼저 선택해주세요!\n\n- 10개 문장 중 하나를 선택해야 녹음할 수 있습니다.");
        return;
      }
      
      console.log("✅ 모든 필수 정보 확인 완료 - 녹음 시작");
      console.log("📋 학습자:", `${currentLearnerInfo.name} (${currentLearnerInfo.gender}, ${currentLearnerInfo.ageGroup || '연령 미지정'})`);
      console.log("📄 연습문장:", currentSelectedFile);
      
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          sampleRate: 44100,
        },
      });

      const audioContext = new AudioContext({ sampleRate: 44100 });
      const analyser = audioContext.createAnalyser();
      const source = audioContext.createMediaStreamSource(stream);

      analyser.fftSize = 4096;
      analyser.smoothingTimeConstant = 0.3;
      source.connect(analyser);
      
      // 🎯 고급 YIN 피치 검출기 초기화
      yinDetectorRef.current = new YINPitchDetector(audioContext.sampleRate, {
        frameMs: 25,
        confidenceThreshold: 0.6,
        voicingThreshold: 0.45
      });

      // Setup MediaRecorder for file saving
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });

      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: "audio/webm",
        });

        setState((prev) => ({
          ...prev,
          recordedBlob: audioBlob,
          // 🎯 피치 분석 데이터 초기화
          advancedPitchData: [],
          currentPitchConfidence: 0,
        }));

        // Upload to backend
        await uploadRecordedAudio(audioBlob);
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(1000); // Record in 1-second chunks

      setState((prev) => ({
        ...prev,
        isRecording: true,
        audioStream: stream,
        audioContext,
        analyser,
        error: null,
      }));

      // Start pitch detection
      const detectPitch = () => {
        if (!analyser) return;

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Float32Array(bufferLength);
        analyser.getFloatFrequencyData(dataArray);

        // Simple pitch detection using autocorrelation
        const sampleRate = audioContext.sampleRate;
        const timeDomainData = new Float32Array(analyser.fftSize);
        analyser.getFloatTimeDomainData(timeDomainData);

        const frequency = autoCorrelate(timeDomainData, sampleRate);

        if (frequency > 0 && onPitchDataRef.current) {
          onPitchDataRef.current(frequency, Date.now());
        }

        animationFrameRef.current = requestAnimationFrame(detectPitch);
      };

      detectPitch();
    } catch (error) {
      setState((prev) => ({
        ...prev,
        error: `마이크 접근 실패: ${error instanceof Error ? error.message : "알 수 없는 오류"}`,
      }));
    }
  }, [learnerInfo, selectedFile]);

  const stopRecording = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      mediaRecorderRef.current.stop();
    }

    if (state.audioStream) {
      state.audioStream.getTracks().forEach((track) => track.stop());
    }

    if (state.audioContext) {
      state.audioContext.close();
    }

    setState((prev) => ({
      ...prev,
      isRecording: false,
      audioStream: null,
      audioContext: null,
      analyser: null,
      error: null,
      recordedBlob: null,
    }));
  }, [state, learnerInfo, selectedFile]);

  const uploadRecordedAudio = async (audioBlob: Blob) => {
    try {
      // 🎯 최신 ref 값 사용
      const currentLearnerInfo = learnerInfoRef.current;
      const currentSelectedFile = selectedFileRef.current;
      
      // 🚨 사용자에게 직접 보여주는 디버깅
      let debugInfo = "🎤 녹음 완료!\n\n";
      debugInfo += `📋 학습자 정보:\n`;
      debugInfo += `  - 이름: ${currentLearnerInfo?.name || "❌ 없음"}\n`;
      debugInfo += `  - 성별: ${currentLearnerInfo?.gender || "❌ 없음"}\n`;
      debugInfo += `  - 연령대: ${currentLearnerInfo?.ageGroup || "❌ 없음"}\n`;
      debugInfo += `📄 선택된 문장: ${currentSelectedFile || "❌ 없음"}\n\n`;
      debugInfo += "이 정보로 파일을 저장합니다.";
      
      alert(debugInfo);
      
      const formData = new FormData();
      formData.append("file", audioBlob, "recording.webm");
      formData.append("sentence_hint", "");
      formData.append("save_permanent", "true");
      
      // 학습자 정보 추가
      if (currentLearnerInfo) {
        formData.append("learner_name", currentLearnerInfo.name || "");
        formData.append("learner_gender", currentLearnerInfo.gender || "");
        formData.append("learner_age_group", currentLearnerInfo.ageGroup || "");
      }
      
      // 연습문장 추가
      if (currentSelectedFile) {
        formData.append("reference_sentence", currentSelectedFile);
      }

      const response = await fetch("/api/auto-process", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        console.log("✅ 자동 처리 완료:", result);
        
        // 처리 결과 상태에 저장
        setState((prev) => ({
          ...prev,
          autoProcessResult: result,
        }));
        
        if (result.success) {
          console.log(`🎯 STT 결과: "${result.transcription}"`);
          console.log(`🔤 ${result.syllables?.length || 0}개 음절 분절 완료`);
        }
      } else {
        console.error("❌ 자동 처리 실패:", response.statusText);
      }
    } catch (error) {
      console.error("❌ 자동 처리 중 오류:", error);
    }
  };

  const playRecordedAudio = useCallback(() => {
    console.log('🎯🎯🎯 [STEP 2] playRecordedAudio 함수 진입!');
    
    // 현재 상태 상세 로깅
    console.log('🎯 [STEP 2.1] 현재 Hook 상태 체크:', {
      'state.recordedBlob': !!state.recordedBlob,
      'state.isPlayingRecorded': state.isPlayingRecorded,
      'state.isRecording': state.isRecording,
      'audioPlaybackController': !!audioPlaybackRef.current
    });
    
    // 현재 상태 확인
    if (!state.recordedBlob) {
      console.log("❌ [STEP 2.2] 녹음된 음성이 없습니다 - 함수 종료");
      return;
    }
    console.log("✅ [STEP 2.2] 녹음된 음성 존재 확인됨");

    // 현재 재생 중이면 정지 (새로운 AudioPlaybackController 사용)
    if (state.isPlayingRecorded) {
      console.log("🛑 [STEP 2.3] 현재 재생 중 - 새로운 컨트롤러로 중지");
      
      audioPlaybackRef.current.stop();
      
      console.log("🛑 [STEP 2.3.4] setState로 isPlayingRecorded: false 설정");
      setState(prev => {
        console.log("🛑 [STEP 2.3.5] setState 콜백 실행 - 이전 상태:", prev.isPlayingRecorded);
        return { ...prev, isPlayingRecorded: false };
      });
      
      console.log("🛑 [STEP 2.3.6] 중지 프로세스 완료 - 함수 종료");
      return;
    }
    console.log("✅ [STEP 2.3] 현재 재생 중이 아님 - 재생 시작 프로세스로 진행");

    // 새로운 AudioPlaybackController로 재생 시작
    console.log("▶️ [STEP 2.4] 새로운 오디오 컨트롤러로 재생 시작");
    try {
      audioPlaybackRef.current.play(state.recordedBlob, () => {
        console.log("🔚 [EVENT] 새로운 컨트롤러 - 재생 완료 이벤트");
        setState(prev => {
          console.log("🔚 [EVENT] setState로 isPlayingRecorded: false 설정");
          return { ...prev, isPlayingRecorded: false };
        });
      }).then(() => {
        console.log("✅ [STEP 2.4.9] 새로운 컨트롤러 재생 성공");
        setState(prev => {
          console.log("✅ [STEP 2.4.10] setState로 isPlayingRecorded: true 설정");
          return { ...prev, isPlayingRecorded: true };
        });
        console.log("✅ [STEP 2.4.11] 재생 시작 프로세스 완료");
      }).catch((error) => {
        console.error("❌ [STEP 2.4.9] 새로운 컨트롤러 재생 실패:", error);
        setState(prev => {
          console.log("❌ [STEP 2.4.10] setState로 isPlayingRecorded: false 설정");
          return { ...prev, isPlayingRecorded: false };
        });
        console.log("❌ [STEP 2.4.11] 재생 실패 정리 작업 완료");
      });

    } catch (error) {
      console.error("❌ [STEP 2.4] try-catch 블록에서 예외 발생:", error);
      setState(prev => {
        console.log("❌ [STEP 2.4.ERROR] setState로 isPlayingRecorded: false 설정");
        return { ...prev, isPlayingRecorded: false };
      });
    }
    
    console.log('🎯🎯🎯 [STEP 2] playRecordedAudio 함수 종료');
  }, [state.recordedBlob, state.isPlayingRecorded]);

  const setPitchCallback = useCallback(
    (callback: (frequency: number, timestamp: number) => void) => {
      onPitchDataRef.current = callback;
    },
    [],
  );

  return {
    ...state,
    startRecording,
    stopRecording,
    playRecordedAudio,
    setPitchCallback,
  };
};

// Autocorrelation pitch detection algorithm
function autoCorrelate(buffer: Float32Array, sampleRate: number): number {
  const SIZE = buffer.length;
  const MAX_SAMPLES = Math.floor(SIZE / 2);
  let bestOffset = -1;
  let bestCorrelation = 0;
  let rms = 0;
  let foundGoodCorrelation = false;
  const correlations = new Array(MAX_SAMPLES);

  for (let i = 0; i < SIZE; i++) {
    const val = buffer[i];
    rms += val * val;
  }
  rms = Math.sqrt(rms / SIZE);

  if (rms < 0.01) return -1;

  let lastCorrelation = 1;
  for (let offset = 1; offset < MAX_SAMPLES; offset++) {
    let correlation = 0;
    for (let i = 0; i < MAX_SAMPLES; i++) {
      correlation += Math.abs(buffer[i] - buffer[i + offset]);
    }
    correlation = 1 - correlation / MAX_SAMPLES;
    correlations[offset] = correlation;

    if (correlation > 0.9 && correlation > lastCorrelation) {
      foundGoodCorrelation = true;
      if (correlation > bestCorrelation) {
        bestCorrelation = correlation;
        bestOffset = offset;
      }
    } else if (foundGoodCorrelation) {
      const shift =
        (correlations[bestOffset + 1] - correlations[bestOffset - 1]) /
        correlations[bestOffset];
      return sampleRate / (bestOffset + 8 * shift);
    }
    lastCorrelation = correlation;
  }

  if (bestCorrelation > 0.01) {
    return sampleRate / bestOffset;
  }
  return -1;
}

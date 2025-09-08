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
  
  // 🎯 새로운 고급 피치 분석 엔진
  const yinDetectorRef = useRef<YINPitchDetector | null>(null);
  const audioPlaybackRef = useRef<AudioPlaybackController>(new AudioPlaybackController());

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
      console.log("🎬🎬🎬 [START] 녹음 시작 요청");
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          sampleRate: 44100,
        },
      });
      console.log("🎬 [START] 미디어 스트림 획득 완료");

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
        console.log("🎬 [DEBUG] MediaRecorder 중지됨 - onstop 실행");
        console.log("🎬 [DEBUG] 오디오 청크 수:", audioChunksRef.current.length);
        
        const audioBlob = new Blob(audioChunksRef.current, {
          type: "audio/webm",
        });
        
        console.log("🎬 [DEBUG] 오디오 Blob 생성 완료:", {
          size: audioBlob.size,
          type: audioBlob.type
        });
        console.log("🎬 [DEBUG] learnerInfo:", learnerInfo);
        console.log("🎬 [DEBUG] selectedFile:", selectedFile);

        setState((prev) => ({
          ...prev,
          recordedBlob: audioBlob,
          // 🎯 피치 분석 데이터 초기화
          advancedPitchData: [],
          currentPitchConfidence: 0,
        }));

        // Upload to backend
        console.log("🎬 [DEBUG] uploadRecordedAudio 호출 시작");
        await uploadRecordedAudio(audioBlob);
        console.log("🎬 [DEBUG] uploadRecordedAudio 호출 완료");
      };

      mediaRecorderRef.current = mediaRecorder;
      console.log("🎬 [START] MediaRecorder 설정 완료");
      mediaRecorder.start(1000); // Record in 1-second chunks
      console.log("🎬 [START] MediaRecorder 시작됨");

      setState((prev) => ({
        ...prev,
        isRecording: true,
        audioStream: stream,
        audioContext,
        analyser,
        error: null,
      }));
      console.log("🎬 [START] 녹음 상태 업데이트 완료");

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
  }, []);

  const stopRecording = useCallback(() => {
    console.log("🛑🛑🛑 [STOP] stopRecording 호출됨");
    console.log("🛑 [STOP] mediaRecorderRef.current:", !!mediaRecorderRef.current);
    console.log("🛑 [STOP] mediaRecorderRef state:", mediaRecorderRef.current?.state);
    
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      console.log("🛑 [STOP] AnimationFrame 취소됨");
    }

    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      console.log("🛑 [STOP] MediaRecorder.stop() 호출");
      mediaRecorderRef.current.stop();
    } else {
      console.log("❌ [STOP] MediaRecorder가 없거나 이미 비활성 상태");
    }

    if (state.audioStream) {
      state.audioStream.getTracks().forEach((track) => track.stop());
      console.log("🛑 [STOP] AudioStream 트랙 정지됨");
    }

    if (state.audioContext) {
      state.audioContext.close();
      console.log("🛑 [STOP] AudioContext 닫힘");
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
    
    console.log("🛑 [STOP] setState 완료");
  }, [state]);

  const uploadRecordedAudio = async (audioBlob: Blob) => {
    try {
      console.log("🎤🎤🎤 [UPLOAD] 녹음 완료 - 자동 처리 시작...");
      console.log("📋 [UPLOAD] 학습자 정보:", learnerInfo);
      console.log("📄 [UPLOAD] 선택된 문장:", selectedFile);
      console.log("💾 [UPLOAD] 오디오 Blob 크기:", audioBlob.size);
      
      const formData = new FormData();
      formData.append("file", audioBlob, "recording.webm");
      formData.append("sentence_hint", ""); // 힌트 없이 순수 STT
      formData.append("save_permanent", "true"); // 영구 저장 활성화
      
      // 학습자 정보 추가
      if (learnerInfo) {
        formData.append("learner_name", learnerInfo.name || "");
        formData.append("learner_gender", learnerInfo.gender || "");
        formData.append("learner_age_group", learnerInfo.ageGroup || "");
      }
      
      // 선택된 연습문장 정보 추가
      if (selectedFile) {
        formData.append("reference_sentence", selectedFile);
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

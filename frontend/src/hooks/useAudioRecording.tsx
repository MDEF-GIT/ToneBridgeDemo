import { useState, useRef, useCallback, useEffect } from "react";

interface AudioRecordingState {
  isRecording: boolean;
  audioStream: MediaStream | null;
  audioContext: AudioContext | null;
  analyser: AnalyserNode | null;
  error: string | null;
  recordedBlob: Blob | null;
  isPlayingRecorded: boolean;
}

export const useAudioRecording = () => {
  const [state, setState] = useState<AudioRecordingState>({
    isRecording: false,
    audioStream: null,
    audioContext: null,
    analyser: null,
    error: null,
    recordedBlob: null,
    isPlayingRecorded: false,
  });

  const animationFrameRef = useRef<number | undefined>(undefined);
  const onPitchDataRef = useRef<
    ((frequency: number, timestamp: number) => void) | null
  >(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordedAudioRef = useRef<HTMLAudioElement | null>(null);

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
  }, []);
  console.log("❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌");
  const stopRecording = useCallback(() => {
    console.log("❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌2222");
    if (animationFrameRef.current) {
      console.log("❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌33333");
      cancelAnimationFrame(animationFrameRef.current);
    }

    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      console.log("❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌44444");
      mediaRecorderRef.current.stop();
    }

    if (state.audioStream) {
      console.log("❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌55555");
      state.audioStream.getTracks().forEach((track) => track.stop());
    }

    if (state.audioContext) {
      console.log("❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌66666");
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
  }, [state]);

  const uploadRecordedAudio = async (audioBlob: Blob) => {
    try {
      const formData = new FormData();
      formData.append("audio_data", audioBlob, "recording.webm");
      formData.append("session_id", `session_${Date.now()}`);

      const response = await fetch("/api/record_realtime", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        console.log("✅ 녹음 파일 업로드 성공");
      } else {
        console.error("❌ 녹음 파일 업로드 실패:", response.statusText);
      }
    } catch (error) {
      console.error("❌ 업로드 중 오류:", error);
    }
  };

  const playRecordedAudio = useCallback(() => {
    console.log('🎯🎯🎯 [STEP 2] playRecordedAudio 함수 진입!');
    
    // 현재 상태 상세 로깅
    console.log('🎯 [STEP 2.1] 현재 Hook 상태 체크:', {
      'state.recordedBlob': !!state.recordedBlob,
      'state.isPlayingRecorded': state.isPlayingRecorded,
      'state.isRecording': state.isRecording,
      'recordedAudioRef.current': !!recordedAudioRef.current
    });
    
    // 현재 상태 확인
    if (!state.recordedBlob) {
      console.log("❌ [STEP 2.2] 녹음된 음성이 없습니다 - 함수 종료");
      return;
    }
    console.log("✅ [STEP 2.2] 녹음된 음성 존재 확인됨");

    // 현재 재생 중이면 정지
    if (state.isPlayingRecorded) {
      console.log("🛑 [STEP 2.3] 현재 재생 중 - 중지 프로세스 시작");
      
      if (recordedAudioRef.current) {
        console.log("🛑 [STEP 2.3.1] 오디오 레퍼런스 존재 - pause() 호출");
        recordedAudioRef.current.pause();
        
        console.log("🛑 [STEP 2.3.2] currentTime = 0 설정");
        recordedAudioRef.current.currentTime = 0;
        
        console.log("🛑 [STEP 2.3.3] 레퍼런스 null로 설정");
        recordedAudioRef.current = null;
      } else {
        console.log("⚠️ [STEP 2.3.1] 오디오 레퍼런스가 null임");
      }
      
      console.log("🛑 [STEP 2.3.4] setState로 isPlayingRecorded: false 설정");
      setState(prev => {
        console.log("🛑 [STEP 2.3.5] setState 콜백 실행 - 이전 상태:", prev.isPlayingRecorded);
        return { ...prev, isPlayingRecorded: false };
      });
      
      console.log("🛑 [STEP 2.3.6] 중지 프로세스 완료 - 함수 종료");
      return;
    }
    console.log("✅ [STEP 2.3] 현재 재생 중이 아님 - 재생 시작 프로세스로 진행");

    // 재생 시작
    console.log("▶️ [STEP 2.4] 녹음음성 재생 시작 프로세스");
    try {
      console.log("▶️ [STEP 2.4.1] URL.createObjectURL() 호출");
      const audioUrl = URL.createObjectURL(state.recordedBlob);
      console.log("▶️ [STEP 2.4.2] 오디오 URL 생성 완료:", audioUrl.substring(0, 50) + '...');
      
      console.log("▶️ [STEP 2.4.3] new Audio() 객체 생성");
      const audio = new Audio(audioUrl);
      console.log("▶️ [STEP 2.4.4] 오디오 객체 생성 완료");

      console.log("▶️ [STEP 2.4.5] recordedAudioRef.current에 오디오 객체 할당");
      recordedAudioRef.current = audio;

      console.log("▶️ [STEP 2.4.6] 이벤트 리스너 설정 시작");
      audio.onended = () => {
        console.log("🔚 [EVENT] 녹음음성 재생 완료 이벤트 발생");
        setState(prev => {
          console.log("🔚 [EVENT] setState로 isPlayingRecorded: false 설정");
          return { ...prev, isPlayingRecorded: false };
        });
        recordedAudioRef.current = null;
        URL.revokeObjectURL(audioUrl);
        console.log("🔚 [EVENT] 정리 작업 완료");
      };

      audio.onerror = (event) => {
        console.log("❌ [EVENT] 녹음음성 재생 오류 이벤트 발생:", event);
        setState(prev => {
          console.log("❌ [EVENT] setState로 isPlayingRecorded: false 설정");
          return { ...prev, isPlayingRecorded: false };
        });
        recordedAudioRef.current = null;
        URL.revokeObjectURL(audioUrl);
        console.log("❌ [EVENT] 오류 정리 작업 완료");
      };
      console.log("▶️ [STEP 2.4.7] 이벤트 리스너 설정 완료");

      // 비동기 재생 시작
      console.log("▶️ [STEP 2.4.8] audio.play() 호출 시작");
      audio.play().then(() => {
        console.log("✅ [STEP 2.4.9] audio.play() 성공 - 재생 시작됨");
        setState(prev => {
          console.log("✅ [STEP 2.4.10] setState로 isPlayingRecorded: true 설정");
          return { ...prev, isPlayingRecorded: true };
        });
        console.log("✅ [STEP 2.4.11] 재생 시작 프로세스 완료");
      }).catch((error) => {
        console.error("❌ [STEP 2.4.9] audio.play() 실패:", error);
        setState(prev => {
          console.log("❌ [STEP 2.4.10] setState로 isPlayingRecorded: false 설정");
          return { ...prev, isPlayingRecorded: false };
        });
        recordedAudioRef.current = null;
        URL.revokeObjectURL(audioUrl);
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

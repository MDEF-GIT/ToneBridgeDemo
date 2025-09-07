import { useState, useRef, useCallback } from 'react';

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
    isPlayingRecorded: false
  });

  const animationFrameRef = useRef<number | undefined>(undefined);
  const onPitchDataRef = useRef<((frequency: number, timestamp: number) => void) | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordedAudioRef = useRef<HTMLAudioElement | null>(null);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          sampleRate: 44100
        } 
      });

      const audioContext = new AudioContext({ sampleRate: 44100 });
      const analyser = audioContext.createAnalyser();
      const source = audioContext.createMediaStreamSource(stream);
      
      analyser.fftSize = 4096;
      analyser.smoothingTimeConstant = 0.3;
      source.connect(analyser);

      // Setup MediaRecorder for file saving
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        
        setState(prev => ({
          ...prev,
          recordedBlob: audioBlob
        }));

        // Upload to backend
        await uploadRecordedAudio(audioBlob);
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(1000); // Record in 1-second chunks

      setState(prev => ({
        ...prev,
        isRecording: true,
        audioStream: stream,
        audioContext,
        analyser,
        error: null
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
      setState(prev => ({
        ...prev,
        error: `마이크 접근 실패: ${error instanceof Error ? error.message : '알 수 없는 오류'}`
      }));
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }

    if (state.audioStream) {
      state.audioStream.getTracks().forEach(track => track.stop());
    }

    if (state.audioContext) {
      state.audioContext.close();
    }

    setState(prev => ({
      ...prev,
      isRecording: false,
      audioStream: null,
      audioContext: null,
      analyser: null,
      error: null,
      recordedBlob: null
    }));
  }, [state]);

  const uploadRecordedAudio = async (audioBlob: Blob) => {
    try {
      const formData = new FormData();
      formData.append('audio_data', audioBlob, 'recording.webm');
      formData.append('session_id', `session_${Date.now()}`);

      const response = await fetch('/api/record_realtime', {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        console.log('✅ 녹음 파일 업로드 성공');
      } else {
        console.error('❌ 녹음 파일 업로드 실패:', response.statusText);
      }
    } catch (error) {
      console.error('❌ 업로드 중 오류:', error);
    }
  };

  const playRecordedAudio = useCallback(() => {
    if (!state.recordedBlob) {
      console.log('❌ 녹음된 음성이 없습니다');
      return;
    }

    // 현재 재생 중이면 정지
    if (state.isPlayingRecorded) {
      console.log('🛑 녹음음성 재생 중지');
      if (recordedAudioRef.current) {
        recordedAudioRef.current.pause();
        recordedAudioRef.current.currentTime = 0;
        recordedAudioRef.current = null;
      }
      setState(prev => ({ ...prev, isPlayingRecorded: false }));
      return;
    }

    console.log('▶️ 녹음음성 재생 시작');
    try {
      const audioUrl = URL.createObjectURL(state.recordedBlob);
      const audio = new Audio(audioUrl);
      
      recordedAudioRef.current = audio;
      
      // 즉시 재생 상태로 설정
      setState(prev => ({ ...prev, isPlayingRecorded: true }));

      audio.onended = () => {
        console.log('🔚 녹음음성 재생 완료');
        setState(prev => ({ ...prev, isPlayingRecorded: false }));
        recordedAudioRef.current = null;
        URL.revokeObjectURL(audioUrl);
      };

      audio.onerror = () => {
        console.log('❌ 녹음음성 재생 오류');
        setState(prev => ({ ...prev, isPlayingRecorded: false }));
        recordedAudioRef.current = null;
        URL.revokeObjectURL(audioUrl);
      };

      audio.onpause = () => {
        console.log('⏸️ 녹음음성 일시정지');
        setState(prev => ({ ...prev, isPlayingRecorded: false }));
      };

      // 비동기 재생 시작
      audio.play().catch(error => {
        console.error('❌ 재생 실패:', error);
        setState(prev => ({ ...prev, isPlayingRecorded: false }));
        recordedAudioRef.current = null;
        URL.revokeObjectURL(audioUrl);
      });
    } catch (error) {
      console.error('❌ 녹음음성 재생 실패:', error);
      setState(prev => ({ ...prev, isPlayingRecorded: false }));
    }
  }, [state.recordedBlob, state.isPlayingRecorded]);

  const setPitchCallback = useCallback((callback: (frequency: number, timestamp: number) => void) => {
    onPitchDataRef.current = callback;
  }, []);

  return {
    ...state,
    startRecording,
    stopRecording,
    playRecordedAudio,
    setPitchCallback
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
      correlation += Math.abs((buffer[i]) - (buffer[i + offset]));
    }
    correlation = 1 - (correlation / MAX_SAMPLES);
    correlations[offset] = correlation;
    
    if (correlation > 0.9 && correlation > lastCorrelation) {
      foundGoodCorrelation = true;
      if (correlation > bestCorrelation) {
        bestCorrelation = correlation;
        bestOffset = offset;
      }
    } else if (foundGoodCorrelation) {
      const shift = (correlations[bestOffset + 1] - correlations[bestOffset - 1]) / correlations[bestOffset];
      return sampleRate / (bestOffset + (8 * shift));
    }
    lastCorrelation = correlation;
  }
  
  if (bestCorrelation > 0.01) {
    return sampleRate / bestOffset;
  }
  return -1;
}
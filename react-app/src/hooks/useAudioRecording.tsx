import { useState, useRef, useCallback } from 'react';

interface AudioRecordingState {
  isRecording: boolean;
  audioStream: MediaStream | null;
  audioContext: AudioContext | null;
  analyser: AnalyserNode | null;
  error: string | null;
}

export const useAudioRecording = () => {
  const [state, setState] = useState<AudioRecordingState>({
    isRecording: false,
    audioStream: null,
    audioContext: null,
    analyser: null,
    error: null
  });

  const animationFrameRef = useRef<number>();
  const onPitchDataRef = useRef<((frequency: number, timestamp: number) => void) | null>(null);

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

    if (state.audioStream) {
      state.audioStream.getTracks().forEach(track => track.stop());
    }

    if (state.audioContext) {
      state.audioContext.close();
    }

    setState({
      isRecording: false,
      audioStream: null,
      audioContext: null,
      analyser: null,
      error: null
    });
  }, [state]);

  const setPitchCallback = useCallback((callback: (frequency: number, timestamp: number) => void) => {
    onPitchDataRef.current = callback;
  }, []);

  return {
    ...state,
    startRecording,
    stopRecording,
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
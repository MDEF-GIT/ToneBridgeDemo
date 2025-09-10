/**
 * ToneBridge 특화 API 함수들
 * 공통 API 클라이언트를 사용하여 모든 ToneBridge API 호출을 표준화
 */

import apiClient, { ApiResponse } from './apiClient';

// 타입 정의들
export interface ReferenceFile {
  id: string;
  title: string;
  sentence_text: string;
  duration: number;
  detected_gender: string;
  average_f0: number;
}

export interface UploadedFile {
  file_id: string;
  filename: string;
  expected_text: string;
  has_textgrid: boolean;
  file_size: number;
  modified_time: number;
}

export interface PitchPoint {
  time: number;
  frequency: number;
  syllable?: string;
  start?: number;
  end?: number;
}

export interface SyllableData {
  label: string;
  start: number;
  end: number;
  frequency?: number;
  semitone?: number;
}

// 🎭 화자 프로필 인터페이스
export interface SpeakerProfile {
  profile_id: string;
  name: string;
  gender: string;
  age_group: string;
  reference_frequency: number;
  measurements: any;
  created_at: string;
  updated_at: string;
  measurement_count: number;
}

/**
 * 참조 파일 관련 API
 */
export const referenceFilesApi = {
  /**
   * 참조 파일 목록 조회
   */
  async getList(): Promise<ApiResponse<ReferenceFile[]>> {
    return apiClient.getArray<ReferenceFile>('/api/reference_files');
  },

  /**
   * 참조 파일 피치 데이터 조회
   */
  async getPitchData(fileId: string, syllableOnly: boolean = true): Promise<ApiResponse<PitchPoint[]>> {
    const endpoint = `/api/reference_files/${encodeURIComponent(fileId)}/pitch?syllable_only=${syllableOnly}`;
    return apiClient.getArray<PitchPoint>(endpoint);
  },

  /**
   * 참조 파일 음절 데이터 조회
   */
  async getSyllables(fileId: string): Promise<ApiResponse<string[]>> {
    const endpoint = `/api/reference_files/${encodeURIComponent(fileId)}/syllables`;
    return apiClient.getArray<string>(endpoint);
  },

  /**
   * 참조 파일 WAV 다운로드 URL 생성
   */
  getWavUrl(fileId: string): string {
    return `/api/reference_files/${encodeURIComponent(fileId)}/wav`;
  }
};

/**
 * 업로드 파일 관련 API
 */
export const uploadedFilesApi = {
  /**
   * 업로드 파일 목록 조회
   */
  async getList(): Promise<ApiResponse<UploadedFile[]>> {
    const response = await apiClient.getObject('/api/uploaded_files');
    if (response.success && response.data) {
      // 중복 API 호출 방지: 백엔드에서 통합된 구조 처리
      const files = response.data.files || response.data;
      return {
        ...response,
        data: Array.isArray(files) ? files : []
      };
    }
    return response;
  },

  /**
   * 업로드 파일 피치 데이터 조회 (통합 버전)
   */
  async getPitchData(fileId: string): Promise<ApiResponse<PitchPoint[]>> {
    // syllable_only=true로 통합 데이터 한 번에 로드
    const endpoint = `/api/uploaded_files/${encodeURIComponent(fileId)}/pitch?syllable_only=true`;
    return apiClient.getArray<PitchPoint>(endpoint, {
      logRequest: true,
      logResponse: true
    });
  },

  /**
   * 파일 최적화 요청
   */
  async optimize(fileId: string): Promise<ApiResponse<any>> {
    const formData = new FormData();
    formData.append('file_id', fileId);
    
    return apiClient.post('/api/optimize-uploaded-file', formData, {
      logRequest: true,
      logResponse: true
    });
  },

  /**
   * 업로드된 파일 삭제 (WAV + TextGrid)
   */
  async delete(fileId: string): Promise<ApiResponse<any>> {
    const endpoint = `/api/uploaded_files/${encodeURIComponent(fileId)}`;
    
    return apiClient.fetch(endpoint, {
      method: 'DELETE',
      logRequest: true,
      logResponse: true
    });
  },

  /**
   * 업로드 파일 WAV URL 생성
   */
  getWavUrl(fileId: string): string {
    return `/uploads/${encodeURIComponent(fileId)}.wav`;
  }
};

/**
 * 녹음 및 실시간 분석 API
 */
export const recordingApi = {
  /**
   * 실시간 녹음 데이터 업로드
   */
  async uploadRealtime(audioBlob: Blob, metadata: any): Promise<ApiResponse<any>> {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');
    
    // 메타데이터 추가
    Object.entries(metadata).forEach(([key, value]) => {
      formData.append(key, String(value));
    });

    return apiClient.uploadFile('/api/record_realtime', formData);
  },

  /**
   * 자동 처리 API (WebM → WAV → STT → TextGrid)
   */
  async autoProcess(file: File, options: {
    sentenceHint?: string;
    savePermanent?: boolean;
    learnerName?: string;
    learnerGender?: string;
    learnerAgeGroup?: string;
    referenceSentence?: string;
  } = {}): Promise<ApiResponse<any>> {
    const formData = new FormData();
    formData.append('file', file);
    
    // 옵션 추가
    Object.entries(options).forEach(([key, value]) => {
      if (value !== undefined) {
        formData.append(key, String(value));
      }
    });

    return apiClient.uploadFile('/api/auto-process', formData, {
      timeout: 60000, // 자동 처리는 오래 걸릴 수 있음
      logRequest: true,
      logResponse: true
    });
  }
};

/**
 * 기타 API
 */
export const miscApi = {
  /**
   * 설문 데이터 저장
   */
  async saveSurvey(surveyData: any): Promise<ApiResponse<any>> {
    return apiClient.post('/api/save_survey', surveyData);
  },

  /**
   * 세션 데이터 저장
   */
  async saveSession(sessionData: any): Promise<ApiResponse<any>> {
    return apiClient.post('/api/save_session', sessionData);
  }
};

/**
 * 화자 프로필 관리 API
 */
export const speakerProfileApi = {
  /**
   * 프로필 생성/업데이트
   */
  async create(profileData: {
    name: string;
    gender: string;
    age_group?: string;
    reference_frequency?: number;
    measurements?: any;
  }): Promise<ApiResponse<{ profile_id: string; profile: SpeakerProfile }>> {
    return apiClient.post('/api/speaker-profile', profileData, {
      logRequest: true,
      logResponse: true
    });
  },

  /**
   * 모든 프로필 목록 조회
   */
  async getList(): Promise<ApiResponse<{ profiles: SpeakerProfile[]; total_count: number }>> {
    return apiClient.getObject('/api/speaker-profiles');
  },

  /**
   * 특정 프로필 조회
   */
  async getProfile(profileId: string): Promise<ApiResponse<{ profile: SpeakerProfile }>> {
    const endpoint = `/api/speaker-profile/${encodeURIComponent(profileId)}`;
    return apiClient.getObject(endpoint);
  },

  /**
   * 프로필 삭제
   */
  async delete(profileId: string): Promise<ApiResponse<any>> {
    const endpoint = `/api/speaker-profile/${encodeURIComponent(profileId)}`;
    return apiClient.fetch(endpoint, {
      method: 'DELETE',
      logRequest: true,
      logResponse: true
    });
  }
};

/**
 * 통합 ToneBridge API 객체 (화자 프로필 시스템 확장)
 */
export const tonebridgeApi = {
  // 🔄 범용 HTTP 메서드들 (화자 프로필 시스템용)
  get: (url: string, config?: any) => apiClient.get(url, config),
  post: (url: string, data?: any, config?: any) => apiClient.post(url, data, config),
  
  // 기존 API들
  referenceFiles: referenceFilesApi,
  uploadedFiles: uploadedFilesApi,
  recording: recordingApi,
  misc: miscApi,
  
  // 🎭 새로운 화자 프로필 API
  speakerProfile: speakerProfileApi
};

export default tonebridgeApi;
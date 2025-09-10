/**
 * 통합 API 클라이언트 - ToneBridge 시스템 일관성 개선
 * 모든 API 호출의 에러 처리, 로깅, 검증을 표준화
 */

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  status?: number;
}

export interface FetchOptions extends RequestInit {
  timeout?: number;
  validateArray?: boolean;
  validateObject?: boolean;
  logRequest?: boolean;
  logResponse?: boolean;
}

class ApiClient {
  private baseURL: string = '';

  /**
   * 통합 fetch 메서드 - 모든 API 호출의 진입점
   */
  async fetch<T = any>(
    endpoint: string, 
    options: FetchOptions = {}
  ): Promise<ApiResponse<T>> {
    const {
      timeout = 30000,
      validateArray = false,
      validateObject = false,
      logRequest = true,
      logResponse = true,
      ...fetchOptions
    } = options;

    const url = `${this.baseURL}${endpoint}`;
    
    if (logRequest) {
      console.log(`🌐 API 요청: ${fetchOptions.method || 'GET'} ${url}`);
    }

    try {
      // 타임아웃 처리
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      
      const response = await fetch(url, {
        ...fetchOptions,
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);

      // 응답 상태 검증
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      // 데이터 타입 검증
      if (validateArray && !Array.isArray(data)) {
        throw new Error(`응답 데이터가 배열이 아닙니다: ${typeof data}`);
      }

      if (validateObject && (typeof data !== 'object' || data === null)) {
        throw new Error(`응답 데이터가 객체가 아닙니다: ${typeof data}`);
      }

      if (logResponse) {
        const dataLength = Array.isArray(data) ? data.length : 
                          typeof data === 'object' ? Object.keys(data).length : 
                          'unknown';
        console.log(`✅ API 응답 성공: ${url} (${dataLength}개 항목)`);
      }

      return {
        success: true,
        data,
        status: response.status
      };

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '알 수 없는 오류';
      console.error(`❌ API 요청 실패: ${url}`, errorMessage);
      
      return {
        success: false,
        error: errorMessage,
        status: error instanceof Error && error.name === 'AbortError' ? 408 : 500
      };
    }
  }

  /**
   * GET 요청 전용 메서드
   */
  async get<T = any>(endpoint: string, options: Omit<FetchOptions, 'method' | 'body'> = {}): Promise<ApiResponse<T>> {
    return this.fetch<T>(endpoint, { ...options, method: 'GET' });
  }

  /**
   * POST 요청 전용 메서드
   */
  async post<T = any>(endpoint: string, body?: any, options: Omit<FetchOptions, 'method' | 'body'> = {}): Promise<ApiResponse<T>> {
    const isFormData = body instanceof FormData;
    
    return this.fetch<T>(endpoint, {
      ...options,
      method: 'POST',
      body: isFormData ? body : JSON.stringify(body),
      headers: isFormData ? options.headers : {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });
  }

  /**
   * 파일 업로드 전용 메서드
   */
  async uploadFile<T = any>(endpoint: string, formData: FormData, options: FetchOptions = {}): Promise<ApiResponse<T>> {
    return this.post<T>(endpoint, formData, {
      ...options,
      cache: 'no-cache',
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        ...options.headers
      }
    });
  }

  /**
   * 배열 응답 전용 메서드 (자동 검증)
   */
  async getArray<T = any>(endpoint: string, options: FetchOptions = {}): Promise<ApiResponse<T[]>> {
    return this.get<T[]>(endpoint, { ...options, validateArray: true });
  }

  /**
   * 객체 응답 전용 메서드 (자동 검증)
   */
  async getObject<T = any>(endpoint: string, options: FetchOptions = {}): Promise<ApiResponse<T>> {
    return this.get<T>(endpoint, { ...options, validateObject: true });
  }
}

// 싱글톤 인스턴스 내보내기
export const apiClient = new ApiClient();
export default apiClient;
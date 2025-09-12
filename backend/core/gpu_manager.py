"""
GPU 관리 모듈 - GPU별 다른 모델 사용
GPU 0: large-v3 (고품질)
GPU 1: medium (빠른 처리)
"""
import torch
import threading
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class GPUManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.gpu_configs = {
                0: {'model_size': 'large-v3', 'min_memory': 8 * 1024**3},
                1: {'model_size': 'medium', 'min_memory': 4 * 1024**3}
            }
            self.gpu_usage = {0: 0, 1: 0}
            self.initialized = True
            logger.info("GPUManager 초기화: GPU0=large-v3, GPU1=medium")
    
    def get_gpu_for_quality(self, high_quality: bool = True) -> Tuple[int, str, str]:
        """품질 요구사항에 따른 GPU 선택"""
        if not torch.cuda.is_available():
            return -1, "cpu", "base"
        
        if high_quality:
            # GPU 0 우선
            try:
                free_mem = torch.cuda.mem_get_info(0)[0]
                if free_mem > self.gpu_configs[0]['min_memory']:
                    self.gpu_usage[0] += 1
                    return 0, "cuda:0", "large-v3"
            except:
                pass
            # GPU 1 폴백
            try:
                free_mem = torch.cuda.mem_get_info(1)[0]
                if free_mem > self.gpu_configs[1]['min_memory']:
                    self.gpu_usage[1] += 1
                    return 1, "cuda:1", "medium"
            except:
                pass
        else:
            # GPU 1 우선 (빠른 처리)
            try:
                free_mem = torch.cuda.mem_get_info(1)[0]
                if free_mem > self.gpu_configs[1]['min_memory']:
                    self.gpu_usage[1] += 1
                    return 1, "cuda:1", "medium"
            except:
                pass
        
        return -1, "cpu", "base"
    
    def get_stats(self) -> dict:
        """GPU 사용 통계"""
        stats = {}
        for gpu_id in [0, 1]:
            try:
                free = torch.cuda.mem_get_info(gpu_id)[0]
                stats[f"gpu_{gpu_id}"] = {
                    "model": self.gpu_configs[gpu_id]['model_size'],
                    "usage_count": self.gpu_usage[gpu_id],
                    "memory_free_gb": f"{free/1024**3:.1f}"
                }
            except:
                pass
        return stats

gpu_manager = GPUManager()

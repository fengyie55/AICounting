import cv2
import numpy as np
from typing import Tuple, Optional

class ImagePreprocessor:
    """图像预处理，支持光照自适应、运动模糊处理、去噪等"""
    
    def __init__(self, config_path="config/settings.yaml"):
        # 加载配置
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 预处理参数
        self.auto_brightness = True
        self.auto_contrast = True
        self.denoise_level = 3
        self.sharpen_level = 1
        self.deblur_enabled = True
        
        # 光照统计
        self.brightness_history = []
        self.max_history = 30
        
    def process(self, frame: np.ndarray) -> Tuple[np.ndarray, dict]:
        """
        预处理图像
        :param frame: 原始帧
        :return: 处理后的帧, 处理信息
        """
        info = {
            'original_brightness': 0,
            'adjusted_brightness': 0,
            'blur_level': 0,
            'enhanced': False
        }
        
        if frame is None:
            return frame, info
        
        # 计算原始亮度
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        original_brightness = gray.mean()
        info['original_brightness'] = original_brightness
        
        # 检测模糊程度
        blur_level = self._detect_blur(gray)
        info['blur_level'] = blur_level
        
        processed = frame.copy()
        
        # 光照自适应调整
        if self.auto_brightness or self.auto_contrast:
            processed = self._adjust_illumination(processed, original_brightness)
            info['enhanced'] = True
        
        # 去噪
        if self.denoise_level > 0:
            processed = cv2.fastNlMeansDenoisingColored(
                processed, None, self.denoise_level, self.denoise_level, 7, 21
            )
        
        # 锐化
        if self.sharpen_level > 0:
            processed = self._sharpen(processed, self.sharpen_level)
        
        # 运动模糊校正
        if self.deblur_enabled and blur_level > 100:
            processed = self._deblur_motion(processed)
            info['enhanced'] = True
        
        # 计算调整后亮度
        adjusted_gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
        info['adjusted_brightness'] = adjusted_gray.mean()
        
        return processed, info
    
    def _adjust_illumination(self, frame: np.ndarray, brightness: float) -> np.ndarray:
        """光照自适应调整"""
        self.brightness_history.append(brightness)
        if len(self.brightness_history) > self.max_history:
            self.brightness_history.pop(0)
        
        # 计算平均亮度
        avg_brightness = sum(self.brightness_history) / len(self.brightness_history)
        
        # 目标亮度范围：80-180
        target_brightness = 128
        alpha = 1.0
        beta = 0
        
        if avg_brightness < 50:  # 太暗
            alpha = 1.5
            beta = 30
        elif avg_brightness > 200:  # 太亮
            alpha = 0.8
            beta = -20
        
        # 调整亮度和对比度
        adjusted = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)
        
        # 直方图均衡化（局部自适应）
        if abs(avg_brightness - target_brightness) > 50:
            lab = cv2.cvtColor(adjusted, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl, a, b))
            adjusted = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        
        return adjusted
    
    def _detect_blur(self, gray: np.ndarray) -> float:
        """检测模糊程度（拉普拉斯方差）"""
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return laplacian.var()
    
    def _sharpen(self, frame: np.ndarray, level: int = 1) -> np.ndarray:
        """图像锐化"""
        if level == 1:
            kernel = np.array([[0, -1, 0],
                              [-1, 5, -1],
                              [0, -1, 0]])
        elif level == 2:
            kernel = np.array([[-1, -1, -1],
                              [-1, 9, -1],
                              [-1, -1, -1]])
        else:
            return frame
        
        return cv2.filter2D(frame, -1, kernel)
    
    def _deblur_motion(self, frame: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        """运动模糊校正"""
        # 创建运动模糊核
        kernel = np.zeros((kernel_size, kernel_size))
        kernel[int((kernel_size-1)/2), :] = np.ones(kernel_size)
        kernel = kernel / kernel_size
        
        # 维纳滤波去模糊
        psf = kernel
        dummy = np.copy(frame)
        for i in range(frame.shape[2]):
            dummy[:, :, i] = self._wiener_filter(frame[:, :, i], psf, 0.01)
        
        return dummy
    
    def _wiener_filter(self, img: np.ndarray, psf: np.ndarray, eps: float) -> np.ndarray:
        """维纳滤波实现"""
        # 傅里叶变换
        input_fft = np.fft.fft2(img)
        psf_fft = np.fft.fft2(psf, s=img.shape)
        
        # 计算共轭
        psf_fft_conj = np.conj(psf_fft)
        
        # 维纳滤波公式
        wiener_filter = psf_fft_conj / (np.abs(psf_fft) ** 2 + eps)
        result_fft = input_fft * wiener_filter
        
        # 逆傅里叶变换
        result = np.fft.ifft2(result_fft)
        result = np.abs(np.fft.fftshift(result))
        
        # 归一化
        result = (result - result.min()) / (result.max() - result.min()) * 255
        return result.astype(np.uint8)
    
    def remove_reflection(self, frame: np.ndarray) -> np.ndarray:
        """去除反光"""
        # 转换到HSV空间
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        
        # 检测高光区域
        _, mask = cv2.threshold(v, 220, 255, cv2.THRESH_BINARY)
        
        # 修复高光区域
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.dilate(mask, kernel, iterations=1)
        result = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
        
        return result
    
    def set_parameters(self, auto_brightness: bool = None, auto_contrast: bool = None,
                      denoise_level: int = None, sharpen_level: int = None,
                      deblur_enabled: bool = None):
        """设置预处理参数"""
        if auto_brightness is not None:
            self.auto_brightness = auto_brightness
        if auto_contrast is not None:
            self.auto_contrast = auto_contrast
        if denoise_level is not None:
            self.denoise_level = max(0, min(10, denoise_level))
        if sharpen_level is not None:
            self.sharpen_level = max(0, min(3, sharpen_level))
        if deblur_enabled is not None:
            self.deblur_enabled = deblur_enabled
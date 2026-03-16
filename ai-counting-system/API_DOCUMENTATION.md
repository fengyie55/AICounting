# AI视觉计数系统 MES API 接口文档

## 概述
本文档描述AI视觉计数系统提供的RESTful API接口，用于与MES系统对接。所有接口采用JSON格式进行数据交互。

## 基础信息
- **基础URL**: `http://<设备IP>:8000/api/v1`
- **认证方式**: 通过请求头 `X-API-Key` 进行身份验证，API密钥可在配置文件中设置
- **字符编码**: UTF-8
- **响应格式**: JSON

## 通用响应格式
```json
{
    "status": "success|error",
    "message": "响应消息",
    "data": {} // 响应数据，仅在success时存在
}
```

## 接口列表

### 1. 健康检查
**接口地址**: `GET /health`
**描述**: 检查API服务是否正常运行
**无需认证**

**响应示例**:
```json
{
    "status": "success",
    "message": "API server is running"
}
```

---

### 2. 获取系统状态
**接口地址**: `GET /status`
**描述**: 获取系统的完整运行状态

**响应示例**:
```json
{
    "status": "success",
    "data": {
        "timestamp": 1710000000000,
        "system": {
            "version": "2.0.0",
            "status": "running"
        },
        "count": {
            "total": 1234,
            "by_direction": {
                "up": 620,
                "down": 614
            },
            "by_line": [1234, 0, 0],
            "by_shift": {
                "0": 1234
            }
        },
        "count_rate": 60.5,
        "product": {
            "id": "prod_1234567890",
            "name": "产品A",
            "model": "YOLOv8n",
            "model_path": "models/product_a.pt",
            "specs": {
                "weight": "100g",
                "size": "10x10cm"
            }
        },
        "camera": {
            "connected": true,
            "current_fps": 30,
            "brightness": 128
        },
        "abnormal": {
            "no_material": false,
            "blocked": false,
            "low_count_rate": false
        }
    }
}
```

---

### 3. 获取计数统计
**接口地址**: `GET /counts`
**描述**: 获取多维度的计数统计数据

**查询参数**:
- `start_time`: 可选，开始时间戳（毫秒）
- `end_time`: 可选，结束时间戳（毫秒）
- `shift`: 可选，班次（0/1/2）
- `line_id`: 可选，计数线ID（0/1/2）
- `class_id`: 可选，类别ID
- `batch_id`: 可选，批次ID
- `product_id`: 可选，产品ID

**响应示例**:
```json
{
    "status": "success",
    "data": {
        "total": 1234,
        "up": 620,
        "down": 614,
        "by_class": {
            "0": {
                "name": "product_a",
                "count": 1234
            }
        }
    }
}
```

---

### 4. 获取计数记录
**接口地址**: `GET /records`
**描述**: 获取最近的计数记录

**查询参数**:
- `limit`: 可选，返回记录数量，默认100，最大1000
- `start_time`: 可选，开始时间戳（毫秒）
- `end_time`: 可选，结束时间戳（毫秒）

**响应示例**:
```json
{
    "status": "success",
    "data": [
        {
            "id": 1,
            "track_id": 1001,
            "direction": "up",
            "class_id": 0,
            "class_name": "product_a",
            "timestamp": 1710000000000,
            "datetime": "2024-03-15 10:00:00",
            "shift": 0,
            "line_id": 0,
            "batch_id": "batch_1234567890",
            "product_id": "prod_1234567890",
            "product_name": "产品A"
        }
    ]
}
```

---

### 5. 重置计数器
**接口地址**: `POST /reset`
**描述**: 重置计数器为0

**请求示例**:
```json
{}
```

**响应示例**:
```json
{
    "status": "success",
    "message": "Counter reset successfully"
}
```

---

### 6. 获取产品列表
**接口地址**: `GET /products`
**描述**: 获取所有产品列表

**响应示例**:
```json
{
    "status": "success",
    "data": [
        {
            "id": "prod_1234567890",
            "name": "产品A",
            "model": "YOLOv8n",
            "model_path": "models/product_a.pt",
            "specs": {
                "weight": "100g"
            },
            "create_time": 1710000000000,
            "update_time": 1710000000000,
            "is_active": true
        }
    ]
}
```

---

### 7. 获取当前产品
**接口地址**: `GET /products/current`
**描述**: 获取当前激活的产品信息

**响应示例**:
```json
{
    "status": "success",
    "data": {
        "id": "prod_1234567890",
        "name": "产品A",
        "model": "YOLOv8n",
        "model_path": "models/product_a.pt",
        "specs": {
            "weight": "100g"
        },
        "is_active": true
    }
}
```

---

### 8. 激活产品
**接口地址**: `POST /products/activate`
**描述**: 切换到指定产品，自动加载对应模型和配置

**请求参数**:
- `product_id`: 字符串，必填，产品ID

**请求示例**:
```json
{
    "product_id": "prod_1234567890"
}
```

**响应示例**:
```json
{
    "status": "success",
    "message": "Product activated successfully"
}
```

---

### 9. 获取系统配置
**接口地址**: `GET /config`
**描述**: 获取当前系统配置

**响应示例**:
```json
{
    "status": "success",
    "data": {
        "detection": {
            "conf_threshold": 0.5,
            "iou_threshold": 0.5
        },
        "tracker": {
            "track_thresh": 0.5
        },
        "counter": {
            "debounce_frames": 5
        }
    }
}
```

---

### 10. 更新系统配置
**接口地址**: `PUT /config`
**描述**: 更新系统配置参数

**请求参数**: 任意配置项，支持部分更新

**请求示例**:
```json
{
    "detection": {
        "conf_threshold": 0.6
    },
    "counter": {
        "debounce_frames": 3
    }
}
```

**响应示例**:
```json
{
    "status": "success",
    "message": "Config updated successfully"
}
```

---

### 11. 获取摄像头状态
**接口地址**: `GET /camera/status`
**描述**: 获取摄像头的运行状态

**响应示例**:
```json
{
    "status": "success",
    "data": {
        "connected": true,
        "current_fps": 30,
        "width": 1280,
        "height": 720,
        "brightness": 128
    }
}
```

---

### 12. 导出数据
**接口地址**: `GET /export`
**描述**: 导出计数数据到文件

**查询参数**:
- `format`: 可选，导出格式：excel/csv/pdf，默认excel
- `start_time`: 可选，开始时间戳（毫秒）
- `end_time`: 可选，结束时间戳（毫秒）
- `batch_id`: 可选，批次ID
- `product_id`: 可选，产品ID
- `shift`: 可选，班次

**响应示例**:
```json
{
    "status": "success",
    "message": "Export completed",
    "data": {
        "download_url": "/download/export_123456.xlsx"
    }
}
```

---

### 13. 获取系统日志
**接口地址**: `GET /logs`
**描述**: 获取系统操作日志和错误日志

**查询参数**:
- `type`: 可选，日志类型：operation/error，默认operation
- `limit`: 可选，返回记录数量，默认100

**响应示例**:
```json
{
    "status": "success",
    "data": [
        {
            "id": 1,
            "operator": "system",
            "action": "activate_product",
            "details": "{\"product_id\": \"prod_1234567890\"}",
            "timestamp": 1710000000000,
            "ip": null
        }
    ]
}
```

---

## 数据推送
系统支持主动推送计数数据和异常事件到MES系统，推送配置可在配置文件中设置。

### 推送地址
在配置文件中设置 `mes_api.push_url` 为MES系统接收数据的接口地址。

### 推送频率
默认每秒推送一次，可通过 `mes_api.push_interval` 配置。

### 推送数据格式
```json
{
    "timestamp": 1710000000000,
    "count": {
        "total": 1234,
        "by_direction": {
            "up": 620,
            "down": 614
        }
    },
    "count_rate": 60.5,
    "product": {
        "id": "prod_1234567890",
        "name": "产品A"
    },
    "abnormal": {
        "no_material": false,
        "blocked": false,
        "low_count_rate": false
    }
}
```

### 异常事件推送
当系统检测到异常时，会立即推送事件：
```json
{
    "type": "abnormal",
    "timestamp": 1710000000000,
    "data": {
        "abnormal_type": "no_material",
        "message": "检测到无物料",
        "level": "warning"
    }
}
```

---

## 错误码说明
| HTTP状态码 | 说明 |
|-----------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | API密钥错误或未提供 |
| 404 | 接口不存在 |
| 500 | 服务器内部错误 |

---

## 对接示例（Python）
```python
import requests

API_KEY = "your_api_key_here"
BASE_URL = "http://192.168.1.100:8000/api/v1"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# 获取系统状态
response = requests.get(f"{BASE_URL}/status", headers=headers)
status = response.json()
print("系统状态:", status)

# 重置计数器
response = requests.post(f"{BASE_URL}/reset", headers=headers, json={})
print("重置结果:", response.json())

# 切换产品
data = {"product_id": "prod_1234567890"}
response = requests.post(f"{BASE_URL}/products/activate", headers=headers, json=data)
print("切换产品结果:", response.json())
```

---

## 版本历史
- **v2.0.0**: 初始版本，提供完整的MES对接功能

# 云相册智能助手 API 接口文档

## 基础信息

- **服务地址**: `http://127.0.0.1:8024`
- **接口前缀**: `/api`
- **数据格式**: JSON
- **字符编码**: UTF-8

---

## 通用说明

### 响应格式

所有接口统一返回以下 JSON 格式：

```json
{
  "code": 200,
  "msg": "操作成功",
  "data": {}
}
```

**字段说明：**
- `code`: 状态码，`200` 表示成功，其他值表示失败
- `msg`: 响应消息描述
- `data`: 业务数据（可选，根据接口不同而变化）

### 错误处理

当请求失败时，HTTP 状态码将为 `500`，响应示例：

```json
{
  "detail": "错误描述信息"
}
```

---

## 接口列表

### 1. 创建会话

**接口说明**: 创建全新的对话会话，生成唯一的会话ID

- **请求方式**: `GET`
- **请求路径**: `/api/create-thread`
- **是否需要认证**: 否

#### 响应示例

```json
{
  "code": 200,
  "thread_id": "c285e95f-2f80-4327-9be7-063784a640ed",
  "msg": "会话创建成功"
}
```

**字段说明：**
- `thread_id`: 会话唯一标识符（UUID格式），后续所有对话都需要携带此ID

#### 前端使用建议

在用户首次打开聊天页面时调用此接口，获取 `thread_id` 并保存到本地存储（如 localStorage），后续所有对话都使用同一个 `thread_id`。

---

### 2. 校验会话

**接口说明**: 检查指定会话是否存在于系统中

- **请求方式**: `GET`
- **请求路径**: `/api/check-thread/{thread_id}`
- **是否需要认证**: 否

#### 路径参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| thread_id | string | 是 | 会话ID |

#### 响应示例

```json
{
  "code": 200,
  "thread_id": "c285e95f-2f80-4327-9be7-063784a640ed",
  "exist": true,
  "msg": "会话存在"
}
```

**字段说明：**
- `exist`: `true` 表示会话存在，`false` 表示会话不存在

#### 前端使用建议

在页面加载时，如果本地有保存的 `thread_id`，可以先调用此接口校验会话是否有效。如果会话不存在，需要重新调用"创建会话"接口。

---

### 3. 发送消息（对话交互）

**接口说明**: 向AI助手发送消息，支持纯文本、图文混合输入和**智能上传确认**

- **请求方式**: `POST`
- **请求路径**: `/api/chat`
- **Content-Type**: `application/json`
- **是否需要认证**: 否

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| thread_id | string | 是 | 会话ID |
| query | string | 是 | 用户输入的文本内容（第二次请求可为空字符串） |
| image_url | string | 否 | 图片URL地址（在线图片或COS上传后的访问地址） |
| user_id | integer | 否 | 用户ID（图片上传时使用） |
| space_id | integer | 否 | 相册ID（null表示公共图库，数字表示个人相册ID） |
| user_confirmed | boolean | 否 | HITL用户确认标志（true=确认上传，false=取消） |
| modified_data | object | 否 | 用户修改后的数据（仅在user_confirmed=true时使用） |

#### 请求示例

**场景1：纯文本对话**
```json
{
  "thread_id": "c285e95f-2f80-4327-9be7-063784a640ed",
  "query": "你好"
}
```

**场景2：图文检索（在线图片）**
```json
{
  "thread_id": "c285e95f-2f80-4327-9be7-063784a640ed",
  "query": "找相似的图片",
  "image_url": "https://example.com/photo.jpg"
}
```

**场景3：图片分析（本地上传后）**
```json
{
  "thread_id": "c285e95f-2f80-4327-9be7-063784a640ed",
  "query": "这是什么动漫角色？",
  "image_url": "https://your-bucket.cos.ap-guangzhou.myqcloud.com/uploads/anime.jpg"
}
```

**场景4：智能上传 - 第一次请求（触发AI分析 + HITL中断）**
```json
{
  "thread_id": "upload-1234567890",
  "query": "这个女孩叫安和昴，请帮我上传到公共图库",
  "image_url": "https://your-bucket.cos.ap-guangzhou.myqcloud.com/temp/photo.jpg",
  "user_id": 1,
  "space_id": null
}
```

**场景5：智能上传 - 第二次请求（用户确认后继续）**
```json
{
  "thread_id": "upload-1234567890",
  "query": "",
  "user_confirmed": true,
  "modified_data": null
}
```

**场景6：智能上传 - 修改后确认**
```json
{
  "thread_id": "upload-1234567890",
  "query": "",
  "user_confirmed": true,
  "modified_data": {
    "name": "自定义名称",
    "introduction": "自定义简介（50-500字）",
    "category": "自定义分类",
    "tags": ["标签1", "标签2", "标签3"],
    "space_id": 100
  }
}
```

**场景7：智能上传 - 取消上传**
```json
{
  "thread_id": "upload-1234567890",
  "query": "",
  "user_confirmed": false
}
```

#### 响应示例

```json
{
  "code": 200,
  "thread_id": "c285e95f-2f80-4327-9be7-063784a640ed",
  "query": "这是什么动漫角色？",
  "reply": "这是《Re:从零开始的异世界生活》中的角色雷姆，她是罗兹瓦尔宅邸的女仆，性格温柔善良...",
  "msg": "success"
}
```

**字段说明：**
- `reply`: AI助手的回复文本内容

#### 功能说明

系统会根据输入自动识别意图并路由到不同的处理链路：

1. **闲聊模式**: 无图片且无检索意图 → 直接对话
2. **图文检索**: 有图片 + 检索意图 → 返回相似图片
3. **图片分析**: 有图片 + 分析意图 → 识别图片内容（动漫角色/景点等）
4. **文本检索**: 无图片 + 检索意图 → 关键词搜图

#### 前端使用建议

1. **纯文本对话**: 只传 `thread_id` 和 `query`
2. **带图片对话**: 
   - 如果是网络图片，直接使用图片URL
   - 如果是本地图片，先调用"获取COS预签名URL"接口上传图片，拿到 `accessUrl` 后再调用此接口

---

### 4. 删除会话

**接口说明**: 删除指定会话的所有历史数据

- **请求方式**: `DELETE`
- **请求路径**: `/api/delete-thread/{thread_id}`
- **是否需要认证**: 否

#### 路径参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| thread_id | string | 是 | 会话ID |

#### 响应示例

```json
{
  "code": 200,
  "thread_id": "c285e95f-2f80-4327-9be7-063784a640ed",
  "msg": "会话删除成功"
}
```

#### 前端使用建议

提供"清除聊天记录"或"新建对话"功能时调用此接口。删除后如需继续对话，需要重新调用"创建会话"接口获取新的 `thread_id`。

---

### 5. 获取COS预签名上传URL

**接口说明**: 获取腾讯云COS对象存储的预签名上传URL，用于前端直接上传本地图片

- **请求方式**: `GET`
- **请求路径**: `/api/cos/presign`
- **是否需要认证**: 否

#### 查询参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| filename | string | 是 | 文件名（包含扩展名，如 `photo.jpg`） |

#### 请求示例

```
GET /api/cos/presign?filename=anime_20240101.jpg
```

#### 响应示例

```json
{
  "uploadUrl": "https://your-bucket.cos.ap-guangzhou.myqcloud.com/anime_20240101.jpg?sign=xxx&expires=xxx",
  "contentType": "image/jpeg",
  "accessUrl": "https://your-bucket.cos.ap-guangzhou.myqcloud.com/anime_20240101.jpg"
}
```

**字段说明：**
- `uploadUrl`: 预签名上传URL（有效期1小时），前端使用 PUT 方法上传文件到此地址
- `contentType`: 文件的MIME类型，上传时需要设置 `Content-Type` 请求头
- `accessUrl`: 上传完成后可公开访问的图片URL，用于发送给对话接口

#### 支持的文件类型

| 扩展名 | Content-Type |
|--------|--------------|
| .jpg / .jpeg | image/jpeg |
| .png | image/png |
| .gif | image/gif |
| .webp | image/webp |

#### 前端上传流程

```javascript
// 步骤1：获取预签名URL
const response = await fetch('/api/cos/presign?filename=photo.jpg');
const { uploadUrl, contentType, accessUrl } = await response.json();

// 步骤2：使用 PUT 方法上传文件到COS
await fetch(uploadUrl, {
  method: 'PUT',
  headers: {
    'Content-Type': contentType
  },
  body: file // File 对象
});

// 步骤3：上传成功后，使用 accessUrl 调用对话接口
const chatResponse = await fetch('/api/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    thread_id: 'your-thread-id',
    query: '这是什么角色？',
    image_url: accessUrl // 使用COS返回的访问URL
  })
});
```

#### 注意事项

1. **URL有效期**: `uploadUrl` 有效期为 1 小时（3600秒），超时后需要重新获取
2. **文件大小限制**: 建议单张图片不超过 10MB
3. **文件名建议**: 使用时间戳或UUID生成唯一文件名，避免覆盖
4. **CORS配置**: COS Bucket需要配置允许跨域访问，确保前端可以直接PUT上传

---

## 完整业务流程示例

### 场景1：纯文本闲聊

```javascript
// 1. 创建会话（首次使用时）
const threadRes = await fetch('/api/create-thread');
const { thread_id } = await threadRes.json();

// 2. 发送消息
const chatRes = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    thread_id: thread_id,
    query: '你好'
  })
});
const { reply } = await chatRes.json();
console.log('AI回复:', reply);
```

### 场景2：本地图片上传 + 图片分析

```javascript
// 1. 用户选择本地图片
const fileInput = document.getElementById('fileInput');
const file = fileInput.files[0];

// 2. 生成唯一文件名
const filename = `upload_${Date.now()}_${file.name}`;

// 3. 获取COS预签名URL
const presignRes = await fetch(`/api/cos/presign?filename=${filename}`);
const { uploadUrl, contentType, accessUrl } = await presignRes.json();

// 4. 上传文件到COS
await fetch(uploadUrl, {
  method: 'PUT',
  headers: { 'Content-Type': contentType },
  body: file
});

// 5. 调用对话接口进行图片分析
const chatRes = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    thread_id: thread_id,
    query: '这是什么动漫角色？',
    image_url: accessUrl
  })
});
const { reply } = await chatRes.json();
console.log('AI回复:', reply);
```

### 场景3：在线图片检索

```javascript
// 直接使用网络图片URL
const chatRes = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    thread_id: thread_id,
    query: '找相似的图片',
    image_url: 'https://example.com/photo.jpg'
  })
});
const { reply } = await chatRes.json();
```

---

## 常见问题

### Q1: 如何保持多轮对话的上下文？

**A**: 所有对话都使用同一个 `thread_id`，系统会自动从Redis加载历史上下文。只需在首次创建会话时获取 `thread_id`，后续所有请求都携带此ID即可。

### Q2: 图片上传失败怎么办？

**A**: 可能的原因：
1. `uploadUrl` 已过期（超过1小时），需要重新获取
2. 文件格式不支持，仅支持 jpg/png/gif/webp
3. COS Bucket CORS配置不正确，需联系后端检查
4. 网络连接问题，检查浏览器控制台错误信息

### Q3: 如何清除对话历史？

**A**: 调用"删除会话"接口删除当前会话，然后重新调用"创建会话"接口获取新的 `thread_id`。

### Q4: 支持哪些图片分析类型？

**A**: 目前支持：
- 动漫角色识别
- 风景景点识别（开发中）
- 通用图片内容分析（开发中）

系统会自动识别图片类型并选择合适的分析模型。

---

## 技术栈说明

- **后端框架**: FastAPI
- **AI编排**: LangGraph
- **向量数据库**: ChromaDB
- **会话存储**: Redis
- **对象存储**: 腾讯云COS
- **AI模型**: DeepSeek（文本）、DashScope Qwen3-VL（多模态）

---

## 更新日志

### v1.0.0 (2024-01-01)
- ✅ 实现基础会话管理（创建/校验/删除）
- ✅ 实现多模态对话接口（支持图文混合输入）
- ✅ 实现COS图片上传功能
- ✅ 支持图文检索、图片分析、闲聊三种模式

---

## 联系方式

如有接口问题或需求变更，请联系后端开发团队。

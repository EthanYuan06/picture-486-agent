/**
 * SSE流式对话前端示例代码
 * 
 * 使用方法：
 * 1. 在浏览器控制台运行此代码
 * 2. 或者集成到你的前端项目中
 */

// ========== 配置 ==========
const API_BASE = 'http://127.0.0.1:8024/api';
let currentThreadId = null;

// ========== 创建会话 ==========
async function createThread() {
    const response = await fetch(`${API_BASE}/create-thread`);
    const result = await response.json();
    currentThreadId = result.data.thread_id;
    console.log('✅ 创建会话成功:', currentThreadId);
    return currentThreadId;
}

// ========== SSE流式对话 ==========
async function sendChatStream(query, imageUrl = null) {
    if (!currentThreadId) {
        await createThread();
    }

    console.log('📤 发送消息:', query);
    
    const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            thread_id: currentThreadId,
            query: query,
            image_url: imageUrl,
            user_id: 1,  // 示例用户ID
            space_id: null  // null表示公共图库
        })
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let accumulatedText = '';

    console.log('📥 开始接收SSE流...');

    while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
            console.log('✅ SSE连接关闭');
            break;
        }

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                try {
                    const data = JSON.parse(line.slice(6));
                    handleSSEEvent(data, accumulatedText);
                    
                    if (data.type === 'message') {
                        accumulatedText += data.data.content;
                    }
                } catch (e) {
                    console.error('解析SSE数据失败:', e, line);
                }
            }
        }
    }

    return accumulatedText;
}

// ========== 处理SSE事件 ==========
function handleSSEEvent(event, currentText) {
    switch (event.type) {
        case 'message':
            // 打字机效果：逐字显示
            process.stdout?.write?.(event.data.content) || 
            console.log('💬 [打字机]:', event.data.content);
            break;

        case 'images':
            console.log('🖼️ 收到图片URL列表:', event.data.urls);
            break;

        case 'interrupt':
            // HITL中断：需要用户确认
            console.log('⚠️ 检测到HITL中断，等待用户确认');
            console.log('待确认数据:', event.data);
            
            // 这里可以弹出确认对话框
            showHitlConfirmDialog(event.data);
            break;

        case 'done':
            console.log('✅ 对话完成');
            break;

        case 'error':
            console.error('❌ 错误:', event.data.error);
            break;

        default:
            console.log('未知事件类型:', event.type, event.data);
    }
}

// ========== HITL确认对话框（示例）==========
function showHitlConfirmDialog(confirmData) {
    console.log('\n========== 上传确认 ==========');
    console.log('名称:', confirmData.name);
    console.log('简介:', confirmData.introduction);
    console.log('分类:', confirmData.category);
    console.log('标签:', confirmData.tags);
    console.log('==============================\n');
    
    // 实际项目中，这里应该显示模态框让用户确认
    // 用户确认后调用 resumeChatStream
}

// ========== HITL恢复执行（使用同一接口）==========
async function resumeChatStream(userConfirmed, modifiedData = null) {
    if (!currentThreadId) {
        throw new Error('没有活跃的会话');
    }

    console.log('📤 恢复执行，用户确认:', userConfirmed);
    
    // 🔥 关键：使用同一个接口，LangGraph自动从checkpoint恢复
    const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            thread_id: currentThreadId,
            query: '',  // 恢复时不需要query
            user_confirmed: userConfirmed,
            modified_data: modifiedData
        })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let accumulatedText = '';

    while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
            console.log('✅ 恢复执行完成');
            break;
        }

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                try {
                    const data = JSON.parse(line.slice(6));
                    handleSSEEvent(data, accumulatedText);
                    
                    if (data.type === 'message') {
                        accumulatedText += data.data.content;
                    }
                } catch (e) {
                    console.error('解析SSE数据失败:', e, line);
                }
            }
        }
    }

    return accumulatedText;
}

// ========== 测试用例 ==========

// 测试1：纯文本对话
async function testTextChat() {
    console.log('\n===== 测试1：纯文本对话 =====');
    await createThread();
    await sendChatStream('你好，请介绍一下自己');
}

// 测试2：图文对话
async function testImageChat() {
    console.log('\n===== 测试2：图文对话 =====');
    await createThread();
    await sendChatStream(
        '这张图片是什么内容？',
        'https://example.com/image.jpg'  // 替换为真实图片URL
    );
}

// 测试3：图片上传（触发HITL）
async function testImageUpload() {
    console.log('\n===== 测试3：图片上传（HITL）=====');
    await createThread();
    
    // 第一次请求：触发中断
    const text = await sendChatStream(
        '上传到公共图库',
        'https://example.com/upload.jpg'  // 替换为真实图片URL
    );
    
    console.log('等待用户确认...');
    
    // 模拟用户确认（实际项目中由用户点击按钮触发）
    setTimeout(async () => {
        console.log('用户确认上传');
        await resumeChatStream(true, null);  // true表示确认，null表示不修改数据
    }, 3000);
}

// ========== 导出函数（供外部调用）==========
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        createThread,
        sendChatStream,
        resumeChatStream,
        testTextChat,
        testImageChat,
        testImageUpload
    };
}

// 如果在浏览器环境中，挂载到window
if (typeof window !== 'undefined') {
    window.SSEChat = {
        createThread,
        sendChatStream,
        resumeChatStream,
        testTextChat,
        testImageChat,
        testImageUpload
    };
}

console.log('✅ SSE流式对话示例代码已加载');
console.log('可用函数: createThread(), sendChatStream(), resumeChatStream()');
console.log('测试函数: testTextChat(), testImageChat(), testImageUpload()');

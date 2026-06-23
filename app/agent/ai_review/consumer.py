"""
AI图片审核 - RabbitMQ消费者
集成到FastAPI应用作为后台任务运行
"""
import asyncio
import json
import threading
from typing import Optional

import pika

from app.agent.ai_review.config import AIReviewConfig
from app.agent.ai_review.workflow import execute_ai_review
from app.agent.ai_review.callback import callback_backend
from app.common.logger import logger


# 全局单例: MQ连接和通道
_mq_connection: Optional[pika.BlockingConnection] = None
_mq_channel: Optional[pika.channel.Channel] = None
_consumer_thread: Optional[threading.Thread] = None
_stop_event: Optional[threading.Event] = None


def _get_mq_connection() -> pika.BlockingConnection:
    """获取MQ连接(单例模式)"""
    global _mq_connection
    
    if _mq_connection is None or _mq_connection.is_closed:
        try:
            credentials = pika.PlainCredentials(
                AIReviewConfig.RABBITMQ_USER,
                AIReviewConfig.RABBITMQ_PASSWORD
            )
            parameters = pika.ConnectionParameters(
                host=AIReviewConfig.RABBITMQ_HOST,
                port=AIReviewConfig.RABBITMQ_PORT,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            _mq_connection = pika.BlockingConnection(parameters)
            logger.info("[MQ消费者] RabbitMQ连接成功")
        except Exception as e:
            logger.error(f"[MQ消费者] RabbitMQ连接失败: {str(e)}", exc_info=True)
            raise
    
    return _mq_connection


def _get_mq_channel() -> pika.channel.Channel:
    """获取MQ通道(单例模式)"""
    global _mq_channel
    
    if _mq_channel is None or _mq_channel.is_closed:
        connection = _get_mq_connection()
        _mq_channel = connection.channel()
        
        # 声明队列(确保队列存在)
        _mq_channel.queue_declare(
            queue=AIReviewConfig.QUEUE_NAME,
            durable=True,  # 持久化
            arguments={
                'x-dead-letter-exchange': 'dlx-exchange',
                'x-dead-letter-routing-key': 'ai.review.dlx',
                'x-message-ttl': 30000  # 30秒超时进死信
            }
        )
        
        # 设置预取计数(每次只处理1条消息)
        _mq_channel.basic_qos(prefetch_count=1)
        
        logger.info(f"[MQ消费者] 队列声明成功: {AIReviewConfig.QUEUE_NAME}")
    
    return _mq_channel


def process_message(ch: pika.channel.Channel, method: pika.spec.Basic.Deliver, 
                   properties: pika.spec.BasicProperties, body: bytes):
    """
    处理MQ消息(手动ACK模式)
    
    Args:
        ch: Channel对象
        method: 方法对象(包含delivery_tag)
        properties: 消息属性
        body: 消息体(JSON字符串)
    """
    delivery_tag = method.delivery_tag
    picture_id = None
    
    try:
        # 1. 解析消息
        message = json.loads(body)
        picture_id = message.get("pictureId")
        user_id = message.get("userId")
        image_url = message.get("url")
        
        logger.info(f"[MQ消费者] 收到AI审核请求 - picture_id: {picture_id}, user_id: {user_id}")
        
        # 2. 构建初始状态
        initial_state = {
            "picture_id": picture_id,
            "user_id": user_id,
            "image_url": image_url
        }
        
        # 3. 执行AI审核工作流
        final_state = execute_ai_review(initial_state)
        
        # 4. 回调后端接口
        success = callback_backend(final_state)
        
        if success:
            # ✅ 成功: 手动ACK
            ch.basic_ack(delivery_tag=delivery_tag)
            logger.info(f"[MQ消费者] AI审核完成并回调成功 - picture_id: {picture_id}")
        else:
            # ❌ 回调失败: 重新入队
            ch.basic_nack(delivery_tag=delivery_tag, requeue=True)
            logger.warning(f"[MQ消费者] 回调失败,消息重新入队 - picture_id: {picture_id}")
    
    except json.JSONDecodeError as e:
        logger.error(f"[MQ消费者] 消息格式错误: {str(e)}, body: {body[:200]}")
        # 格式错误: 拒绝消息(不重新入队)
        ch.basic_nack(delivery_tag=delivery_tag, requeue=False)
    
    except Exception as e:
        logger.error(f"[MQ消费者] AI审核异常 - picture_id: {picture_id}, error: {str(e)}", exc_info=True)
        # 异常: 重新入队
        ch.basic_nack(delivery_tag=delivery_tag, requeue=True)


async def start_ai_review_consumer():
    """
    启动MQ消费者(在线程中运行,不阻塞事件循环)
    
    在FastAPI lifespan中调用此函数:
    asyncio.create_task(start_ai_review_consumer())
    """
    global _consumer_thread, _stop_event
    
    logger.info("[MQ消费者] 准备启动AI审核消费者...")
    
    # 等待一小段时间,确保应用完全启动
    await asyncio.sleep(2)
    
    def run_consumer():
        """在线程中运行阻塞的消费者"""
        try:
            logger.info("[MQ消费者] 线程启动,尝试连接RabbitMQ...")
            
            # 获取MQ通道
            channel = _get_mq_channel()
            
            # 开始消费(手动ACK)
            channel.basic_consume(
                queue=AIReviewConfig.QUEUE_NAME,
                on_message_callback=process_message,
                auto_ack=False  # ⚠️ 手动ACK
            )
            
            logger.info(f"[MQ消费者] AI审核消费者已启动,监听队列: {AIReviewConfig.QUEUE_NAME}")
            
            # 进入消费循环(阻塞,但在独立线程中)
            while not _stop_event.is_set():
                try:
                    channel.connection.process_data_events(time_limit=1)
                except Exception as e:
                    logger.error(f"[MQ消费者] 消费异常: {str(e)}", exc_info=True)
                    break
            
            logger.info("[MQ消费者] 消费者线程退出")
            
        except Exception as e:
            logger.error(f"[MQ消费者] 消费者线程异常: {str(e)}", exc_info=True)
    
    # 创建停止事件
    _stop_event = threading.Event()
    
    # 在后台线程中运行
    _consumer_thread = threading.Thread(target=run_consumer, daemon=True, name="mq-consumer")
    _consumer_thread.start()
    logger.info("[MQ消费者] 消费者线程已启动")
    
    # 保持异步任务运行,定期检查线程状态
    while True:
        await asyncio.sleep(60)
        if _consumer_thread and not _consumer_thread.is_alive():
            logger.warning("[MQ消费者] 消费者线程意外退出,尝试重启...")
            _stop_event.clear()
            _consumer_thread = threading.Thread(target=run_consumer, daemon=True, name="mq-consumer")
            _consumer_thread.start()


def stop_ai_review_consumer():
    """停止MQ消费者(应用关闭时调用)"""
    global _mq_channel, _mq_connection, _consumer_thread, _stop_event
    
    try:
        # 设置停止信号
        if _stop_event:
            _stop_event.set()
            logger.info("[MQ消费者] 已发送停止信号")
        
        # 等待线程退出(最多等待5秒)
        if _consumer_thread and _consumer_thread.is_alive():
            _consumer_thread.join(timeout=5)
            if _consumer_thread.is_alive():
                logger.warning("[MQ消费者] 消费者线程未在规定时间内退出")
            else:
                logger.info("[MQ消费者] 消费者线程已退出")
        
        # 关闭通道和连接
        if _mq_channel and not _mq_channel.is_closed:
            try:
                _mq_channel.stop_consuming()
                _mq_channel.close()
                logger.info("[MQ消费者] 通道已关闭")
            except Exception as e:
                logger.warning(f"[MQ消费者] 关闭通道异常: {str(e)}")
        
        if _mq_connection and not _mq_connection.is_closed:
            try:
                _mq_connection.close()
                logger.info("[MQ消费者] 连接已关闭")
            except Exception as e:
                logger.warning(f"[MQ消费者] 关闭连接异常: {str(e)}")
    
    except Exception as e:
        logger.error(f"[MQ消费者] 关闭异常: {str(e)}", exc_info=True)
    
    finally:
        _mq_channel = None
        _mq_connection = None
        _consumer_thread = None
        _stop_event = None

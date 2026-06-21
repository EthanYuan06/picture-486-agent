import logging
import os
import sys

# 加载环境变量
from dotenv import load_dotenv
from fastapi import APIRouter
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from app.utils.api_utils import success_response

load_dotenv()
router = APIRouter()

# 设置日志级别
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 从环境变量中加载凭证信息
secret_id = os.environ.get('COS_SECRET_ID')
secret_key = os.environ.get('COS_SECRET_KEY')
region = os.environ.get('COS_REGION')
token = None
scheme = 'https'

# 创建COS配置和客户端
config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme=scheme)
client = CosS3Client(config)

# COS Bucket配置 (Bucket由 BucketName-Appid 组成)
COS_BUCKET = os.getenv("COS_BUCKET")

# 前端上传图片后，发送消息时同步上传到COS，获取URL发送给大模型
@router.get("/cos/presign")
def get_presign_upload_url(filename: str):
    # 根据文件扩展名判断 Content-Type
    content_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    ext = filename.split(".")[-1].lower() if "." in filename else "jpg"
    content_type = content_type_map.get(ext, "application/octet-stream")

    # 生成预签名URL，上传到temp目录
    response = client.get_presigned_url(
        Method='PUT',
        Bucket=COS_BUCKET,
        Key=f'temp/{filename}',  # 上传到temp目录
        Expired=3600,  # 过期时间（秒）
        Headers={'Content-Type': content_type}
    )

    # 返回上传 URL 和可访问的图片路径
    return success_response(
        data={
            "uploadUrl": response,
            "contentType": content_type,
            "accessUrl": f"https://{COS_BUCKET}.cos.{region}.myqcloud.com/temp/{filename}"
        }
    )

"""
检查 ChromaDB 数据库内容
用于诊断为什么检索返回 0 个文档
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.agent.config.chroma_config import chroma_vector_store
from app.common.logger import logger

def check_chroma_data():
    """检查 ChromaDB 中的数据"""
    
    logger.info("=" * 80)
    logger.info("开始检查 ChromaDB 数据")
    logger.info("=" * 80)
    
    try:
        # 1. 检查集合是否存在
        collection = chroma_vector_store._collection
        logger.info(f"✓ 集合名称: {collection.name}")
        
        # 2. 检查总文档数
        count = collection.count()
        logger.info(f"✓ 总文档数: {count}")
        
        if count == 0:
            logger.error(" 数据库为空！没有插入任何图片数据")
            logger.info("\n可能的原因：")
            logger.info("  1. 图片上传功能未执行，数据库中无数据")
            logger.info("  2. 使用了错误的 persist_directory 路径")
            logger.info("  3. 数据插入失败但未报错")
            return
        
        # 3. 抽样查看前 5 条数据
        logger.info(f"\n抽样查看前 5 条数据:")
        sample = collection.get(limit=5, include=['metadatas', 'documents'])
        
        for i in range(len(sample['ids'])):
            doc_id = sample['ids'][i]
            metadata = sample['metadatas'][i]
            document = sample['documents'][i]
            
            logger.info(f"\n[{i+1}] ID: {doc_id}")
            logger.info(f"    名称: {metadata.get('name', 'N/A')}")
            logger.info(f"    简介: {metadata.get('introduction', 'N/A')[:50]}...")
            logger.info(f"    图片URL: {metadata.get('image_url', 'N/A')}")
            logger.info(f"    分类: {metadata.get('category', 'N/A')}")
            logger.info(f"    Document: {document[:100]}...")
        
        # 4. 测试简单查询
        logger.info(f"\n" + "=" * 80)
        logger.info("测试简单查询")
        logger.info("=" * 80)
        
        test_queries = ["安和", "猫", "女孩"]
        for query in test_queries:
            logger.info(f"\n查询关键词: '{query}'")
            results = collection.query(
                query_texts=[query],
                n_results=3,
                include=['metadatas', 'distances']
            )
            
            if len(results['ids'][0]) == 0:
                logger.warning(f"  ✗ 未找到任何结果")
            else:
                logger.info(f"  ✓ 找到 {len(results['ids'][0])} 个结果")
                for j in range(len(results['ids'][0])):
                    name = results['metadatas'][0][j].get('name', 'N/A')
                    distance = results['distances'][0][j]
                    similarity = 1.0 / (1.0 + distance)
                    logger.info(f"    [{j+1}] {name}: 距离={distance:.4f}, 相似度={similarity:.4f}")
        
        # 5. 检查是否有特定的图片
        logger.info(f"\n" + "=" * 80)
        logger.info("检查特定图片是否存在")
        logger.info("=" * 80)
        
        # 尝试通过元数据过滤查找
        all_data = collection.get(include=['metadatas'])
        names = [m.get('name', '') for m in all_data['metadatas']]
        
        target_names = ["安和猫", "安和_猫", "cat", "girl"]
        for target in target_names:
            matches = [n for n in names if target.lower() in n.lower()]
            if matches:
                logger.info(f"✓ 找到包含 '{target}' 的图片: {matches}")
            else:
                logger.warning(f"✗ 未找到包含 '{target}' 的图片")
        
    except Exception as e:
        logger.error(f"✗ 检查失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    logger.info("\n" + "=" * 80)
    logger.info("检查完成")
    logger.info("=" * 80)


if __name__ == "__main__":
    check_chroma_data()

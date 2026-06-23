#### 业务模块的标准结构：

```
app/agent/{business_name}/
├─ __init__.py          # 【必存】唯一顶层导出入口，对外输出State、build_subgraph、业务常量（导出≥3个对象）
├─ state.py             # 当前业务专属Graph状态定义
├─ graph.py             # 封装build_subgraph()，内部节点组装、私有路由、子图编译
├─ config.py            # 业务私有LLM参数、循环阈值、工具配置
├─ prompts/             # 存放业务专属提示词模板、Few-shot
│  └─ __init__.py       # 仅当需要批量导出Prompt常量时创建；仅1个prompt文件则删掉此init
├─ tools/               # 业务私有自定义工具
│  └─ __init__.py       # 仅当对外暴露多个工具函数/类时创建；单工具文件直接删除init
└─ nodes/               # 业务所有执行节点
   └─ __init__.py       # 仅graph.py需要批量导入节点时创建；节点≤2个直接删除此init
```

#### `__init__.py` 生成规则

1. **多文件关联**：子目录下 ≥3 个业务文件
2. **代码复杂度**：模块总代码 ≥200 行
4. **统一导出**：对外导出 ≥3 个类/常量/函数


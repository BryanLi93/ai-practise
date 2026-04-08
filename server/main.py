# 题目：构建一个 "AI Model Registry" 的 API，管理 AI 模型的注册信息。
# 要求：

# GET /models — 获取所有模型列表，支持 skip 和 limit 查询参数
# GET /models/{model_id} — 获取单个模型详情，model_id 为 int
# POST /models — 注册新模型（用 Pydantic BaseModel 定义 request body，至少包含 name: str, provider: str, version: str）
# PUT /models/{model_id} — 更新模型信息
# DELETE /models/{model_id} — 删除模型，返回 204

# 附加要求：

# 用一个 list[dict] 做内存存储（不需要数据库）
# 当 model_id 不存在时，返回 404（提示：from fastapi import HTTPException，抛出 HTTPException(status_code=404, detail="Model not found")）
# 给每个端点加上合适的 status_code
# 完成后访问 /docs 截图，体验自动文档

# Bonus：

# 加一个 GET /models/search，支持按 provider 查询参数筛选
# 注意：这个路由要放在 GET /models/{model_id} 前面，否则 "search" 会被当成 model_id 参数（和 Express 一样的路由匹配顺序问题）

from fastapi import FastAPI, status, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Literal, get_args

app = FastAPI()

Provider = Literal["OpenAI", "Anthropic", "Google", "Alibaba", "DeepSeek", "Meta"]
provider_list = list(get_args(Provider))

class PricingTier(BaseModel):
    input_per_1m: float
    output_per_1m: float
class ModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d{4}-\d{2}(-\d{2})?$")
    pricing_tier: PricingTier | None = None
    
    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in provider_list:
            raise ValueError(f"provider 必须是 {provider_list} 之一")
        return v

class ModelUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    provider: str | None = Field(None, min_length=1)
    version: str | None = Field(None, pattern=r"^\d{4}-\d{2}(-\d{2})?$")
    pricing_tier: PricingTier | None = None
class ModelResponse(ModelCreate):
    id: int
class IdGenerator():
    def __init__(self) -> None:
        self.id = 0

    def get_new_id(self):
        self.id += 1
        return self.id
class Models():
    models = []
    def __init__(self, items: list[ModelResponse] | None) -> None:
        self.models = items or []
    def get_models(self):
        return self.models
    def get_model(self, id: int):
        return next((m for m in self.models if m.id == id), None)
    def append(self, model: ModelCreate):
        new_mode = ModelResponse(
            id=id_generator.get_new_id(),
            **model.model_dump()
        )
        self.models.append(new_mode)
        return new_mode
    def update(self, id: int, model_info: ModelUpdate | ModelCreate):
        result = next(((i, m) for i, m in enumerate(self.models) if m.id == id), (-1, None))
        index, model = result
        if not model:
            raise ValueError("未找到数据")
        self.models[index] = model.model_copy(update=model_info.model_dump(exclude_unset=True))
        return self.models[index]
    def delete(self, id: int):
        original_len = len(self.models)
        models = [m for m in self.models if not m.id == id]
        if len(models) == original_len:
            raise ValueError("未找到数据")
        self.models = models        
    def __len__(self):
        return len(self.models)

id_generator = IdGenerator()
models = Models([
    ModelResponse(id=id_generator.get_new_id(), name="GPT-4o", provider="OpenAI", version="2024-08-06"),
    ModelResponse(id=id_generator.get_new_id(), name="Claude 3.5 Sonnet", provider="Anthropic", version="2024-10-22"),
    ModelResponse(id=id_generator.get_new_id(), name="Gemini 2.0 Flash", provider="Google", version="2025-02"),
    ModelResponse(id=id_generator.get_new_id(), name="Qwen2.5-72B", provider="Alibaba", version="2024-09"),
    ModelResponse(id=id_generator.get_new_id(), name="DeepSeek-V3", provider="DeepSeek", version="2024-12"),
])

# 列表
@app.get('/models', response_model=list[ModelResponse])
def list_models(skip: int = 0, limit: int = 100):
    return models.get_models()[skip: skip + limit]

# 查询列表
@app.get('/models/search', response_model=list[ModelResponse])
def list_models_filtered(provider: Provider):
    return [m for m in models.get_models() if m.provider == provider]

# 详情
@app.get('/models/{model_id}', response_model=ModelResponse)
def detail_model(model_id: int):
    model = models.get_model(model_id)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")
    return model

# 新增
@app.post('/models', status_code=status.HTTP_201_CREATED, response_model=ModelResponse)
def create_model(model: ModelCreate):
    new_model = models.append(model)
    return new_model

# 更新
@app.put('/models/{model_id}', response_model=ModelResponse)
def update_model(model_id: int, model_info: ModelCreate):
    try:
        new_model = models.update(id=model_id, model_info=model_info)
        return new_model
    except ValueError:
        raise HTTPException(status_code=404, detail="Model not found")

# 部分更新
@app.patch('/models/{model_id}', response_model=ModelResponse)
def patch_model(model_id: int, model_info: ModelUpdate):
    # patch_data_dict = model_info.model_dump(exclude_unset=True)
    # patch_data = ModelUpdate.model_validate(patch_data_dict)
    try:
        new_model = models.update(id=model_id, model_info=model_info)
        return new_model
    except ValueError:
        raise HTTPException(status_code=404, detail="Model not found")

# 删除
@app.delete('/models/{model_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: int):
    try:
        models.delete(id=model_id)
        return True
    except ValueError:
        raise HTTPException(status_code=404, detail="Model not found")
    
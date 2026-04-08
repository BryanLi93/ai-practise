from typing import Literal, get_args
from pydantic import BaseModel, Field, field_validator

Provider = Literal["OpenAI", "Anthropic", "Google", "Alibaba", "DeepSeek", "Meta"]
provider_list = list(get_args(Provider))

# class PricingTier(BaseModel):
#     input_per_1m: float
#     output_per_1m: float
class ModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d{4}-\d{2}(-\d{2})?$")
    # pricing_tier: PricingTier | None = None
    input_per_1m: float | None = None
    output_per_1m: float | None = None
    
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
    # pricing_tier: PricingTier | None = None
    input_per_1m: float | None = None
    output_per_1m: float | None = None
class ModelResponse(ModelCreate):
    id: int

    model_config = { "from_attributes": True }

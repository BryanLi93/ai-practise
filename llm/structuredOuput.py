from pydantic import BaseModel, ValidationError, Field
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolUnionParam
from utils import chat_completions, chat_for_tool_calls
from typing import Iterable, Literal

reviews = [
    # 热情好评
    "用了两周了真的被惊艳到！之前完全不懂怎么写提示词，现在随便输入几句话就能出很好的内容，感觉打开了新世界的大门。客服响应也很快，遇到问题基本当天解决。强烈推荐给和我一样的AI小白！", 
    # 理性好评
    "作为用了半年的老用户说几点：稳定性比同类产品好很多，高峰期也没遇到过严重卡顿；上下文记忆能力在同价位里算强的；API调用文档写得清晰，开发者友好。扣一星是因为免费额度太少，想好好用还是得充钱。", 
    # 情绪差评
    "充了会员第二天就开始限速，问客服说是'系统正常机制'？正常机制就是让付费用户用起来和免费版一样慢吗？功能是挺多的，但这个会员体验真的让我很失望，续费之前会好好想想。", 
    # 混合评价
    "写文案、改简历、做翻译：满分。让它帮我算复杂表格、处理专业数据：翻车。所以这个工具适合内容类需求，别指望它做严谨的数字分析。定位清楚了反而觉得还不错，就是定价偏高，希望出个轻量版。", 
    # 冷静差评
    "用了快一年，最近版本更新之后反而越来越难用。回答变得更'安全'了，很多之前能做的内容现在直接拒绝，创作自由度大幅下降。理解平台有合规压力，但目前状态已经不适合我的使用场景了，换了别家。"
]

class ReviewAnalysis(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"] = Field(description="情感倾向") # positive / negative / neutral
    score: float = Field(ge=0, le=1, description="情感得分") # 0.0 - 1.0 情感得分
    pros: list[str] = Field(description="优点列表") # 优点列表
    cons: list[str] = Field(description="缺点列表") # 缺点列表
    keywords: list[str] = Field(description="关键词") # 关键词
    summary: str = Field(description="关键词") # 一句话摘要

# JSON Mode
def json_mode():
    jsons_success_json_mode = []
    jsons_fail_json_mode = []
    messages_json_mode: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": """你是一个评论分析助手。请严格按照以下 JSON 格式输出：
            {
                "sentiment": "positive/negative/neutral",
                "score": 0.0-1.0,
                "pros": ["优点1", "优点2"],
                "cons": ["缺点1", "缺点2"],
                "keywords": ["关键词1", "关键词2"],
                "summary": "一句话摘要"
            }
            只输出 JSON，不要其他内容。"""
        },
    ]
    for index, review in enumerate(reviews):
        print(f"[JSON Mode]: is handling {index + 1}")
        reply = chat_completions(messages_history=messages_json_mode, user_input=review)
        if reply:
            try:
                ReviewAnalysis.model_validate_json(json_data=reply)
                jsons_success_json_mode.append(reply)
            except ValidationError:
                jsons_fail_json_mode.append(reply)

    print("jsons_success_json_mode--- ", jsons_success_json_mode)
    print("jsons_fail_json_mode--- ", jsons_fail_json_mode)

# Function Calling
tools_schema: Iterable[ChatCompletionToolUnionParam] = [
    {
        "type": "function",
        "function": {
            "name": "get_review_structure",
            "description": "获取评论的结构",
            # TODO: 怎么添加 description？
            "parameters": ReviewAnalysis.model_json_schema()
        }
    },
]
messages_function_calling: list[ChatCompletionMessageParam] = [
    {"role": "system", "content": "你是一个分析用户评价的助手"}
]

def function_calling():
    jsons_success_function_calling = []
    jsons_fail_function_calling = []

    for index, review in enumerate(reviews):
        print(f"[Function Calling]: is handling {index + 1}")
        reply = chat_for_tool_calls(
            [
                *messages_function_calling,
                { "role": "user", "content": review }
            ],
            tools_schema
        )
        arguments = reply[0].function.arguments
        if arguments:
            try:
                ReviewAnalysis.model_validate_json(json_data=arguments)
                jsons_success_function_calling.append(arguments)
            except ValidationError:
                jsons_fail_function_calling.append(arguments)

    print("jsons_success_function_calling--- ", jsons_success_function_calling)
    print("jsons_fail_function_calling--- ", jsons_fail_function_calling)


# Structured Output
def structured_output():
    messages_structured_output: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": "你是一个分析用户评价的助手"
        }
    ]
    jsons_success_structured_output = []
    jsons_fail_structured_output = []

    for index, review in enumerate(reviews):
        print(f"[Structured Output]: is handling {index + 1}")
        reply = chat_completions(
            messages_history=messages_structured_output,
            user_input=review,
            response_format= {
                "type": "json_schema",
                "json_schema": {
                    "name": "review_analysis",
                    "schema": ReviewAnalysis.model_json_schema()
                }
            }
        )
        if reply:
            try:
                ReviewAnalysis.model_validate_json(json_data=reply)
                jsons_success_structured_output.append(reply)
            except ValidationError:
                jsons_fail_structured_output.append(reply)

    print("jsons_success_structured_output--- ", jsons_success_structured_output)
    print("jsons_fail_structured_output--- ", jsons_fail_structured_output)



json_mode()
function_calling()
structured_output()
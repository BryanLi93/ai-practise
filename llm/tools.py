from typing import Iterable
from openai.types.chat import ChatCompletionToolUnionParam

def get_weather(city: str):
    print(f"get_weather({city})")
    city_weather_map = {
        "镇江": {
            "temp": 15,
            "condition": "雨"
        },
        "厦门": {
            "temp": 26,
            "condition": "阴"
        },
        "北京": {
            "temp": 20,
            "condition": "晴"
        }
    }
    try:
        return city_weather_map[city]
    except KeyError:
        return { "error": "未找到该城市的天气数据" }

# print(get_weather("镇江"))
# print(get_weather("北京"))
# print(get_weather("成都"))

def calculate(expression: str):
    print(f"calculate({expression})")
    return eval(expression)

# print(calculate("1+10"))
# print(calculate("4*8"))

# 工具的结构，传给 AI
tools_schema: Iterable[ChatCompletionToolUnionParam] = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如 '北京'"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算算术表达式",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "算术表达式，如 '10*4'"
                    }
                },
                "required": ["expression"]
            }
        }
    }
]

# 工具名映射字典
tools_registry = {
    "get_weather": get_weather,
    "calculate": calculate
}
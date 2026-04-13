from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from dotenv import load_dotenv
import os
from typing import Any

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_BASE_URL = os.getenv("GOOGLE_BASE_URL")

client = OpenAI(base_url=GOOGLE_BASE_URL, api_key=GOOGLE_API_KEY)

def chat_completions(user_input: str, messages_history: list[ChatCompletionMessageParam], response_format: dict[str, Any] | None = None):
    try:
        if not messages_history:
            messages_history = []
        params = {
            "model":"gemini-3.1-flash-lite-preview",
            "messages":[*messages_history, { "role": "user", "content": user_input }],
        }
        if response_format:
            params["response_format"] = response_format
        response = client.chat.completions.create(
            **params
        )
        reply = response.choices[0].message.content
        if reply:
            return reply
            # return [*messages_history, { "role": "user", "content": user_input }, { "role": "assistant", "content": reply }]
        else:
            print("error: LLM no response")
    except Exception as e:
        print(e)

def chat_for_tool_calls(messages: list[ChatCompletionMessageParam], tools_schema):
    response = client.chat.completions.create(
        model="gemini-3.1-flash-lite-preview",
        messages=messages,
        tools=tools_schema
    )
    return response.choices[0].message.tool_calls
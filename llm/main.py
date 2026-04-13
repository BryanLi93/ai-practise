from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from dotenv import load_dotenv
import os
from tools import tools_schema, tools_registry
import json

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_BASE_URL = os.getenv("GOOGLE_BASE_URL")

client = OpenAI(base_url=GOOGLE_BASE_URL, api_key=GOOGLE_API_KEY)
messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": "你是一个助手"}]

# while True:
#     user_input = input("You: ")
#     if user_input in ["quit", "exit"]:
#         break
#     try:
#         response = client.chat.completions.create(
#             model="gemini-3.1-flash-lite-preview",
#             messages=messages
#         )
#         reply = response.choices[0].message.content
#         if reply:
#             messages.append({ "role": "user", "content": user_input })
#             messages.append({ "role": "assistant", "content": reply })
#             print(f"Assistant: {reply}")
#         else:
#             print("error: LLM no response")
#     except Exception as e:
#         print(e)

def func_call(messages: list[ChatCompletionMessageParam]):
    response = client.chat.completions.create(
        model="gemini-3.1-flash-lite-preview",
        messages=messages,
        tools=tools_schema
    )
    message = response.choices[0].message

    if message.tool_calls:
        tool_messages = []
        for tool_call in message.tool_calls:
            name = tool_call.function.name

            arguments = tool_call.function.arguments
            args = json.loads(arguments)

            result = tools_registry[name](**args)
            tool_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)
            })
        return [
            *messages,
            message,
            *tool_messages
        ]
    else:
        return messages

# 流式
while True:
    user_input = input("You: ")
    if user_input in ["quit", "exit"]:
        break
    try:
        messages.append({ "role": "user", "content": user_input })
        messages_with_tools = func_call(messages)
        messages = messages_with_tools

        stream = client.chat.completions.create(
            model="gemini-3.1-flash-lite-preview",
            messages=messages,
            stream=True,
        )
        reply = ""
        print("\nAssistant: ")
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                reply += delta.content
                print(delta.content, end="", flush=True)
        messages.append({ "role": "assistant", "content": reply })
        print("\n")
    except Exception as e:
        print(e)
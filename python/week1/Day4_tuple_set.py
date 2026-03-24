import copy

# Day 4：元组（tuple）、集合（set）、解包

### 练习 1：函数返回多值 + 解包

# 写一个函数，分析一组数字，返回多个统计值：

def analyze_numbers(nums: list[int | float]) -> tuple:
    
    """
    返回一个 tuple，包含：(最小值, 最大值, 平均值, 极差)
    极差 = 最大值 - 最小值
    """
    
    return (min(nums), max(nums), sum(nums)/len(nums), max(nums) - min(nums))

# 测试
data = [23, 45, 12, 67, 34, 89, 5, 56]

# 用解包接收
minimum, maximum, average, range_val = analyze_numbers(data)
# print(f"最小值：{minimum}")          # 5
# print(f"最大值：{maximum}")          # 89
# print(f"平均值：{average}")          # 41.375
# print(f"极差：{range_val}")          # 84

### 练习 2：set 集合运算

# 模拟两个版本的 API 接口变更分析：

v1_endpoints = {
    "/api/users",
    "/api/users/:id",
    "/api/products",
    "/api/products/:id",
    "/api/orders",
    "/api/auth/login",
    "/api/auth/logout",
}

v2_endpoints = {
    "/api/users",
    "/api/users/:id",
    "/api/users/:id/profile",
    "/api/products",
    "/api/products/:id",
    "/api/products/search",
    "/api/orders",
    "/api/orders/:id",
    "/api/auth/login",
}

def analyze_api_changes(old: set, new: set) -> dict:
    """
    返回一个字典：
    {
        "added": 新增的接口（v2有v1没有）,
        "removed": 移除的接口（v1有v2没有）,
        "unchanged": 未变的接口,
        "total_old": v1 接口总数,
        "total_new": v2 接口总数,
    }
    """
    return     {
        "added": new - old,
        "removed": old - new,
        "unchanged": new & old,
        "total_old": len(old),
        "total_new": len(new),
    }

result = analyze_api_changes(v1_endpoints, v2_endpoints)
# 打印变更报告
# print(result)

### 练习 3：`*args` / `**kwargs` 实战

# 写一个灵活的日志函数：

def log(level: str, *messages, **metadata):
    """
    level: "INFO" / "WARN" / "ERROR"
    *messages: 任意数量的日志消息，用空格拼接
    **metadata: 任意附加信息，格式化为 key=value

    输出格式：[LEVEL] 消息内容 | key1=value1 key2=value2
    如果没有 metadata，不输出 | 后面的部分
    """
    addition_info = ''
    for key, value in metadata.items():
        addition_info += f'{key}={value} '
    addition_info = addition_info.strip()
    
    print(f"[{level}] {' '.join(messages)}{' | ' + addition_info if addition_info else '' }")


# 测试
# log("INFO", "服务器启动成功")
# [INFO] 服务器启动成功

# log("WARN", "请求超时", "正在重试", retry=3, timeout=5000)
# [WARN] 请求超时 正在重试 | retry=3 timeout=5000

# log("ERROR", "数据库连接失败", host="192.168.1.1", port=5432, db="myapp")
# [ERROR] 数据库连接失败 | host=192.168.1.1 port=5432 db=myapp

### 练习 4：数据去重 + 统计

# 处理一组用户行为日志，去重并统计：

access_logs = [
    {"user": "Alice", "page": "/home", "action": "view"},
    {"user": "Bob", "page": "/products", "action": "view"},
    {"user": "Alice", "page": "/home", "action": "view"},      # 重复
    {"user": "Charlie", "page": "/home", "action": "view"},
    {"user": "Alice", "page": "/products", "action": "click"},
    {"user": "Bob", "page": "/products", "action": "view"},     # 重复
    {"user": "Alice", "page": "/checkout", "action": "click"},
    {"user": "Diana", "page": "/home", "action": "view"},
    {"user": "Bob", "page": "/home", "action": "view"},
    {"user": "Charlie", "page": "/products", "action": "click"},
    {"user": "Alice", "page": "/products", "action": "click"},  # 重复
    {"user": "Diana", "page": "/checkout", "action": "view"},
]

def analyze_logs(logs: list[dict]) -> dict:
    """
    要求：
    1. 去重：同一用户在同一页面的同一行为只算一次
       提示：把 user+page+action 组合成 tuple 放进 set 去重
    2. 统计每个用户访问了哪些不同的页面（set）
    3. 统计每个页面的独立访客数（UV）
    4. 找出所有用户都访问过的页面（交集）
    5. 找出只有一个用户访问过的页面


    返回格式：
    {
        "unique_count": 去重后的记录数,
        "user_pages": {"Alice": {"/home", "/products", ...}, ...},
        "page_uv": {"/home": 4, "/products": 3, ...},
        "common_pages": 所有用户都访问过的页面集合,
        "exclusive_pages": 只有一个用户访问过的页面集合,
    }
    """
    jointLogs = [f"{l['user']}{l['page']}{l['action']}" for l in logs]

    user_pages = {}
    page_pv = {}
    for l in logs:
        # if l['action'] == 'view':
        user_pages.setdefault(l["user"], set()).add(l["page"])
        page_pv.setdefault(l["page"], []).append(l["user"])

    page_uv = { p: len(set(names)) for p, names in page_pv.items()}
    user_pages_set = list(user_pages.values())

    return {
        "unique_count": len(set(jointLogs)),
        "user_pages": user_pages,
        "page_uv": page_uv,
        # "common_pages": user_pages["Alice"] & user_pages["Bob"] & user_pages["Charlie"] & user_pages["Diana"] ,
        # "exclusive_pages": user_pages["Alice"] ^ user_pages["Bob"] ^ user_pages["Charlie"] ^ user_pages["Diana"],
        "common_pages": user_pages_set[0].intersection(*user_pages_set[1:]),
        "exclusive_pages": [page for page, uv in page_uv.items() if uv == 1],
    }

result = analyze_logs(access_logs)
# print(result)

### 练习 5：综合应用 — 配置合并器

# 写一个配置合并函数，模拟前端项目中常见的"默认配置 + 用户配置 + 环境配置"多层合并：

default_config = {
    "host": "localhost",
    "port": 3000,
    "debug": False,
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "mydb",
    },
    "features": {"auth", "logging"},       # 注意这是 set
    "allowed_origins": ("http://localhost",),  # 注意这是 tuple
}

user_config = {
    "port": 8080,
    "debug": True,
    "database": {
        "host": "db.example.com",
        "password": "secret123",
    },
    "features": {"cache", "logging"},
}

env_config = {
    "host": "0.0.0.0",
    "database": {
        "name": "prod_db",
    },
    "allowed_origins": ("http://localhost", "https://example.com"),
}

def merge_configs(*configs) -> dict:
    result_configs = copy.deepcopy(configs[0])

    for config in configs[1:]:
        for key, new_value in config.items():
            # print(key, new_value)
            old_value = result_configs.get(key)
            if (key in result_configs):
                if isinstance(old_value, tuple):
                    result_configs[key] = tuple(set(old_value + new_value))
                elif  isinstance(old_value, set):
                    result_configs[key] = old_value | new_value
                elif  isinstance(old_value, dict):
                    merge_configs(old_value, new_value)
                else:
                    result_configs[key] = new_value
            else:
                result_configs[key] = new_value
    return result_configs


    """
    要求：
    1. 接收任意数量的配置字典（用 *args）
    2. 后面的配置覆盖前面的（优先级从左到右递增）
    3. 嵌套字典要深度合并，不是直接覆盖
       比如 user_config 的 database 应该跟 default 的 database 合并，
       而不是整个替换掉
    4. set 类型的值做并集合并（features 应该是三者的并集）
    5. tuple 类型的值做拼接去重
    6. 其他类型直接覆盖

    merge_configs(default_config, user_config, env_config)

    期望输出：
    {
        "host": "0.0.0.0",
        "port": 8080,
        "debug": True,
        "database": {
            "host": "db.example.com",
            "port": 5432,
            "name": "prod_db",
            "password": "secret123",
        },
        "features": {"auth", "logging", "cache"},
        "allowed_origins": ("http://localhost", "https://example.com"),
    }
    """
    pass

result = merge_configs(default_config, user_config, env_config)
# print(result)

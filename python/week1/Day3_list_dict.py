# 练习 1：列表基础操作
# 模拟一个任务管理器，实现以下操作：
def task_manager():
    tasks = ["写周报", "review 代码", "修 bug", "开周会", "写文档"]

    # 1. 在"修 bug"后面插入"写单测"
    bug_index = tasks.index("修 bug")
    tasks.insert(bug_index + 1,"写单测")
    # 2. 删除"开周会"
    weekly_meeting_index = tasks.index("开周会")
    tasks.pop(weekly_meeting_index)
    # 3. 把最后一个任务移到第一个位置
    last_item = tasks.pop()
    tasks.insert(0, last_item)
    # 4. 返回修改后的列表
    return tasks

# print(task_manager())
# 期望：["写文档", "写周报", "review 代码", "修 bug", "写单测"]


# 练习 2：字典 CRUD
# 写一个简易通讯录：
def contacts_demo():
    contacts = {}

    # 1. 添加 3 个联系人：
    #    "Alice" → {"phone": "13800001111", "email": "alice@test.com"}
    #    "Bob" → {"phone": "13900002222", "email": "bob@test.com"}
    #    "Charlie" → {"phone": "13700003333", "email": "charlie@test.com"}
    contacts.update({
        "Alice":  {"phone": "13800001111", "email": "alice@test.com"},
        "Bob": {"phone": "13900002222", "email": "bob@test.com"},
        "Charlie": {"phone": "13700003333", "email": "charlie@test.com"}
    })

    # 2. 修改 Bob 的 phone 为 "15000005555"
    contacts["Bob"] = contacts.get("Bob") | { "phone": "15000005555" }

    # 3. 安全获取 "David" 的信息（不存在不要报错），打印结果
    print(contacts.get("David"))

    # 4. 删除 Charlie
    contacts.pop("Charlie")

    # 5. 打印所有联系人的名字和电话（格式："{name}: {phone}"）
    for k, v in contacts.items():
        print(f"{k}: {v.get("phone")}")

    # 你的代码
    return contacts

# contacts_demo()

# 练习 3：列表推导式改写
# 把以下 JS 逻辑用 Python 列表推导式实现：
products = [
    {"name": "手机", "price": 4999, "category": "电子"},
    {"name": "耳机", "price": 299, "category": "电子"},
    {"name": "T恤", "price": 99, "category": "服装"},
    {"name": "笔记本电脑", "price": 8999, "category": "电子"},
    {"name": "运动鞋", "price": 599, "category": "服装"},
    {"name": "键盘", "price": 399, "category": "电子"},
]

# 1. 提取所有商品名称
#    JS: products.map(p => p.name)
# names = # 你的代码
# print([product.get("name") for product in products])

# 2. 筛选价格大于 500 的商品
#    JS: products.filter(p => p.price > 500)
# expensive = # 你的代码
# print([product for product in products if product.get("price") > 500 ])

# 3. 提取"电子"类别的商品名称
#    JS: products.filter(p => p.category === "电子").map(p => p.name)
# electronics = # 你的代码
# print([product.get("name") for product in products if product.get("category") == "电子"])


# 4. 给所有商品打 8 折，生成 [{name, discounted_price}] 列表
#    JS: products.map(p => ({ name: p.name, discountedPrice: p.price * 0.8 }))
# discounted = # 你的代码
# print([{ "name": product.get("name"), "discountedPrice": round(product.get("price") * 0.8, 2) } for product in products])

# 5. 按类别分组，生成 {"电子": [...], "服装": [...]} 的字典
#    JS: 用 reduce 实现分组
# grouped = # 你的代码（这个用字典推导式或循环都行）
grouped = {}
for product in products:
    grouped.setdefault(product.get("category"), [])
    grouped.get(product.get("category")).append(product)
# print(grouped)

# 练习 4：数据清洗
# 处理一组脏数据，练习 list + dict + 推导式的综合运用：
raw_scores = [
    {"student": "Alice", "math": "95", "english": "88"},
    {"student": "Bob", "math": "76", "english": "N/A"},
    {"student": "", "math": "80", "english": "90"},
    {"student": "Charlie", "math": "invalid", "english": "72"},
    {"student": "Diana", "math": "88", "english": "91"},
    {"student": "Eve", "math": "60", "english": "55"},
]

def process_scores(data: list[dict]):
    # -> dict:
    """
    要求：
    1. 跳过 student 为空的记录
    2. 将 math 和 english 从字符串转为 int，无法转换的视为 0 分
    3. 计算每个学生的平均分
    4. 返回一个字典，格式为：
       {
           "students": [
               {"name": "Alice", "math": 95, "english": 88, "avg": 91.5},
               ...
           ],
           "class_avg": 全班平均分（float，保留1位小数）,
           "highest": 最高平均分的学生名字,
           "passed": 平均分 >= 60 的学生名字列表
       }
    """
    step1_arr = [d for d in data if d.get("student")]
    step2_arr = [ d | { "math": int(d.get("math")) if d.get("math").isdigit() else 0, "english": int(d.get("english")) if d.get("english").isdigit() else 0 }  for d in step1_arr]
    step3_arr = [ d | { "avg": (d.get("math") + d.get("english")) / 2 }  for d in step2_arr]
    
    students = sorted(step3_arr, key=lambda s: s["avg"], reverse=True)
    avg_total = 0
    highest = ""
    passed = []
    for index, student in enumerate(students):
        name = student.get("student")
        avg = student.get("avg")

        student["name"] = name
        student.pop("student")
        avg_total += avg
        if index == 0: highest = name
        if avg >= 60: passed.append(name)
    return {
        "students": students,
        "class_avg": avg_total / len(students),
        "highest": highest,
        "passed": passed
    }

result = process_scores(raw_scores)
# print(result)

# 练习 5：JSON 数据转换
# 写一个函数，把嵌套的前端组件树结构展平成列表（这个场景你在前端一定遇到过）：
component_tree = {
    "name": "App",
    "type": "div",
    "children": [
        {
            "name": "Header",
            "type": "header",
            "children": [
                {"name": "Logo", "type": "img", "children": []},
                {"name": "Nav", "type": "nav", "children": [
                    {"name": "Link1", "type": "a", "children": []},
                    {"name": "Link2", "type": "a", "children": []},
                ]},
            ]
        },
        {
            "name": "Main",
            "type": "main",
            "children": [
                {"name": "Article", "type": "article", "children": []},
            ]
        },
    ]
}

def flatten_tree(node: dict, depth: int = 0) -> list[dict]:
    """
    把嵌套组件树展平成一维列表，每项包含：
    - name: 组件名
    - type: 元素类型
    - depth: 嵌套深度（根节点为 0）
    
    期望输出：
    [
        {"name": "App", "type": "div", "depth": 0},
        {"name": "Header", "type": "header", "depth": 1},
        {"name": "Logo", "type": "img", "depth": 2},
        {"name": "Nav", "type": "nav", "depth": 2},
        {"name": "Link1", "type": "a", "depth": 3},
        {"name": "Link2", "type": "a", "depth": 3},
        {"name": "Main", "type": "main", "depth": 1},
        {"name": "Article", "type": "article", "depth": 2},
    ]
    """
    dom_list = [{ "name": node["name"], "type": node["type"], "depth": depth }]
    for c in node.get("children"): dom_list.extend(flatten_tree(c, depth + 1))
    return dom_list
print(flatten_tree(component_tree))
result = flatten_tree(component_tree)
for item in result:
    indent = "  " * item["depth"]
    print(f"{indent}{item['name']} <{item['type']}>")

# 期望输出：
# ```
# App <div>
#   Header <header>
#     Logo <img>
#     Nav <nav>
#       Link1 <a>
#       Link2 <a>
#   Main <main>
#     Article <article>
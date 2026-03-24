# Day 2：变量、数据类型、字符串操作
# ⚠️主要的 JS → Python 习惯迁移要注意：if 不加括号、命名用 snake_case、用负索引代替 arr[arr.length - 1]。这些不是错误，但越早养成 Python 风格越好。

# print(10 / 3)

# 整除法
# print(10 // 3) # 3

# 多行字符串
# print('''这是一个多行字符串
#     可以换行
# ''')

# 练习 1：基础类型转换
# 写一个函数，接收一个用户输入的字符串（比如 "123.45"），判断它是整数还是浮点数，并转换成对应的数值类型返回。如果无法转换，返回 None。
def parse_number(s: str) -> int | float | None:
    if ("." in s):
        try: return float(s)
        except ValueError:
            pass
    else:
        try: return int(s)
        except ValueError:
            pass
    pass

# 测试
# print(parse_number("42"))       # 42 (int)
# print(parse_number("3.14"))     # 3.14 (float)
# print(parse_number("hello"))    # None

# 练习 2：f-string 格式化报表
# 写一个函数，接收商品名称、单价和数量，返回格式化的字符串。要求：商品名左对齐 15 个字符宽，单价保留 2 位小数，总价带千分位分隔符。
def format_line(name: str, price: float, qty: int) -> str:
    return f"{name:<15}| ¥{price:,.2f} x {qty} | 总计：¥{price * qty:,.2f}"
    pass

# 测试
# print(format_line("iPhone 16", 7999.00, 3))
# 期望输出："iPhone 16       | ¥7,999.00 x 3 | 总计：¥23,997.00"
# print(format_line("数据线", 29.90, 10))
# 期望输出："数据线            | ¥29.90 x 10 | 总计：¥299.00"

# 练习 3：Truthy/Falsy 检测器
# 写一个函数，接收任意值，返回一个描述字符串，包含：值本身、类型名、bool 转换结果。
def describe(value) -> str:
    return f"值：{value} | {type(value).__name__} | bool：{bool(value)}"
    pass

# 测试
# print(describe(0))         # "值：0 | 类型：int | bool：False"
# print(describe(""))        # "值： | 类型：str | bool：False"
# print(describe("hello"))   # "值：hello | 类型：str | bool：True"
# print(describe(None))      # "值：None | 类型：NoneType | bool：False"
# print(describe([1, 2]))    # "值：[1, 2] | 类型：list | bool：True"

# 练习 4：字符串切片工具
# 写三个函数：
# 1. 提取文件扩展名
def get_extension(filename: str) -> str | None | list:
    if ("." in filename):
        return filename.rsplit(".", 1)[-1]
print(get_extension("app.tsx")) #→ "tsx"
print(get_extension("Dockerfile")) #→ None

# 2. 隐藏手机号中间4位
def mask_phone(phone: str) -> str:
    if len(phone) == 11:
        return phone[0:3] + '****' + phone[-4:]  
    pass
# print(mask_phone("13812345678")) # → "138****5678"

# 3. 驼峰转蛇形（camelCase → snake_case）
def to_snake_case(s: str) -> str:
    result = ''
    for word in s:
        if (word.isupper()):
            result += '_' + word.lower()
        else:
            result += word
    return result
# print(to_snake_case("backgroundColor")) #→ "background_color"
# print(to_snake_case("fontSize")) #→ "font_size"

# 练习 5：购物车数据处理
# 综合运用所有知识点，处理一组混乱的原始数据：
# 原始数据（模拟从接口拿到的脏数据）
raw_items = [
    {"name": "MacBook Pro", "price": "14999.00", "qty": "2", "in_stock": "true"},
    {"name": "AirPods", "price": "1299", "qty": "0", "in_stock": "false"},
    {"name": "", "price": "999.50", "qty": "1", "in_stock": "true"},
    {"name": "iPad Air", "price": "invalid", "qty": "3", "in_stock": "true"},
    {"name": "Magic Mouse", "price": "699.00", "qty": "1", "in_stock": "true"},
]

def format_cart_line(name: str, price: float, qty: int) -> str:
    return f'{name:<16} | ¥{price:<9,.2f} x {qty} | {"已售罄" if qty == 0 else f"¥{price*qty:<9,.2f}"}' 

def process_cart(items: list[dict]) -> str:
    # 要求：
    # 1. 跳过 name 为空的项
    # 2. price 无法转为数字的，打印警告并跳过
    # 3. qty 为 0 的标注"已售罄"
    # 4. in_stock 是字符串 "true"/"false"，转为 bool
    # 5. 最终打印格式化的购物车清单和有效商品总价
    item_lines = []
    total_price = 0
    for item in items:
        name = item.get('name')
        qty = item.get('qty')
        price = item.get('price')

        if (not name):
            # return '⚠️  跳过：name 为空'
            item_lines.append('⚠️  跳过：name 为空')
        # elif (int(qty) == 0):
        #     item_lines.append(f'{name:<16} | ¥{price:<9,.2f} x {qty} | ' )
        else:
            try:
                item_lines.append(format_cart_line(name, float(price), int(qty)))
                total_price += float(price) * int(qty)
            except(ValueError, TypeError):
                item_lines.append(f'⚠️  跳过：{item.get('price')} 价格无效 ("{price}")')
            # print(item.get('price'))
            # print(item.get('price').isdigit())
            # item_lines.append(f'⚠️  跳过：{item.get('price')} 价格无效 ("invalid")')
    print(item_lines)

    return f'''
🛒 购物车清单
──────────────────────────────────────
{'\n'.join(item_lines)}
──────────────────────────────────────
有效商品总计：¥{total_price:,.2f}
'''
#     pass

# print(process_cart(raw_items))
# ```

# 期望输出类似：
# ```
# 🛒 购物车清单
# ──────────────────────────────────────
# MacBook Pro      | ¥14,999.00 x 2 | ¥29,998.00
# AirPods          | ¥1,299.00  x 0 | 已售罄
# ⚠️  跳过：name 为空
# ⚠️  跳过：iPad Air 价格无效 ("invalid")
# Magic Mouse      | ¥699.00    x 1 | ¥699.00
# ──────────────────────────────────────
# 有效商品总计：¥30,697.00
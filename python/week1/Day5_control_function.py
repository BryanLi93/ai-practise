import copy
# Day 5：控制流 + 函数

### 练习 1：多条件排序

# 写一个函数，对员工列表进行多条件排序：

employees = [
    {"name": "Alice", "dept": "engineering", "salary": 15000, "years": 3},
    {"name": "Bob", "dept": "marketing", "salary": 12000, "years": 5},
    {"name": "Charlie", "dept": "engineering", "salary": 18000, "years": 7},
    {"name": "Diana", "dept": "marketing", "salary": 12000, "years": 2},
    {"name": "Eve", "dept": "engineering", "salary": 15000, "years": 5},
    {"name": "Frank", "dept": "design", "salary": 13000, "years": 4},
]

def sort_employees(
    data: list[dict],
    *,
    by: str = "salary",
    descending: bool = True,
    dept_filter: str | None = None,
) -> list[dict]:
    """
    1. 如果指定了 dept_filter，先筛选该部门的员工
    2. 按 by 指定的字段排序
    3. descending 控制升降序
    4. 注意：by 参数后面加 * 强制关键字传参
    
    返回排序后的新列表（不修改原数据）
    """
    filtered = [d for d in data if not dept_filter or d['dept'] == dept_filter ]
    filtered.sort(key = lambda e: e[by], reverse=descending)

    return filtered


# 测试
# 全部员工按薪资降序
# print(sort_employees(employees))

# 只看 engineering 部门，按工龄升序
# print(sort_employees(employees, by="years", descending=False, dept_filter="engineering"))

# 薪资相同时按工龄降序（进阶：by 接受 tuple，多字段排序）

### 练习 2：高阶过滤器

# 写一个函数工厂，根据条件生成过滤函数：

def create_filter(**conditions):
    """
    接收任意关键字参数作为过滤条件，返回一个过滤函数。
    
    支持的条件格式：
    - 字段名=值           → 精确匹配
    - 字段名_min=值       → 大于等于
    - 字段名_max=值       → 小于等于
    - 字段名_contains=值  → 字符串包含
    
    返回的函数接收一个 list[dict]，返回过滤后的 list[dict]
    """
    def filter_func (to_filter_list: list[dict]):
        return [item for item in to_filter_list]

products = [
    {"name": "iPhone 16", "price": 7999, "brand": "Apple", "category": "手机"},
    {"name": "Galaxy S24", "price": 6999, "brand": "Samsung", "category": "手机"},
    {"name": "MacBook Pro", "price": 14999, "brand": "Apple", "category": "电脑"},
    {"name": "ThinkPad X1", "price": 9999, "brand": "Lenovo", "category": "电脑"},
    {"name": "AirPods Pro", "price": 1899, "brand": "Apple", "category": "耳机"},
    {"name": "Pixel 9", "price": 5999, "brand": "Google", "category": "手机"},
]

# 测试
apple_filter = create_filter(brand="Apple")
# print(apple_filter(products))
# [iPhone 16, MacBook Pro, AirPods Pro]

phone_filter = create_filter(category="手机", price_max=7000)
# print(phone_filter(products))
# [Galaxy S24, Pixel 9]

search_filter = create_filter(name_contains="Pro")
# print(search_filter(products))
# [MacBook Pro, AirPods Pro]

combo_filter = create_filter(brand="Apple", price_min=5000, price_max=10000)
# print(combo_filter(products))
# [iPhone 16]

### 练习 3：数据聚合管道

# 写一组聚合函数，模拟数据库的 GROUP BY + 聚合操作：

orders = [
    {"id": 1, "customer": "Alice", "product": "手机", "amount": 4999, "date": "2024-01"},
    {"id": 2, "customer": "Bob", "product": "耳机", "amount": 299, "date": "2024-01"},
    {"id": 3, "customer": "Alice", "product": "电脑", "amount": 8999, "date": "2024-02"},
    {"id": 4, "customer": "Charlie", "product": "手机", "amount": 5999, "date": "2024-02"},
    {"id": 5, "customer": "Bob", "product": "手机", "amount": 4999, "date": "2024-02"},
    {"id": 6, "customer": "Alice", "product": "耳机", "amount": 1299, "date": "2024-03"},
    {"id": 7, "customer": "Charlie", "product": "电脑", "amount": 9999, "date": "2024-03"},
    {"id": 8, "customer": "Bob", "product": "电脑", "amount": 6999, "date": "2024-03"},
]

def group_by(data: list[dict], key: str) -> dict[str, list[dict]]:
    """按指定字段分组"""
    grouped_data = {}
    for d in data:
        grouped_data.setdefault(d.get(key), []).append(d)
    return grouped_data

def aggregate(groups: dict[str, list[dict]], field: str, func: str) -> dict:
    """
    对分组后的数据做聚合计算
    func 支持: "sum", "avg", "max", "min", "count"
    返回 {组名: 聚合结果}
    """
    operation_dict = {
        "sum": sum,
        "avg": lambda arr: round(sum(arr) / len(arr), 2),
        "max": max,
        "min": min,
        "count": len
    }
    # print(operation_dict[func])

    return { key: operation_dict[func]([record[field] for record in group]) for key, group in groups.items()   }

def top_n(data: list[dict], key: str, n: int = 3, descending: bool = True) -> list[dict]:
    """取 top N"""
    return sorted(data, key=lambda user: user[key], reverse=descending)[:n]

# 测试

# 1. 按客户分组，统计每人总消费
by_customer = group_by(orders, "customer")
customer_totals = aggregate(by_customer, "amount", "sum")
print(customer_totals)
# {"Alice": 15297, "Bob": 12297, "Charlie": 15998}

# 2. 按月份分组，统计每月订单数
by_month = group_by(orders, "date")
monthly_counts = aggregate(by_month, "id", "count")
print(monthly_counts)
# {"2024-01": 2, "2024-02": 3, "2024-03": 3}

# 3. 按产品分组，统计平均客单价
by_product = group_by(orders, "product")
product_avg = aggregate(by_product, "amount", "avg")
print(product_avg)
# {"手机": 5332.33, "耳机": 799.0, "电脑": 8665.67}

# 4. 消费最高的前 2 名客户
print(top_n(
    [{"customer": k, "total": v} for k, v in customer_totals.items()],
    key="total",
    n=2
))
# [{"customer": "Charlie", "total": 15998}, {"customer": "Alice", "total": 15297}]

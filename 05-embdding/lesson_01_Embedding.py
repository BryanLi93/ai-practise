from utils import cosine_similarity, get_embeddings

sentences = [
    # 编程相关（中文）
    "Python 是一门非常流行的编程语言",
    "学习 Python 编程可以提升工作效率",
    # 编程相关（英文）
    "Python is a popular programming language",
    # 天气相关
    "今天天气很好，适合出门散步",
    "The weather is nice today",
    # 美食相关
    "我最喜欢吃四川火锅",
    "重庆火锅是中国最有名的美食之一",
    # 完全不相关
    "量子计算机可以解决经典计算机无法处理的问题",
    "太阳系有八大行星围绕太阳运转",
    "今天的股票市场波动很大",
]



vecs_list = get_embeddings(sentences)
similarities: list[tuple[float, str, str]] = []

for i, val1 in enumerate(vecs_list):
    for j, val2 in enumerate(vecs_list[i+1:], start=i+1):
        score = cosine_similarity(val1, val2)
        similarities.append((score, sentences[i], sentences[j]))
similarities.sort(key=lambda x: x[0], reverse=True)

top3 = similarities[:3]
last3 = similarities[-3:]

print("top3:", top3)
print("last3", last3)

'''
top3: [(0.8460421638931941, 'Python 是一门非常流行的编程语言', 'Python is a popular programming language'), (0.7954512957680543, '我最喜欢吃四川火锅', '重庆火锅是中国最有名的美食之一'), (0.7904822979772519, '今天天气很好，适合出门散步', 'The weather is nice today')]
last3 [(0.4995812180174928, '我最喜欢吃四川火锅', '量子计算机可以解决经典计算机无法处理的问题'), (0.49490893925216944, '学习 Python 编程可以提升工作效率', '重庆火锅是中国最有名的美食之一'), (0.48490021013977275, 'The weather is nice today', '量子计算机可以解决经典计算机无法处理的问题')]
'''
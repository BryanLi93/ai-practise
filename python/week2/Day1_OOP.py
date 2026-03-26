from datetime import datetime
# 练习 1：用 class 实现 TodoList
class Todo:
    id_mark = 1

    """单个待办项"""
    def __init__(self, title: str, priority: str = "medium", tags: list[str] | None = None):
        """
        title: 待办标题
        priority: "high" / "medium" / "low"
        创建时自动设置：
        - id: 自增 ID（用类属性计数器实现）
        - completed: False
        - created_at: 当前时间（用 from datetime import datetime）
        """
        self.title = title
        self.priority = priority
        self.tags = tags if tags is not None else []

        self.id = Todo.id_mark
        Todo.id_mark = Todo.id_mark + 1

        self.completed = False
        self.created_at = datetime.now()

    def __str__(self) -> str:
        """打印格式："[✅] #1 买菜 (high)" 或 "[  ] #1 买菜 (high)" """
        return f"[{'✅' if self.completed else ' '}] #{self.id} {self.title} ({self.priority})"

    # def __repr__(self) -> str:
    #     """调试格式："Todo(id=1, title='买菜', priority='high', completed=False)" """
    #     pass

    def __eq__(self, other) -> bool:
        """两个 Todo 的 id 相同就视为相等"""
        pass

    def __lt__(self, other) -> bool:
        """按优先级排序：high > medium > low"""
        priority_order = ['low', 'medium', 'high']
        if priority_order.index(self.priority) < priority_order.index(other.priority):
            return False
        return True

class TodoList:
    """待办列表管理器"""
    def __init__(self, name: str = "My Todos"):
        """
        name: 列表名称
        _todos: 内部存储列表
        """
        self.name = name
        self._todos = []

    def add(self, title: str, priority: str = "medium") -> Todo:
        """添加待办，返回创建的 Todo 对象"""
        todo = Todo(title, priority)
        self._todos.append(todo)
        return todo

    def complete(self, todo_id: int) -> bool:
        """标记完成，返回是否成功"""
        todo =  next((t for t in self._todos if t.id == todo_id), None)
        if (todo):
            todo.completed = True

    def remove(self, todo_id: int) -> bool:
        """删除待办，返回是否成功"""
        pass

    def get_by_priority(self, priority: str) -> list[Todo]:
        """获取指定优先级的所有待办"""
        return [t.title for t in self._todos if t.priority == priority]

    @property
    def pending(self) -> list[Todo]:
        """只读属性：未完成的待办列表"""
        return [t for t in self._todos if t.completed == False]

    @property
    def completed(self) -> list[Todo]:
        """只读属性：已完成的待办列表"""
        return [t for t in self._todos if t.completed == True]

    @property
    def stats(self) -> dict:
        """
        只读属性：统计信息
        返回 {"total": 总数, "completed": 已完成数, "pending": 未完成数, "completion_rate": "XX%"}
        """
        return {
            "total": len(self._todos), "completed": len(self.completed), "pending": len(self.pending), "completion_rate": f"{len(self.completed) / len(self._todos):.0%}"
        }

    def __len__(self) -> int:
        """len(todo_list) 返回总待办数"""
        pass

    def __contains__(self, todo_id: int) -> bool:
        """支持 `todo_id in todo_list` 语法"""
        return any(t.id == todo_id for t in self._todos)

    def __str__(self) -> str:
        """打印整个列表，格式化输出"""
        #         
        return f'''
{self.name} ({len(self._todos)} 项)
──────────────────
{'\n'.join(str(todo) for todo in self._todos)}
        '''


# 测试
todos = TodoList("工作任务")

# 添加待办
t1 = todos.add("完成 RAG 项目", "high")
t2 = todos.add("写技术博客", "medium")
t3 = todos.add("整理书签", "low")
t4 = todos.add("准备面试", "high")

# 打印列表
# print(todos)
# 工作任务 (4 项)
# ──────────────────
# [  ] #1 完成 RAG 项目 (high)
# [  ] #2 写技术博客 (medium)
# [  ] #3 整理书签 (low)
# [  ] #4 准备面试 (high)

# 完成任务
todos.complete(1)
todos.complete(3)

# 属性访问
# print(f"未完成：{len(todos.pending)}")    # 2
# print(f"已完成：{len(todos.completed)}")  # 2
# print(todos.stats)
# {"total": 4, "completed": 2, "pending": 2, "completion_rate": "50%"}

# 按优先级筛选
high_priority = todos.get_by_priority("high")
# print(high_priority)     # [Todo(完成 RAG 项目), Todo(准备面试)]

# in 操作符
# print(1 in todos)        # True
# print(99 in todos)       # False

# 排序（按优先级）
sorted_todos = sorted(todos.pending)
# print([t.title for t in sorted_todos])

# 练习 2：继承 — 带分类的 TodoList
# 在练习 1 的基础上扩展：
# class TimedTodo(Todo):
#     """带截止时间的待办"""
#     def __init__(self, title: str, priority: str = "medium", tags = [], deadline: str = ""):
#         """
#         deadline: "2024-12-31" 格式的截止日期
#         """
#         pass

#     @property
#     def is_overdue(self) -> bool:
#         """是否已过期"""
#         pass

#     def __str__(self) -> str:
#         """在父类基础上追加截止日期：
#         "[  ] #5 提交报告 (high) | 截止：2024-12-31"
#         如果过期追加 ⚠️ 标记
#         """
#         pass


# class ProjectTodoList(TodoList):
#     """项目级待办列表，支持按标签分类"""
#     def __init__(self, name: str, project: str):
#         super().__init__(name)
#         self.project = project

#     def add(self, title: str, priority: str = "medium", tags: list[str] = None) -> Todo:
#         """重写 add，支持标签"""
#         todo = TimedTodo(title, priority, tags)
#         self._todos.append(todo)
#         return todo


#     def get_by_tag(self, tag: str) -> list[Todo]:
#         """按标签筛选"""
#         pass

#     @property
#     def all_tags(self) -> set[str]:
#         """所有使用过的标签（去重）"""
#         pass

#     def summary(self) -> str:
#         """
#         打印项目摘要：
#         项目：RAG 文档问答
#         总任务：6  完成：2  待办：4
#         标签分布：backend(3) frontend(2) devops(1)
#         逾期任务：1
#         """
#         return f'''
# 项目摘要：
# 项目：{self.project}
# 总任务：{len(self._todos)}  完成：{len(self.completed)}  待办：{len(self.pending)}
# 标签分布：backend(3) frontend(2) devops(1)
# 逾期任务：1
#         '''


# # # 测试
# project = ProjectTodoList("Sprint 1", "RAG 文档问答")

# project.add("搭建 FastAPI 后端", "high", ["backend"])
# project.add("实现文档解析", "high", ["backend", "ai"])
# project.add("对接向量数据库", "medium", ["backend", "database"])
# project.add("Chat UI 开发", "medium", ["frontend"])
# project.add("Docker 部署", "low", ["devops"])

# project.complete(1)

# print(project.summary())
# print(project.get_by_tag("backend"))
# print(project.all_tags)
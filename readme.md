# 1.概要

## 1.1 agent架构

		用户
                 │
                 │ 编程任务
                 ▼
        ┌─────────────────┐
        │   Agent Runtime 			│
        │   你自己实现   		       │
        └────────┬────────┘
                 │
          构造 messages
                 │
                 ▼
        ┌─────────────────┐
        │      LLM        				│
        │ GPT/Qwen/etc.   			│
        └────────┬────────┘
                 │
        text / tool_call
                 │
                 ▼
        ┌─────────────────┐
        │ Tool Dispatcher 			│
        │   你自己实现   			  │
        └──────┬─────┬────┘
        		    │   │
       ┌───────┘     └────────┐
       ▼                      ▼
   read_file              run_command
   write_file             list_files
   edit_file              search_text
       │                      │
       └──────────┬───────────┘
                  │
             Tool Result
                  │
                  ▼
                LLM
                  │
              下一步决策
                  │
                  ▼
              直到完成

## 1.2 项目模块概要

coding-agent/
│
├── main.py
│
├── agent/
│   ├── loop.py
│   ├── context.py
│   └── prompt.py
│
├── tools/
│   ├── filesystem.py
│   ├── shell.py
│   └── registry.py
│
├── llm/
│   └── client.py
│
├── workspace/
│
├── config.py
└── README.md

说明：

| 功能层                     | 对应代码文件                                | 功能                                                                 |
| -------------------------- | ------------------------------------------- | -------------------------------------------------------------------- |
| 第一层：LLM Client         | `llm/client.py`                           | 封装 OpenAI / DeepSeek / Qwen / Gemini 等模型 API                    |
| 第二层：Tools              | `tools/filesystem.py`、`tools/shell.py` | 真正执行读写文件、编辑文件、运行命令                                 |
| 第三层：Tool Schema        | `tools/registry.py`                       | 注册工具、定义 schema、根据 tool name 分发调用                       |
| 第四层：Agent Loop         | `agent/loop.py`                           | 驱动“LLM → tool_call → 执行工具 → 返回结果 → 再调用 LLM”的循环 |
| 第五层：Context Management | `agent/context.py`                        | 管理历史消息、摘要、workspace 状态、上下文裁剪                       |
| System Prompt              | `agent/prompt.py`                         | 定义 Agent 的角色、规则、工具使用策略                                |
| 配置层                     | `config.py`                               | 模型名、API Key、workspace、最大轮数等                               |
| 程序入口                   | `main.py`                                 | 初始化各模块、接收用户任务、启动 Agent                               |
| 工作区                     | `workspace/`                              | Agent 实际读写和修改的项目目录                                       |
| 项目说明                   | `README.md`                               | 架构说明、运行方式、示例                                             |

# 2 项目模块

#### 1、 第一层：LLM Client  （`llm/client.py`）

	封装 OpenAI / DeepSeek / Qwen / Gemini 等大语言模型 API以获取llm语言智能支持。

	负责：

messages
↓
API
↓
response

	例如：

from openai import OpenAI

class LLMClient:
    def __init__(self):
        self.client = OpenAI()

    def chat(self, messages, tools):
        return self.client.chat.completions.create(
            model="gpt-5.1",
            messages=messages,
            tools=tools
        )

### 2、第二层：Tools  （`tools/filesystem.py`、`tools/shell.py`）

	提供llm智能与程序文件的交互接口，实现从文字到真正执行读写文件、编辑文件、运行命令。

	最开始只实现 5 个工具就完全够了：

| 工具            | Agent 需要它解决什么问题 | 对应操作              |
| --------------- | ------------------------ | --------------------- |
| `list_files`  | 项目里有什么？           | `ls`/ 看项目目录    |
| `read_file`   | 文件里面写了什么？       | 打开源码              |
| `write_file`  | 创建一个新文件           | 新建`.py/.java/.md` |
| `edit_file`   | 修改已有代码             | IDE 中编辑源码        |
| `run_command` | 修改后是否正确？         | 运行、编译、测试      |

#### list_files：建立对 Workspace 的认知

***流程***

用户提问：

	帮我修复这个项目的登录 Bug

Agent 检索确认项目结构。

	list_files(".")

得到：

	src/
	tests/
	requirements.txt
	README.md

再继续：

	list_files("src")

最终到具体文件：

	main.py
	auth.py
	database.py

***本质：***

用户提问
    ↓
探索确认相关未知环境
    ↓
建立项目结构认知

#### read_file：获得真实代码状态

***流程：***

读指定文件auth.py

	read_file("src/auth.py")

得到相关内容，例如：

def login(username, password):
    user = get_user(username)

    if user.password == password:
        return True

    return False

***本质：***

 observe workspace

所以 read_file 相当于 Agent 的“眼睛”。

#### edit_file：修改已有代码

知道问题以后修改文件，而不需全部重写

解决两个问题：

第一，容易把不需要修改的代码破坏掉。

第二，对于一个 1000 行文件，只改 2 行，却重新写整个文件，非常低效。

#### write_file：创建不存在的文件

有些任务不是修改，而是增加功能。

#### run_command：运行后的反馈闭环（检验、审阅）

检验模型修改代码后需要代码是否能跑，否则需重新思考生成可运行正常代码

***流程***

	run_command("pytest")

得到：

	FAILED

	NameError:
	verify_password is not defined

则模型重新思考：

	哦，我用了 verify_password，但是忘记 import 了。

然后：

	edit_file
	↓
	run_command("pytest")

直到：

	15 passed

最终实现了Agent智能处理的闭环：

        ┌───────────────┐
        │     LLM      			 │
        └───────┬───────┘
                │
              Action
                ↓
        ┌───────────────┐
        │  Environment  		│
        └───────┬───────┘
              	  │
           Observation
                ↓
        ┌───────────────┐
        │     LLM       │
        └───────────────┘

而 run_command 就是最主要的 Environment Feedback Channel。

#### 总结操作全流程

            Workspace

       ┌─────────────────┐
       │   list_files    │
       └────────┬────────┘
                │
           找到文件
                ↓
       ┌─────────────────┐
       │    read_file    │
       └────────┬────────┘
                │
           理解代码
                ↓
       ┌─────────────────┐
       │ edit / write    │
       └────────┬────────┘
                │
           修改代码
                ↓
       ┌─────────────────┐
       │   run_command   │
       └────────┬────────┘
                │
           查看结果
                ↓
              LLM
                │
                └──── 再次循环

### 3、第三层：Tool Schema （`tools/registry.py`）

***本质***

	是 **LLM 和本地工具之间的接口协议层**。为“第二层里写好的 Python 函数”生成“LLM 能理解、能选择、能正确传参的工具说明”，让 LLM知道第二层里编写的 Python 函数，从而将自己从纯语言交流的llm到具有操作文件交互能力的agent智能体。

	与 MCP 思想类似，但比 MCP 简单得多。

***流程***

告诉模型有这些工具：

	例如：

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the content of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string"
                    }
                },
                "required": ["path"]
            }
        }
    }
]

模型于是返回：

tool_call:
read_file(
    path="src/main.py"
)

### 4、第四层：Agent Loop —— 智能体的任务循环管理 （`agent/loop.py`）

***本质***

	Agent Loop 是决定何时做哪个动作、根据结果下一步做什么的控制器，驱动智能体完成“LLM → tool_call → 执行工具 → 返回结果 → 再调用 LLM”的循环。

伪代码：

messages = [
    system_prompt,
    user_task
]

while True:

    response = llm.chat(
        messages,
        tools
    )

    if response has tool_calls:

        for tool_call in response.tool_calls:

            name = tool_call.name
            args = tool_call.arguments

            result = execute_tool(
                name,
                args
            )

            messages.append(
                tool_result
            )

    else:
        print(response.content)
        break

***流程***

用户说：

	帮我给这个 Python 项目增加一个 calculator.py，实现加减乘除并写单元测试。

Agent 可能自动执行：

第1轮
LLM:
list_files

↓

第2轮
LLM:
read_file("main.py")

↓

第3轮
LLM:
write_file("calculator.py")

↓

第4轮
LLM:
write_file("test_calculator.py")

↓

第5轮
LLM:
run_command("pytest")

↓

报错

↓

第6轮
LLM:
read_file("test_calculator.py")

↓

第7轮
LLM:
edit_file(...)

↓

第8轮
LLM:
run_command("pytest")

↓

PASS

↓

Final Answer:
任务完成。

### 5、第五层：Context Management （`agent/context.py`）

***本质***

	通过构建用户画像，实现界面里的上下文管理、记忆等的智能性

***流程：***

问题是越来越长。

所以你可以设计：

最近 N 条完整保留
+
较早历史摘要
+
当前 workspace 状态

例如：

context = [
    system_prompt,
    project_summary,
    previous_summary,
    recent_messages[-10:]
]

这已经是一个非常不错的考核亮点。

### 6、最后再做 UI（`main.py`）

***本质：***

	初始化各模块、接收用户任务、启动 Agent Loop，并将 Agent 的思考状态、工具调用、执行结果和最终回答展示给用户，为用户提供可视化交互使用窗口 ，是整个系统的 **入口层 / 交互层 / orchestration layer** 。

***流程：***

程序启动
   ↓
读取配置
   ↓
初始化 LLM Client
   ↓
初始化 Tool Registry
   ↓
初始化 Context Manager
   ↓
初始化 Agent Loop
   ↓
等待用户输入编程任务
   ↓
将 user_task 交给 Agent
   ↓
Agent 开始循环执行
   ↓
实时展示：
    ├─ Agent 当前状态
    ├─ tool_call
    ├─ 工具参数
    ├─ tool_result
    ├─ 命令执行结果
    └─ 错误信息
   ↓
Agent 判断任务完成
   ↓
输出最终结果
   ↓
等待下一个任务 / 退出

# 3. 预计 待完成（改进点）

#### 1.Memory

保存“对后续任务有价值的长期状态”

Coding Agent 的 memory 最简单可以是：

<pre class="overflow-visible! px-0!" data-start="6204" data-end="6227"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute end-1.5 top-1 z-2 md:end-2 md:top-1"></div><div class="relative"><div class="pe-11 pt-3"><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span>memory.json</span></code></pre></div></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></pre>

里面保存：

<pre class="overflow-visible! px-0!" data-start="6236" data-end="6453"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="relative h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute inset-x-4 top-12 bottom-4"><div class="pointer-events-none sticky z-40 shrink-0 z-1!"><div class="sticky bg-token-border-light"></div></div></div><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class=""><div class="relative"><div class=""><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span>{
  "project": </span><span class="ͼz">"Todo Web App"</span><span>,
  "language": </span><span class="ͼz">"Python"</span><span>,
  "framework": </span><span class="ͼz">"Flask"</span><span>,
  "important_files": [
    </span><span class="ͼz">"app.py"</span><span>,
    </span><span class="ͼz">"templates/index.html"</span><span>
  ],
  "decisions": [
    </span><span class="ͼz">"Use SQLite"</span><span>,
    </span><span class="ͼz">"Use pytest"</span><span>
  ]
}</span></code></pre></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></div></div></pre>

下一轮模型可以读取。

但我提醒你：

> **这个题目首先考 agent runtime，不是 memory research。**

所以优先级应该是：

<pre class="overflow-visible! px-0!" data-start="6535" data-end="6630"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute end-1.5 top-1 z-2 md:end-2 md:top-1"></div><div class="relative"><div class="pe-11 pt-3"><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span>Agent Loop
★★★★★

Tools
★★★★★

Context
★★★★

Error Handling
★★★★

Memory
★★★

UI
★★</span></code></pre></div></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></pre>

---

#### 2、 Error Feedback Loop

当工具执行失败以后，Agent 怎么消费错误，并自主进入下一轮修复。

例如模型生成：

<pre class="overflow-visible! px-0!" data-start="6692" data-end="6716"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="relative h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute inset-x-4 top-12 bottom-4"><div class="pointer-events-none sticky z-40 shrink-0 z-1!"><div class="sticky bg-token-border-light"></div></div></div><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class=""><div class="relative"><div class=""><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span class="ͼ11">print</span><span>(</span><span class="ͼ11">foo</span><span>)</span></code></pre></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></div></div></pre>

执行：

<pre class="overflow-visible! px-0!" data-start="6723" data-end="6749"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="relative h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute inset-x-4 top-12 bottom-4"><div class="pointer-events-none sticky z-40 shrink-0 z-1!"><div class="sticky bg-token-border-light"></div></div></div><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class=""><div class="relative"><div class=""><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span>python main.py</span></code></pre></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></div></div></pre>

返回：

<pre class="overflow-visible! px-0!" data-start="6756" data-end="6797"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute end-1.5 top-1 z-2 md:end-2 md:top-1"></div><div class="relative"><div class="pe-11 pt-3"><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span>NameError: foo is not defined</span></code></pre></div></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></pre>

不要结束。

把错误重新发给模型：

<pre class="overflow-visible! px-0!" data-start="6818" data-end="6905"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute end-1.5 top-1 z-2 md:end-2 md:top-1"></div><div class="relative"><div class="pe-11 pt-3"><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span>Tool result:

Command failed.

stderr:
NameError: name 'foo' is not defined</span></code></pre></div></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></pre>

模型：

<pre class="overflow-visible! px-0!" data-start="6912" data-end="6938"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute end-1.5 top-1 z-2 md:end-2 md:top-1"></div><div class="relative"><div class="pe-11 pt-3"><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span>我需要修改 main.py。</span></code></pre></div></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></pre>

然后：

<pre class="overflow-visible! px-0!" data-start="6945" data-end="6974"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute end-1.5 top-1 z-2 md:end-2 md:top-1"></div><div class="relative"><div class="pe-11 pt-3"><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span>read
↓
edit
↓
run</span></code></pre></div></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></pre>

这才真正体现：

> **Agent，而不是一次性代码生成。**

---

#### 3、安全性

控制智能体的交互安全而不越界（擅自修改系统文件等）

因为：

<pre class="overflow-visible! px-0!" data-start="7036" data-end="7076"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="relative h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute inset-x-4 top-12 bottom-4"><div class="pointer-events-none sticky z-40 shrink-0 z-1!"><div class="sticky bg-token-border-light"></div></div></div><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class=""><div class="relative"><div class=""><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span class="ͼ11">subprocess</span><span class="ͼv">.</span><span>run(</span><span class="ͼ11">shell</span><span class="ͼv">=</span><span class="ͼy">True</span><span>)</span></code></pre></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></div></div></pre>

非常危险。

至少限制 workspace：

<pre class="overflow-visible! px-0!" data-start="7102" data-end="7138"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute end-1.5 top-1 z-2 md:end-2 md:top-1"></div><div class="relative"><div class="pe-11 pt-3"><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span>/root/project/workspace/</span></code></pre></div></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></pre>

工具不能访问：

<pre class="overflow-visible! px-0!" data-start="7149" data-end="7187"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute end-1.5 top-1 z-2 md:end-2 md:top-1"></div><div class="relative"><div class="pe-11 pt-3"><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span>/etc
/root/.ssh
/root/.env</span></code></pre></div></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></pre>

例如：

<pre class="overflow-visible! px-0!" data-start="7194" data-end="7426"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="relative h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute inset-x-4 top-12 bottom-4"><div class="pointer-events-none sticky z-40 shrink-0 z-1!"><div class="sticky bg-token-border-light"></div></div></div><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class=""><div class="relative"><div class=""><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span class="ͼv">def</span><span></span><span class="ͼ11">safe_path</span><span>(</span><span class="ͼ11">path</span><span>):
    </span><span class="ͼ11">resolved</span><span></span><span class="ͼv">=</span><span> (</span><span class="ͼ11">WORKSPACE</span><span></span><span class="ͼv">/</span><span></span><span class="ͼ11">path</span><span>)</span><span class="ͼv">.</span><span>resolve()

    </span><span class="ͼv">if</span><span></span><span class="ͼv">not</span><span></span><span class="ͼ11">str</span><span>(</span><span class="ͼ11">resolved</span><span>)</span><span class="ͼv">.</span><span>startswith(</span><span class="ͼ11">str</span><span>(</span><span class="ͼ11">WORKSPACE</span><span>)):
        </span><span class="ͼv">raise</span><span></span><span class="ͼ11">PermissionError</span><span>(
            </span><span class="ͼz">"Path outside workspace."</span><span>
        )

    </span><span class="ͼv">return</span><span></span><span class="ͼ11">resolved</span></code></pre></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></div></div></pre>

命令也可以过滤：

<pre class="overflow-visible! px-0!" data-start="7438" data-end="7490"><div class="relative w-full mt-4 mb-1"><div class=""><div class="contents"><div class="relative"><div class="h-full min-h-0 min-w-0"><div class="h-full min-h-0 min-w-0"><div class="border border-token-border-light border-radius-3xl corner-superellipse/1.1 rounded-3xl"><div class="h-full w-full border-radius-3xl bg-(--code-block-surface) corner-superellipse/1.1 overflow-clip rounded-3xl [--code-block-surface:var(--bg-elevated-secondary)] dark:[--code-block-surface:var(--composer-surface-primary)] lxnfua_clipPathFallback"><div class="pointer-events-none absolute end-1.5 top-1 z-2 md:end-2 md:top-1"></div><div class="relative"><div class="pe-11 pt-3"><div class="relative z-0 flex max-w-full"><div id="code-block-viewer" dir="ltr" class="q9tKkq_viewer cm-editor z-10 light:cm-light dark:cm-light flex h-full w-full flex-col items-stretch ͼs ͼ16"><div class="cm-scroller"><pre class="cm-content q9tKkq_readonly m-0"><code><span>rm -rf /
shutdown
reboot
curl ... | bash</span></code></pre></div></div></div></div></div></div></div></div></div><div class=""><div class=""></div></div></div></div></div></div></pre>

面试的时候这会成为很好的设计决策：

> “由于 agent 拥有命令执行权限，我对 filesystem 与 shell tool 增加了 workspace sandbox 和危险命令检查。”

---

# 4.项目运行指导

下载环境包：

	pip install -r requirements.txt

提供配置api：
	$env:AGENT_API_KEY="你的 API Key"    sk-8e8216950a2e40608aca2efa8a3d7478

	$env:AGENT_BASE_URL="https://api.deepseek.com"
	$env:AGENT_MODEL="deepseek-chat"

运行:

	python main.py

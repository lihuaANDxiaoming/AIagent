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

### 6、UI（`main.py`）

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

# 3. 改进

3.1 项目架构

coding-agent/
│
├── main.py
├── config.py
│
├── agent/
│   ├── loop.py
│   ├── context.py
│   ├── memory.py
│   ├── prompt.py
│   ├── safety.py
│   └── checkpoint.py
│
├── llm/
│   └── client.py
│
├── tools/
│   ├── filesystem.py
│   ├── shell.py
│   └── registry.py
│
├── storage/
│   ├── memory.json
│   └── checkpoints/
│
├── workspace/
│
├── tests/
│   ├── test_tools.py
│   ├── test_safety.py
│   └── test_agent.py
│
└── README.md

3.2 新增部分

| 新增/增强功能                   | 具体在哪                                         | 作用                                                                |
| ------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------- |
| **长期 Memory**           | `agent/memory.py`+`storage/memory.json`      | 记录跨任务项目状态、技术决策、重要文件、用户长期偏好                |
| **短期 Context 管理增强** | `agent/context.py`                             | 不只是存 messages，还负责最近消息保留、历史摘要、上下文裁剪         |
| **Error Feedback Loop**   | `agent/loop.py`                                | 工具失败后不退出，把 stderr/错误结果重新喂给 LLM，让 Agent 自主修复 |
| **Safety 权限控制**       | `agent/safety.py`                              | workspace 边界、危险命令检查、ALLOW/CONFIRM/DENY                    |
| **用户授权机制**          | `agent/safety.py`+`agent/loop.py`            | 遇到敏感操作时，由 loop 暂停执行并请求授权                          |
| **Rollback / Checkpoint** | `agent/checkpoint.py`+`storage/checkpoints/` | 文件修改前生成快照，支持恢复到最近历史状态                          |
| **持久化层**              | `storage/`                                     | 保存 Memory、checkpoint 等需要跨运行保留的数据                      |
| **Agent Runtime 测试**    | `tests/`                                       | 测 Safety、Tools、Agent Loop、错误恢复等，而不仅仅测试业务代码      |
| **安全配置项**            | `config.py`                                    | workspace 根目录、最大 Agent 轮数、checkpoint 数量、危险命令规则等  |

## 1.Memory

***本质***

	保存“对后续任务有价值的状态信息”，通过对当前任务上下文、长期项目知识以及持久化存储的分层管理，实现 Agent 在跨轮次、跨任务、跨会话场景下对项目状态、用户约束与关键决策的持续利用。

***组成：***

#### 1.1 Short-term Context：短期上下文记忆

***概要：***

	保存当前任务执行过程中产生的上下文信息，并将其作为下一轮 LLM 推理的背景知识。让模型能够感知刚才的信息，包括用户要求、已经调用过的工具、文件内容、执行结果以及错误信息等，从而维持同一任务内部连续的推理与操作能力。

***实现方法：***

	在 `agent/context.py`中维护当前任务的 `messages`表，将用户输入、LLM 输出、tool call 以及 tool result 按顺序加入上下文。在每次重新调用 LLM 时，将当前有效上下文重新组织后发送给模型。

***基本结构：***

System Prompt
+
User Task
+
Assistant Tool Call
+
Tool Result
+
Assistant Tool Call
+
Tool Result
+
...

#### 1.2 Long-term Project Memory：长期记忆增强（Summarization + Truncation）

***概要：***

长期记忆：从短期上下文中筛选并提取对未来任务仍具有价值的稳定信息，并在后续任务中重新注入模型上下文（例如项目技术栈、架构决策、用户长期约束...）。

记忆增强：由于上下文窗口有限，通过 Summarization 与 Truncation 对历史信息进行压缩、筛选和抽象，从而提升信息利用效率。

***实现方法：***

在 `agent/memory.py`中设计 `MemoryManager`，负责长期信息的提取、更新与检索。

可以将长期记忆划分为：

```
project_info
important_files
commands
decisions
constraints
completed_tasks
```

例如：

```
{
  "project": {
    "language": "Python",
    "framework": "Flask"
  },
  "commands": {
    "test": "pytest"
  },
  "important_files": [
    "app.py",
    "auth.py"
  ],
  "decisions": [
    "Use SQLite",
    "Use JWT authentication"
  ]
}
```

同时使用两种上下文压缩机制：

```
History Summarization
=
将较早但仍有价值的历史压缩为摘要

Context Truncation
=
直接删除已经失去价值的低信息内容
```

例如：

```
原始历史：

读取 app.py
读取 auth.py
发现登录逻辑缺少密码哈希校验
修改 auth.py
第一次 pytest 失败
修复测试 fixture
第二次 pytest 全部通过
```

可以压缩为：

```
Summary:
认证逻辑位于 auth.py，
已加入密码哈希校验，
相关测试已经通过。
```

而类似：

```
File written successfully.
Command finished in 0.8s.
```

这类早期低价值信息可以直接 Truncate，不再继续发送给模型。

#### 1.3 Persistent Storage：记忆持久化存储

***概要：***

	将需要长期保留的 Memory 写入外部存储，使 Agent 在程序关闭、重新启动或进入新的对话任务后，仍然能够恢复之前积累的项目知识，从而支持新任务冷启动以及同一项目在不同会话之间的知识共享。

***实现方法：***

用storage/memory.json作为持久化介质。

在 Agent 启动时：

```
load memory.json
↓
恢复 Long-term Project Memory
↓
注入当前 Agent Context
```

任务完成后：

```
提取长期有效信息
↓
更新 Memory
↓
save memory.json
```

可以在 `<span>agent/memory.py</span>` 中实现：

```
class MemoryManager:
    def load(self):
    def save(self):
    def remember(self, key, value):
    def recall(self, key):
```

## 2、Error Feedback Loop

***本质：***

	将工具执行、代码运行和测试过程中产生的错误信息重新反馈给 Agent，使模型能够基于真实环境结果进行再次推理、定位问题、修改代码并重新验证，从而形成自纠错闭环。

***组成：***

#### 2.1 Error Capture：错误捕获

**概要：**

负责从工具执行结果中提取真实环境反馈，包括标准输出、标准错误、返回码、异常信息以及测试结果，使 Agent 能够感知某次操作是成功还是失败，以及失败的具体原因。

**实现方法：**

主要由 `tools/shell.py`中的 `run_command` 提供底层执行能力。

**实例：**

Agent 执行：

run_command("python main.py")

程序返回：

stdout:

stderr:
NameError: name 'foo' is not defined

returncode:
1

此时系统能够明确判断：

此次运行失败
+
错误类型为 NameError
+
错误内容为 foo 未定义

这些信息将作为后续自纠错的输入。

#### 2.2 Feedback Injection：错误反馈注入

***概要：***

	将 Tool 执行产生的错误结果重新加入当前 Short-term Context，使下一轮 LLM 调用能够看到真实环境中的失败信息，并据此继续推理。

***实现方法：***

在 `agent/loop.py` 执行 Tool 后，无论成功还是失败，都将 Tool Result 写入 `agent/context.py` 管理的消息序列。

***实例：***

第一次：

```
LLM:
run_command("pytest")
```

返回：

```
1 failed, 8 passed

AssertionError:
expected 4, got 5
```

系统不会在终端打印错误后就结束，而是将错误信息

```
pytest failed
AssertionError
expected 4, got 5
```

重新放入 Context，帮助因此下一轮模型继续定位代码问题。

#### 2.3 Error Diagnosis：错误诊断与重新推理

***概要：***

LLM 根据上一轮注入的错误信息重新分析当前任务状态，判断错误可能来自哪个文件、哪段逻辑或哪一步操作，并自主选择下一步 Tool。

这是 Error Feedback Loop 中真正体现 Agent 智能性的部分。

***实现方法：***

	agent/loop.py 不直接硬编码，而是将将真实错误交给 LLM，由模型结合用户任务+之前读过的文件+之前做出的修改+当前错误信息共同决定下一步 Action。

#### 2.4 Retry & Self-Correction：重试与自主修正

***概要：***

在完成错误分析和代码修改后，Agent 需要重新执行原有测试或运行命令，对修复结果进行验证。

如果仍然失败，则继续进入下一轮 Error Feedback Loop；如果成功，则退出修复循环并进入最终回答。

***实现方法：***

在 `agent/loop.py` 中保持持续循环：

```
Tool 执行失败
↓
错误加入 Context
↓
重新调用 LLM
↓
再次操作
```

直到测试通过或达到 MAX_AGENT_STEPS（可设置，例如MAX_AGENT_STEPS=20）

#### 2.5 Runtime Verification：运行结果验证

***概要：***

	不仅根据“文件是否成功写入”判断任务完成，还要求 Agent 通过测试、编译或实际运行结果对修改进行验证，从而降低“代码看起来正确但实际上无法运行”的问题。

***实现方法：***

根据不同项目类型选择对应验证方式（例如 Python→ pytest / python main.py）

验证命令仍然通过run_command执行。

Agent Prompt 中可以明确要求：

```
修改代码后尽可能运行测试或构建命令。
如果验证失败，不要直接宣布任务完成。
```

同时在 `<span>tests/test_agent_loop.py</span>` 中测试 Agent Runtime 是否能够正确处理：

```
Tool Failure
Error Injection
Retry
Successful Recovery
```

实例：

Agent 写入：

```
def add(a, b):
    return a - b
```

文件写入工具本身会返回：

```
File written successfully.
```

但这只能证明：

```
文件写成功了
```

并不能证明：

```
功能正确
```

继续执行：

```
pytest
```

得到：

```
FAILED
Expected: 5
Actual: -1
```

Agent 根据反馈修改：

```
def add(a, b):
    return a + b
```

再次运行：

```
pytest
```

得到：

```
PASSED
```

此时才能认为该修改真正经过环境验证。

#### 2.6 整体工作流程

```
LLM
↓
生成 Tool Call
↓
执行 Tool
↓
获得 Tool Result
↓
┌────────────────────────┐
│                        │
成功                    失败
│                        │
继续判断任务           捕获 Error
│                        ↓
│                  Feedback Injection
│                        ↓
│                      LLM
│                        ↓
│                 Error Diagnosis
│                        ↓
│                  read / edit
│                        ↓
│                     retry
│                        │
└───────────────←────────┘
        ↓
    Validation PASS
        ↓
    Final Answer
```

## 3、安全性

***本质***

对 Coding Agent 的文件访问、命令执行和代码修改行为进行风险控制，避免模型误操作影响真实环境，并保证关键修改具备可恢复性。

***组成：***

#### 3.1 Safety 权限控制

**概要：**

对 Agent 的 Tool Call 进行风险分级，判断当前操作是否可以直接执行。

实现方法：

在 `agent/safety.py` 中实现权限判断，根据操作类型返回：

```
ALLOW
CONFIRM
DENY
```

基本规则例如：

```
workspace 内文件读写
→ ALLOW

workspace 外普通文件操作
→ CONFIRM

高风险系统文件或危险命令
→ DENY
```

同时限制 Agent 默认只能操作指定的：

```
workspace/
```

并检查危险 Shell 命令，例如：

```
rm -rf /
shutdown
reboot
curl ... | bash
```

#### 3.2 用户授权机制

**概要：**

	对于具有一定风险但并非绝对禁止的操作，将最终决策权交给用户。

**实现方法：**

	`agent/safety.py` 负责判断是否需要人CONFIRM，`agent/loop.py` 负责暂停当前 Tool 执行并向用户请求授权。

用户允许则执行 Tool；用户拒绝则 返回 Permission Denied→ 将结果重新反馈给 LLM→ Agent 重新规划

**实例：**

Agent 希望执行：

```
pip install flask-jwt-extended
```

由于会修改当前运行环境：

```
Safety → CONFIRM
```

系统向用户申请授权，得到允许后才真正执行。

---

#### 3.3 Rollback / Checkpoint

概要：

	在文件修改之前保存 Workspace 的历史状态，使 Agent 修改错误或用户对结果不满意时可以恢复。

实现方法：

在 `agent/checkpoint.py` 中实现：

```
create_checkpoint()
rollback()
```

对于：

```
write_file
edit_file
delete_file
```

等修改性操作，在真正执行前创建 Checkpoint，历史数据保存storage/checkpoints/

实例：

```
Checkpoint 1
修改 main.py

Checkpoint 2
修改 auth.py

Checkpoint 3
修改 config.py
```

如果用户要求：

```
撤销刚才修改
```

则可以恢复到最近一个 Checkpoint。

---

#### 安全配置项

概要：

将安全规则集中配置，避免权限判断和危险命令规则散落在不同代码文件中。

实现方法：

在 `<span>config.py</span>` 中统一设置：

```
WORKSPACE = "./workspace"

MAX_AGENT_STEPS = 20

MAX_CHECKPOINTS = 5

CONFIRM_OUTSIDE_WORKSPACE = True

BLOCKED_COMMANDS = [
    "rm -rf /",
    "shutdown",
    "reboot"
]
```

这些配置分别控制：

```
Agent 可操作范围
最大自主执行轮数
Checkpoint 保留数量
越界访问授权策略
危险命令规则
```

实例：

可以根据不同运行环境设置不同安全等级：

```
开发模式
→ workspace 内修改自动允许

严格模式
→ 文件修改需要确认

只读模式
→ 禁止所有写操作
```

# 4.项目运行指导

初次使用请下载环境包：

	pip install -r requirements.txt

提供配置api：
	$env:AGENT_API_KEY="你的 API Key"  

（例如：$env:AGENT_API_KEY="sk-8e8216950a2e40608aca2efa8a3d7478"）

	$env:AGENT_BASE_URL="https://api.deepseek.com"
	$env:AGENT_MODEL="deepseek-chat"

运行:

	python main.py

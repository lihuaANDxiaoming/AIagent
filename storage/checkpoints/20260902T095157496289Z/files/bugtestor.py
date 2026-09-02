# test_bugs.py

# 手动复刻main内部环境，直接拿到内部函数，复现全部bug
def test_all_bugs():
    students = []

    # ========== Bug1：分数存字符串，计算平均分报TypeError ==========
    print("==== Bug1 测试：分数未转数字 ====")
    try:
        # 模拟add_student
        name = "张三"
        score = "85"   # 字符串，Bug1
        students.append({"name": name, "score": score})

        total = 0
        for s in students:
            total += s["score"]
        avg = total / len(students)
        print(f"平均分:{avg}")
    except Exception as e:
        print(f"捕获异常: {type(e).__name__}: {e}\n")

    # ========== Bug2：删除非法索引 IndexError ==========
    print("==== Bug2 测试：删除越界索引 ====")
    try:
        del students[999]  # 非法下标
        print("删除成功")
    except Exception as e:
        print(f"捕获异常: {type(e).__name__}: {e}\n")

    # ========== Bug3：空列表计算平均分 ZeroDivisionError ==========
    print("==== Bug3 测试：空学生列表求平均分 ====")
    students.clear()
    try:
        total = 0
        for s in students:
            total += s["score"]
        avg = total / len(students)
        print(f"平均分:{avg}")
    except Exception as e:
        print(f"捕获异常: {type(e).__name__}: {e}\n")

    # ========== Bug4：查询条件写反，逻辑错误，无异常 ==========
    print("==== Bug4 测试：查询条件写反 ====")
    students.append({"name":"王五","score":90})
    find_name = "王五"
    found = False
    for s in students:
        # 原bug代码：!=
        if s["name"] != find_name:
            print(f"找到学生：{s['name']}，分数：{s['score']}")
            found = True
            break
    if not found:
        print("输出：未找到该学生（明明存在，逻辑bug）\n")

    # ========== Bug5：save_to_file 局部变量覆盖外部students，保存为空 ==========
    print("==== Bug5 测试：save_to_file作用域bug ====")
    students.clear()
    students.append({"name":"赵六","score":78})
    # 复刻bug版save_to_file
    def save_to_file_bug():
        students = []   # bug：局部覆盖
        with open("score.txt","w",encoding="utf-8") as f:
            for s in students:
                f.write(f"{s['name']},{s['score']}\n")

    save_to_file_bug()
    # 读取文件
    with open("score.txt","r",encoding="utf-8") as f:
        txt = f.read()
    if len(txt.strip()) == 0:
        print("score.txt 为空！作用域bug生效\n")
    else:
        print("文件有内容，bug未复现\n")


if __name__ == "__main__":
    test_all_bugs()

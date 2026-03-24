# Rubric 字段复制助手

这是一个零依赖本地小工具，用来把 `rubrics_all.json` 直接拆成你表单里要填写的单独字段。

## 现在能做什么

- 自动扫描当前工作目录下的 rubric JSON 文件
- 按表单顺序拆分字段：`评分点 -> 类型 -> 得分 -> 来源 -> 引用 -> 说明`
- 支持复制单个字段
- 支持 `复制并前进`，一路顺着填写同一条 rubric
- 支持切换到上一条 / 下一条 rubric
- 支持复制整条字段包
- 支持按关键词筛选

## 最推荐的用法

1. 选择一个 rubric JSON
2. 点击左侧某条 rubric 的 `打开字段填写`
3. 在右侧按顺序填表
4. 每填完一个字段，就点一次 `复制并前进`
5. 填完整条后，继续下一条 rubric

## 快捷键

- `Enter`：复制当前字段并前进
- `↑`：回到上一个字段
- `↓`：前进到下一个字段

## 启动

在 `/Users/yanhanli/Desktop/labelease/search` 下运行：

```bash
python3 rubric_copy_tool/server.py
```

或者直接双击：

```text
/Users/yanhanli/Desktop/labelease/search/rubric_copy_tool/run.command
```

然后打开浏览器访问：

```text
http://127.0.0.1:8765
```

## 适用文件

默认会扫描当前目录及子目录下文件名包含 `rubric` 的 `.json` 文件。

## 说明

- 不依赖第三方包
- 不会改动原始 JSON
- 如果浏览器不允许直接写剪贴板，字段内容仍会显示在页面里，可以手动复制

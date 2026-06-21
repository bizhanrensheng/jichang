# 机场签到脚本使用说明

## 1. 项目用途

这个项目是一个基于 `Python + Playwright` 的机场签到自动化脚本。它会：

- 自动登录账号
- 自动进入签到页面
- 自动识别验证码并提交签到
- 支持多个账号顺序执行
- 可选推送签到结果到 `PushPlus`

项目里有两个入口：

- `checkin.py`：主脚本，支持前台/无头运行
- `checkin_headless.py`：后台启动器，用于静默运行

## 2. 环境要求

- Windows
- Python 3.10+（建议 3.11 或 3.12）
- 已安装 `pip`

## 3. 安装依赖

在项目目录执行：

```powershell
py -m pip install -U requests ddddocr playwright
py -m playwright install chromium
```

如果没有 `py`，可改用：

```powershell
python -m pip install -U requests ddddocr playwright
python -m playwright install chromium
```

## 4. 账号配置

### 方式一：直接修改脚本

在 `checkin.py` 里的 `ACCOUNTS` 数组中填写账号和密码：

```python
ACCOUNTS = [
    {"username": "账号1", "password": "密码1"},
    {"username": "账号2", "password": "密码2"},
]
```

### 方式二：使用环境变量

设置 `CHECKIN_ACCOUNTS`，支持两种格式：

- JSON 格式
- `username:password` 逗号分隔格式

示例：

```powershell
$env:CHECKIN_ACCOUNTS='[{"username":"账号1","password":"密码1"},{"username":"账号2","password":"密码2"}]'
```

或：

```powershell
$env:CHECKIN_ACCOUNTS='账号1:密码1,账号2:密码2'
```

## 5. PushPlus 推送（可选）

如果想接收签到结果通知，可以设置：

```powershell
$env:PUSHPLUS_TOKEN='你的PushPlusToken'
```

不设置也可以运行，只是不推送消息。

## 6. 运行方式

### 前台运行

```powershell
python checkin.py
```

### 无头运行

```powershell
python checkin.py --headless
```

### 后台运行

```powershell
python checkin_headless.py
```

后台启动后会生成：

- `checkin_headless.log`：运行日志
- `checkin_headless.pid`：进程号

## 7. 常用参数

`checkin.py` 支持这些参数：

- `--retries`：单个账号验证码重试次数，默认 `8`
- `--interval`：多个账号之间的等待秒数，默认 `1.5`
- `--headless`：无头模式运行
- `--slow`：页面关闭前保留的毫秒数，默认 `800`

示例：

```powershell
python checkin.py --headless --retries 10 --interval 2
```

## 8. 返回结果

脚本结束后会输出汇总信息，并尝试发送 PushPlus 通知。返回值含义大致如下：

- `0`：全部账号签到成功或已签到
- `1`：部分账号失败
- `2`：未配置账号

## 9. 常见问题

### 1）验证码识别失败

- 重新运行一次
- 增加 `--retries`
- 确认 `chromium` 已正确安装

### 2）登录后没有进入签到页

- 检查账号密码是否正确
- 确认网站地址可访问
- 查看 `checkin_headless.log` 或控制台输出

### 3）提示依赖缺失

重新执行依赖安装命令：

```powershell
py -m pip install -U requests ddddocr playwright
py -m playwright install chromium
```

## 10. 安全建议

- 不要把真实密码长期明文提交到仓库
- 更推荐使用环境变量管理账号信息
- `PushPlus Token` 也建议单独保存，不要公开


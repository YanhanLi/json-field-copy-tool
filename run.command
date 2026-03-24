#!/bin/zsh
set -e
cd /Users/yanhanli/Desktop/labelease/search
printf 'JSON 字段复制工具正在启动...\n'
printf '优先使用 http://127.0.0.1:8765；如果端口占用，会自动切换到别的可用端口。\n'
printf '请以终端里打印出来的实际地址为准。\n\n'
python3 rubric_copy_tool/server.py

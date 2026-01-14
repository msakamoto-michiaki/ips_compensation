#!/bin/bash
#
git config --global user.email "msakamoto.michiaki@gmail.com"
git config --global user.name "msakamoto-michiaki"

# ③ すべてのファイルをステージングに追加
git add .

# ④ 最初のコミット
git commit -m "initial commit"

# ⑤ リモートリポジトリ（GitHub）を登録
# ※ [コピーしたURL] の部分は先ほどGitHubでコピーしたものに書き換えてください
git remote add origin https://github.com/msakamoto-michiaki/ips_compensation.git

# ⑥ GitHubへ送信（Push）
#git branch -M main
git push -u origin main

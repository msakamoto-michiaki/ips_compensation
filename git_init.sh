#!/bin/bash
#
# ① ディレクトリに移動
cd /Users/sakamotomichiaki/work/git/ips_compensation

# ② Gitリポジトリとして初期化（すでに行っている場合はスキップ可）
git init

# ③ すべてのファイルをステージングに追加
git add .

# ④ 最初のコミット
git commit -m "initial commit"

# ⑤ リモートリポジトリ（GitHub）を登録
# ※ [コピーしたURL] の部分は先ほどGitHubでコピーしたものに書き換えてください
git remote add origin https://github.com/msakamoto-michiaki/ips_compensation.git

# ⑥ GitHubへ送信（Push）
git branch -M main
git push -u origin main

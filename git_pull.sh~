#!/bin/bash
#./git_sync.sh "修正内容のメモ"
#
# 1. すべての変更をステージング
git add .
# 2. コミットメッセージを受け取ってコミット
# メッセージが空の場合は "update" とする
msg=${1:-"update"}
git commit -m "$msg"

# 3. GitHubへPush
git push origin main

#!/bin/bash
# Markdown图片本地化Skill实现

set -e

if [ $# -ne 1 ]; then
    echo "❌ 用法错误"
    echo "正确用法: /md-img-local <markdown文件路径>"
    echo "示例: /md-img-local \"某百万DAU游戏的服务端优化工作.md\""
    exit 1
fi

MD_FILE="$1"
if [ ! -f "$MD_FILE" ]; then
    echo "❌ 错误: 文件 '$MD_FILE' 不存在"
    exit 1
fi

# 创建唯一的临时文件（基于PID，确保并发安全）
TEMP_FILE=$(mktemp /tmp/img_urls_XXXXXX.txt)
# 清理函数：清理临时文件和可能的残留脚本文件
cleanup() {
    rm -f "$TEMP_FILE"
    # 清理可能的残留脚本文件
    rm -f "$(dirname "$MD_FILE")/download_images.sh"
    rm -f "$(dirname "$MD_FILE")/replace_links.py"
}
trap "cleanup" EXIT

# 提取文件的绝对路径，计算哈希确保前缀唯一性
MD_ABS=$(cd "$(dirname "$MD_FILE")" && pwd)/$(basename "$MD_FILE")
PATH_HASH=$(echo -n "$MD_ABS" | md5sum | cut -c1-8)

# 提取文件名作为前缀（不带后缀，清理特殊字符）并与路径哈希拼接
BASE_PREFIX=$(basename "$MD_FILE" .md | tr ' ' '_' | sed 's/[^a-zA-Z0-9_\u4e00-\u9fa5]//g')
PREFIX="${BASE_PREFIX}_${PATH_HASH}"

# 创建assets目录
mkdir -p assets
echo "✅ 创建assets目录完成"

# 提取所有网络图片链接（去重）
grep -o '!\[.*\](https\?://[^)]*)' "$MD_FILE" | grep -o 'https\?://[^)]*' | sort | uniq > "$TEMP_FILE"

COUNT=$(wc -l < "$TEMP_FILE")
if [ "$COUNT" -eq 0 ]; then
    echo "ℹ️ 未找到任何网络图片，无需处理"
    exit 0
fi

echo "🔍 找到 $COUNT 张网络图片"

# 下载并替换
INDEX=1
SUCCESS_COUNT=0
FAILURE_COUNT=0

while read -r URL; do
    # 提取原文件名
    FILENAME=$(basename "$URL" | cut -d'?' -f1)
    EXT="${FILENAME##*.}"
    if [ "$EXT" = "$FILENAME" ] || [ -z "$EXT" ]; then
        EXT="jpg"
        FILENAME="${FILENAME}.jpg"
    fi

    # 新文件名：前缀_序号_原文件名，确保唯一
    NEW_FILENAME="${PREFIX}_${INDEX}_${FILENAME}"
    NEW_PATH="assets/${NEW_FILENAME}"

    echo -n "📥 下载 ($INDEX/$COUNT): $URL -> $NEW_PATH ... "

    # 下载图片，重试2次
    if curl -s --retry 2 -o "$NEW_PATH" "$URL"; then
        # 替换原文件中的链接（使用原子性操作：写临时文件 + mv）
        sed "s|$URL|$NEW_PATH|g" "$MD_FILE" > "${MD_FILE}.tmp_$$" && mv "${MD_FILE}.tmp_$$" "$MD_FILE"
        echo "✅ 成功"
        SUCCESS_COUNT=$((SUCCESS_COUNT+1))
    else
        echo "❌ 失败"
        FAILURE_COUNT=$((FAILURE_COUNT+1))
    fi

    INDEX=$((INDEX+1))
done < "$TEMP_FILE"

echo -e "\n🎉 处理完成！"
echo "✅ 成功下载: $SUCCESS_COUNT 张"
if [ "$FAILURE_COUNT" -gt 0 ]; then
    echo "❌ 下载失败: $FAILURE_COUNT 张"
fi
echo "📝 所有图片已保存到 assets/ 目录，原文件链接已更新为本地路径"

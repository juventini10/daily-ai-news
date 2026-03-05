#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests, re, os, sys
from datetime import datetime

def get_news():
    """聚合多个国内可访问源，智能过滤非AI内容"""
    sources = [
        ("少数派", "https://sspai.com/feed"),
        ("36氪", "https://36kr.com/feed"),
        ("知乎AI话题", "https://www.zhihu.com/rss")
    ]
    
    all_items = []
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; GitHubActions/1.0; +https://github.com/actions)'}
    
    for name, url in sources:
        try:
            resp = requests.get(url, headers=headers, timeout=8, verify=False)
            resp.encoding = 'utf-8'
            # 提取<title>标签内容（简化版RSS解析）
            titles = re.findall(r'<title>([^<]+)</title>', resp.text)
            links = re.findall(r'<link[^>]*>(https?://[^<]+)</link>', resp.text)
            # 合并标题+链接（跳过频道标题）
            for i in range(1, min(len(titles), len(links))):
                title = titles[i].strip()
                # 智能过滤：保留含AI关键词的内容
                if any(kw in title.lower() for kw in ['ai', '人工智能', '大模型', '机器学习', '深度学习', '算法']):
                    all_items.append(f"[{title}]({links[i]}) | 来源：{name}")
        except Exception as e:
            print(f"⚠️ {name}源失败: {str(e)[:50]}")
    
    # 去重 + 截取前5条
    unique_items = list(dict.fromkeys(all_items))[:5]
    
    if not unique_items:
        return "🔍 今日暂无AI相关资讯（已扫描少数派/36氪/知乎）\n💡 尝试关键词：大模型、芯片、AIGC"
    
    content = "**✨ 今日AI精选（智能聚合）**\n" + "\n".join(f"{i+1}. {item}" for i, item in enumerate(unique_items))
    content += f"\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')} | GitHub Actions自动推送"
    return content

if __name__ == "__main__":
    webhook = os.getenv("FEISHU_WEBHOOK")
    if not webhook:
        print("❌ 错误：未设置 FEISHU_WEBHOOK Secret！", file=sys.stderr)
        sys.exit(1)
    
    content = get_news()
    
    # 飞书消息（简化版，避免卡片格式问题）
    payload = {
        "msg_type": "text",
        "content": {"text": content}
    }
    
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("code") == 0:
            print("✅ 飞书推送成功！")
            sys.exit(0)
        else:
            print(f"❌ 推送失败: {resp.text}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"⚠️ 网络异常: {str(e)}", file=sys.stderr)
        sys.exit(1)

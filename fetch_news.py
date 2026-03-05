#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import feedparser, os, requests, sys

def get_news(rss_url, count=5):
    try:
        feed = feedparser.parse(rss_url)
        if not feed.entries: return "❌ 无新闻数据"
        lines = ["**✨ 今日AI精选（来源：机器之心）**"]
        for i, e in enumerate(feed.entries[:count], 1):
            title = e.title.replace("\n", " ").strip().replace("(", "（").replace(")", "）")
            lines.append(f"{i}. [{title}]({e.link})")
        lines.append("\n💡 回复「领域」定制推送（如：大模型/芯片）")
        return "\n".join(lines)
    except Exception as ex:
        return f"⚠️ RSS解析失败: {str(ex)}"

if __name__ == "__main__":
    webhook = os.getenv("FEISHU_WEBHOOK")
    if not webhook:
        print("❌ 错误：未设置 FEISHU_WEBHOOK Secret！", file=sys.stderr)
        sys.exit(1)
    
    content = get_news(os.getenv("RSS_URL", "https://rsshub.app/tophub/ai"))
    
    # 构造飞书交互式卡片（避免纯文本截断）
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "📰 每日AI要闻"}, "template": "blue"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "🤖 GitHub Actions自动推送 | " + __file__}]}
            ]
        }
    }
    
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("code") == 0:
            print("✅ 飞书消息推送成功！")
            sys.exit(0)
        else:
            print(f"❌ 推送失败: {resp.text}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"⚠️ 网络异常: {str(e)}", file=sys.stderr)
        sys.exit(1)

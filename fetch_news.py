#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import feedparser, re, os, sys, requests
from datetime import datetime, timedelta, timezone

# === AI摘要模块（通义千问）===
DASHSCOPE_AVAILABLE = False
try:
    import dashscope
    from dashscope import Generation
    DASHSCOPE_AVAILABLE = True
except ImportError:
    print("ℹ️ 未安装dashscope（AI摘要将跳过）")

def ai_summarize(text, api_key):
    """通义千问重写摘要｜30字口语化｜失败自动回退"""
    if not text or len(text) < 15 or not api_key or not DASHSCOPE_AVAILABLE:
        return None
    
    prompt = (
        "你是一名科技编辑，请用30字口语化总结：\n"
        "1. 避免专业术语 2. 突出价值点 3. 带情绪钩子（如'炸了''稳了'）\n"
        f"原文：{text[:300]}"
    )
    
    try:
        dashscope.api_key = api_key
        resp = Generation.call(
            model='qwen-turbo',  # 低成本高速模型（1元≈10万字）
            prompt=prompt,
            temperature=0.85,
            top_p=0.9,
            timeout=5
        )
        if resp.status_code == 200 and resp.output and resp.output.text:
            res = resp.output.text.strip()
            # 清洗多余标点/空格
            res = re.sub(r'^[^\w]+|[^\w]+$', '', res)
            return res if 10 <= len(res) <= 60 else None
    except Exception as e:
        print(f"⚠️ AI摘要失败: {str(e)[:40]}")
    return None

def clean_html(text):
    """清洗HTML标签 + 精简摘要"""
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', str(text))
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:120]  # 原摘要保留稍长（供AI参考）

def get_news():
    """8条24h新闻 + AI重写摘要 + 时效验证"""
    sources = [
        ("36氪AI", "https://36kr.com/feed"),
        ("IT之家AI", "https://www.ithome.com/feed"),
        ("雷锋网", "https://www.leiphone.com/feed"),
        ("量子位", "https://www.qbitai.com/feed"),
        ("机器之心", "https://www.jiqizhixin.com/rss"),
        ("InfoQ AI", "https://www.infoq.cn/feed"),
        ("AI科技评论", "https://www.leiphone.com/feed"),
        ("新智元", "https://www.aixinzhijie.com/rss")
    ]
    
    ai_keywords = ['ai', '人工智能', '大模型', '机器学习', '深度学习', 'aigc', '生成式', 
                  '芯片', 'gpu', 'llm', '自动驾驶', '计算机视觉', 'nlp', '语音识别', '机器人']
    
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=24)
    valid_items = []
    ai_api_key = os.getenv("DASHSCOPE_API_KEY")  # 仅此处获取一次
    
    for name, url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # === 时间验证 ===
                pub_time = None
                for time_attr in ['published_parsed', 'updated_parsed']:
                    if hasattr(entry, time_attr) and getattr(entry, time_attr):
                        t = getattr(entry, time_attr)
                        try:
                            pub_time = datetime(t.tm_year, t.tm_mon, t.tm_mday, 
                                              t.tm_hour, t.tm_min, t.tm_sec, tzinfo=timezone.utc)
                            break
                        except: continue
                if not pub_time or pub_time < cutoff or pub_time > now_utc:
                    continue
                
                # === 标题清洗 ===
                title = re.sub(r'[\r\n\t]+', ' ', entry.title).strip()
                if len(title) < 15: continue
                if any(skip in title.lower() for skip in ['rss', '订阅', '公告', '招聘', '广告']):
                    continue
                if not any(kw in title.lower() for kw in ai_keywords):
                    continue
                
                # === 原始摘要提取 ===
                raw_summary = ""
                for field in ['summary', 'description', 'content']:
                    val = getattr(entry, field, None)
                    if val:
                        if isinstance(val, list) and len(val) > 0:
                            val = val[0].get('value', '')
                        raw_summary = clean_html(str(val))
                        if raw_summary and len(raw_summary) > 15:
                            break
                
                # === AI重写摘要（核心！）===
                final_summary = "💡 点击链接查看全文（含技术细节/行业影响）"
                if raw_summary:
                    ai_summary = ai_summarize(raw_summary, ai_api_key) if ai_api_key else None
                    final_summary = ai_summary if ai_summary else raw_summary[:80] + "..."
                
                # === 生成新闻条目 ===
                hours_ago = int((now_utc - pub_time).total_seconds() // 3600)
                time_tag = f"🔥{hours_ago}h" if hours_ago < 2 else f"⏰{hours_ago}h"
                item_text = (
                    f"{time_tag} **[{title}]({entry.link})** | {name}\n"
                    f"   └ {final_summary}"
                )
                valid_items.append({'time': pub_time, 'content': item_text})
        except Exception as e:
            print(f"⚠️ {name}解析失败: {str(e)[:40]}")
    
    # === 排序 + 去重 + 限8条 ===
    valid_items.sort(key=lambda x: x['time'], reverse=True)
    seen_titles = set()
    final_items = []
    for item in valid_items:
        title_key = re.search(r'\[(.*?)\]', item['content'])
        key = title_key.group(1)[:50] if title_key else item['content'][:50]
        if key not in seen_titles and len(final_items) < 8:
            seen_titles.add(key)
            final_items.append(item['content'])
    
    # === 生成最终消息 ===
    if not final_items:
        return ("🔍 今日暂无24小时内AI新闻（已扫描8大源）\n"
                "💡 可能原因：节假日/源更新延迟 | 下次推送将自动补全")
    
    content = (
        "**📰 今日AI快讯（8条·严格24h）**\n"
        "━━━━━━━━━━━━━━━━━━\n" +
        "\n\n".join(final_items) +
        f"\n\n✅ 时效验证：仅含{cutoff.strftime('%m-%d %H:%M')}后发布内容"
        "\n🤖 摘要说明：通义千问AI重写｜点击链接查看全文"
    )
    return content

if __name__ == "__main__":
    webhook = os.getenv("FEISHU_WEBHOOK")
    if not webhook:
        print("❌ 错误：未设置 FEISHU_WEBHOOK Secret！", file=sys.stderr)
        sys.exit(1)
    
    content = get_news()
    
    # 飞书Markdown卡片
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📰 今日AI快讯（AI摘要版）"},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {"tag": "note", "elements": [
                    {"tag": "plain_text", "content": f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')} | GitHub Actions自动推送"}
                ]}
            ]
        }
    }
    
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        news_count = content.count("**[")
        if resp.status_code == 200 and resp.json().get("code") == 0:
            ai_status = "✨AI摘要已启用" if os.getenv("DASHSCOPE_API_KEY") else "ℹ️未配置AI（使用原摘要）"
            print(f"✅ 推送成功！{news_count}条新闻 | {ai_status}")
            sys.exit(0)
        else:
            print(f"❌ 推送失败: {resp.text}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"⚠️ 异常: {str(e)}", file=sys.stderr)
        sys.exit(1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import feedparser, re, os, sys, requests
from datetime import datetime, timedelta, timezone

def clean_html(text):
    """清洗HTML标签 + 精简摘要"""
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', str(text))  # 移除HTML标签
    text = re.sub(r'\s+', ' ', text).strip()   # 合并空白字符
    return text[:80] + "..." if len(text) > 80 else text  # 截断80字符

def get_news():
    """8条24h新闻 + 智能摘要 + 时效验证"""
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
    
    for name, url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # === 时间验证（核心）===
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
                
                # === 标题清洗 + 关键词过滤 ===
                title = re.sub(r'[\r\n\t]+', ' ', entry.title).strip()
                if len(title) < 15: continue
                if any(skip in title.lower() for skip in ['rss', '订阅', '公告', '招聘', '广告']):
                    continue
                if not any(kw in title.lower() for kw in ai_keywords):
                    continue
                
                # === 摘要提取（核心新增）===
                summary = ""
                # 优先尝试summary/description字段
                for field in ['summary', 'description', 'content']:
                    val = getattr(entry, field, None)
                    if val:
                        if isinstance(val, list) and len(val) > 0:
                            val = val[0].get('value', '')
                        summary = clean_html(str(val))
                        if summary and len(summary) > 10:  # 有效摘要需>10字符
                            break
                
                # 无摘要时生成智能提示
                if not summary or len(summary) < 15:
                    summary = "💡 点击链接查看全文（含技术细节/行业影响）"
                
                # === 生成带摘要的新闻条目 ===
                hours_ago = int((now_utc - pub_time).total_seconds() // 3600)
                time_tag = f"🔥{hours_ago}h" if hours_ago < 2 else f"⏰{hours_ago}h"
                item_text = (
                    f"{time_tag} **[{title}]({entry.link})** | {name}\n"
                    f"   └ {summary}"
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
        if key not in seen_titles and len(final_items) < 8:  # 🔑 改为8条
            seen_titles.add(key)
            final_items.append(item['content'])
    
    # === 生成最终消息 ===
    if not final_items:
        return ("🔍 今日暂无24小时内AI新闻（已扫描8大源）\n"
                "💡 可能原因：节假日/源更新延迟 | 下次推送将自动补全")
    
    content = (
        "**📰 今日AI快讯（8条·严格24小时内）**\n"
        "━━━━━━━━━━━━━━━━━━\n" +
        "\n\n".join(final_items) +  # 用双换行分隔，提升可读性
        f"\n\n✅ 时效验证：仅含{cutoff.strftime('%m-%d %H:%M')}后发布内容"
        "\n🤖 摘要说明：自动提取RSS摘要｜点击链接查看全文"
    )
    return content

if __name__ == "__main__":
    webhook = os.getenv("FEISHU_WEBHOOK")
    if not webhook:
        print("❌ 错误：未设置 FEISHU_WEBHOOK Secret！", file=sys.stderr)
        sys.exit(1)
    
    content = get_news()
    
    # 飞书Markdown卡片（优化排版｜避免纯文本截断）
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📰 今日AI快讯（8条）"},
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
        if resp.status_code == 200 and resp.json().get("code") == 0:
    news_count = content.count("**[")  # ✅ 安全估算条数（基于已生成的content）
    print(f"✅ 推送成功！{news_count}条24h内新闻（含摘要）已发送至飞书")
    sys.exit(0)
        else:
            print(f"❌ 推送失败: {resp.text}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"⚠️ 异常: {str(e)}", file=sys.stderr)
        sys.exit(1)

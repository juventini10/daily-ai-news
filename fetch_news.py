#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import feedparser, re, os, sys
from datetime import datetime, timedelta, timezone

def get_news():
    """严格24小时新闻过滤｜自动跳过无时间/旧文章"""
    sources = [
        ("36氪AI", "https://36kr.com/feed"),
        ("IT之家AI", "https://www.ithome.com/feed"),
        ("雷锋网", "https://www.leiphone.com/feed"),
        ("量子位", "https://www.qbitai.com/feed"),
        ("机器之心", "https://www.jiqizhixin.com/rss")
    ]
    
    ai_keywords = ['ai', '人工智能', '大模型', '机器学习', '深度学习', 'aigc', '生成式', 
                  '芯片', 'gpu', 'llm', '自动驾驶', '计算机视觉', 'nlp', '语音识别']
    
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=24)  # 24小时前的UTC时间
    valid_items = []
    
    for name, url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # === 1. 严格时间验证（核心！）===
                pub_time = None
                # 优先用published，其次updated
                for time_attr in ['published_parsed', 'updated_parsed']:
                    if hasattr(entry, time_attr) and getattr(entry, time_attr):
                        t = getattr(entry, time_attr)
                        try:
                            pub_time = datetime(t.tm_year, t.tm_mon, t.tm_mday, 
                                              t.tm_hour, t.tm_min, t.tm_sec, tzinfo=timezone.utc)
                            break
                        except: continue
                
                # 跳过无时间/超时文章
                if not pub_time or pub_time < cutoff or pub_time > now_utc:
                    continue
                
                # === 2. 标题清洗 + 关键词过滤 ===
                title = re.sub(r'[\r\n\t]+', ' ', entry.title).strip()
                if len(title) < 15: continue  # 过滤标题过短
                if any(skip in title.lower() for skip in ['rss', '订阅', '公告', '招聘']):
                    continue
                if not any(kw in title.lower() for kw in ai_keywords):
                    continue
                
                # === 3. 生成带时效标记的内容 ===
                hours_ago = int((now_utc - pub_time).total_seconds() // 3600)
                time_tag = f"🔥{hours_ago}h" if hours_ago < 2 else f"⏰{hours_ago}h"
                valid_items.append({
                    'time': pub_time,
                    'content': f"{time_tag} [{title}]({entry.link}) | {name}"
                })
        except Exception as e:
            print(f"⚠️ {name}解析失败: {str(e)[:40]}")
    
    # === 4. 按时间倒序 + 去重 ===
    valid_items.sort(key=lambda x: x['time'], reverse=True)
    seen = set()
    final_items = []
    for item in valid_items:
        key = re.sub(r'\[.*?\]\(.*?\)', '', item['content']).strip()[:60]
        if key not in seen and len(final_items) < 5:
            seen.add(key)
            final_items.append(item['content'])
    
    # === 5. 生成结果 ===
    if not final_items:
        return ("🔍 今日暂无24小时内AI新闻（已扫描5大源）\n"
                "💡 可能原因：节假日/源更新延迟 | 下次推送将自动补全")
    
    content = "**📰 今日AI快讯（严格24小时内·实时更新）**\n" + "\n".join(final_items)
    content += f"\n\n✅ 时效验证：仅含{cutoff.strftime('%m-%d %H:%M')}后发布内容"
    return content

if __name__ == "__main__":
    webhook = os.getenv("FEISHU_WEBHOOK")
    if not webhook:
        print("❌ 错误：未设置 FEISHU_WEBHOOK Secret！", file=sys.stderr)
        sys.exit(1)
    
    content = get_news()
    payload = {"msg_type": "text", "content": {"text": content}}
    
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("code") == 0:
            count = content.count("http")
            print(f"✅ 推送成功！{len([l for l in content.split('\\n') if 'http' in l])}条24h内新闻")
            sys.exit(0)
        else:
            print(f"❌ 推送失败: {resp.text}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"⚠️ 异常: {str(e)}", file=sys.stderr)
        sys.exit(1)

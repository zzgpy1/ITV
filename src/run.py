# src/run.py (只列出关键修改部分)

async def run_legacy_mode():
    # ... 前面代码不变 ...

    # 5. 强制使用固定源（从数据库读取，覆盖所有频道）
    all_stable = await stable_mgr.get_stable_sources()
    if all_stable:
        # 只取固定源 (is_fixed=True)
        fixed_sources = {name: src for name, src in all_stable.items() if src.get('is_fixed', False)}
        if fixed_sources:
            matcher = get_alias_matcher()
            fixed_count = 0
            for ch in ordered_channels:
                raw_name = ch.get('name')
                if not raw_name:
                    continue
                std_name = matcher.normalize(raw_name) if matcher else raw_name
                if std_name in fixed_sources:
                    src = fixed_sources[std_name]
                    # 强制覆盖 URL
                    ch['url'] = src['url']
                    ch['latency'] = src.get('latency', 50)
                    ch['video_codec'] = src.get('video_codec', 'h264')
                    ch['is_fixed'] = True
                    if 'urls' in ch:
                        if src['url'] not in ch['urls']:
                            ch['urls'] = [src['url']] + [u for u in ch['urls'] if u != src['url']]
                    fixed_count += 1
                    logger.info(f"🔄 固定源强制覆盖: {std_name} -> {src['url'][:50]}...")
            logger.info(f"📌 固定源强制覆盖完成: {fixed_count} 个频道")

    # 6. 生成输出（保持不变）
    generate_outputs_from_demo(ordered_channels, demo_order)
    # ... 后续代码 ...

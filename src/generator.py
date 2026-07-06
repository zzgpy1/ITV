def generate_m3u_by_demo_order(
    channels_by_name: Dict[str, dict],
    demo_order: List[Tuple[str, str]],
    extra_channels: List[dict],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        # 先输出所有 demo 中的频道（按顺序）
        # 同时记录已经输出过的分类（用于合并额外频道）
        outputted_categories = set()
        # 存储每个分类下已输出的频道（用于排序，但这里直接按顺序）
        for cat, demo_name in demo_order:
            clean_cat = cat.replace(",#genre#", "").strip()
            f.write(f'#EXTINF:-1 group-title="{clean_cat}",{demo_name}\n')
            # 但这里需要获取频道URL，而不是直接写demo_name
            # 我们得从channels_by_name中获取
        # 重新设计：先循环demo_order，输出匹配的频道
        # 但为了合并，我们需要先输出所有匹配频道，同时记录分类
        # 然后处理extra_channels
        # 我们可以先构建一个有序的分类列表
        category_order = []
        for cat, _ in demo_order:
            clean_cat = cat.replace(",#genre#", "").strip()
            if clean_cat not in category_order:
                category_order.append(clean_cat)
        
        # 第一遍：输出匹配的频道
        # 为了不重复写分类标题，我们可以记录当前分类
        current_cat = None
        for cat, demo_name in demo_order:
            clean_cat = cat.replace(",#genre#", "").strip()
            channel = channels_by_name.get(demo_name)
            if channel:
                url = get_first_url(channel)
                if url:
                    # 如果分类变化，写分类标题
                    if clean_cat != current_cat:
                        f.write(f'\n# ----- {clean_cat} -----\n')
                        current_cat = clean_cat
                    name = channel.get("name", demo_name)
                    f.write(f'#EXTINF:-1 group-title="{clean_cat}",{name}\n')
                    f.write(f"{url}\n")
        
        # 第二遍：处理 extra_channels，按分类分组
        if extra_channels:
            # 分组
            grouped = defaultdict(list)
            for ch in extra_channels:
                cat = ch.get("demo_category", ch.get("group_title", "其他"))
                grouped[cat].append(ch)
            
            # 按分类顺序输出：先按category_order顺序，再按字母
            # 但为了合并，我们优先将extra_channels追加到已存在的分类
            # 已存在的分类即为category_order中的分类
            # 我们按category_order顺序输出，并在每个分类的尾部追加该分类的extra_channels
            # 然后再处理不在category_order中的分类
            
            # 先处理已存在的分类
            for cat in category_order:
                if cat in grouped and grouped[cat]:
                    # 如果当前分类已经输出过（由demo匹配输出），则直接追加，不再写标题
                    # 但为了确保标题存在，如果之前没有输出过任何频道，但当前分类有extra频道，我们要写标题
                    # 简单处理：不管是否已输出，我们都先确保标题存在，但可能会重复
                    # 更好的方式：在输出demo匹配时已经写了标题，这里只需追加频道
                    # 我们可以在输出demo匹配时保存已输出分类列表，然后这里追加
                    # 但我们没有保存，所以可以在这里判断如果该分类之前没有输出过，则写标题
                    # 由于我们可能先输出所有demo匹配，然后才处理extra，我们可以先输出所有demo匹配，然后再处理extra时，
                    # 对于每个分类，先检查该分类是否已经输出过（通过标志变量）
                    
                    # 我们重构：先输出所有demo匹配，并记录已经输出过的分类，然后处理extra时，如果分类已输出则直接追加，否则写标题。
                    
                    # 由于前面的循环已经输出了匹配频道，且可能写了标题，但我们现在无法知道标题是否已写。
                    # 更好的办法：先构建一个按分类顺序的完整频道列表，然后统一输出。
        
        # 我们采用另一种方式：先构建一个按分类顺序的完整频道列表。
        # 但为了简单，我们按如下方式：
        # 1. 先输出所有 demo 匹配的频道，同时记录输出过的分类。
        # 2. 然后处理 extra_channels，对于每个分类，如果该分类已经输出过，则直接追加（不写标题），否则写标题后追加。
        # 这样合并分类。

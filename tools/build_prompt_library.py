# -*- coding: utf-8 -*-
"""生成 Stable Diffusion 交互式提示词卡片库（单文件 HTML）。"""
import json, re, html as _html

# ---------------------------------------------------------------- 前 100 条
LEGACY = [
 ("人像与人物", "portrait of a young woman, long wavy hair, (freckles:1.2), soft smile, cinematic lighting, 85mm portrait, shallow depth of field, photorealistic, masterpiece, best quality", "用 (词:1.2) 强化雀斑细节；85mm 人像镜头 + 浅景深控制虚化。"),
 ("人像与人物", "(close-up:1.3) of an elderly fisherman, weathered skin, deep wrinkles, sea wind in hair, golden hour, dramatic rim light, 8k, ultra-detailed", "给构图词 close-up 加权拉近；weathered/wrinkles 堆质感，rim light 勾轮廓。"),
 ("人像与人物", "a girl, (iriya:1.1), school uniform, cherry blossom petals, anime style, cel shading, vibrant colors, studio lighting", "角色名/触发词单独加权，常用于角色 LoRA 与 Textual Inversion；cel shading 指定平涂。"),
 ("人像与人物", "full body shot, female warrior in ornate silver armor, holding a glowing spear, confident pose, dramatic backlight, fantasy, concept art, ArtStation trending", "full body 锁定全身构图；概念艺术 + 平台热词提升风格倾向。"),
 ("人像与人物", "a man in business suit, confident, city skyline bokeh background, (looking at viewer:1.2), professional headshot, softbox lighting, photorealistic", "对视线方向加权，比反复写 face/eyes 更稳；softbox 指定商业布光。"),
 ("人像与人物", "woman with (rainbow hair:1.2), cyberpunk fashion, neon reflections on skin, night, futuristic, synthwave, hyperdetailed", "非现实发色必须加权才不易被模型「纠正」回自然色。"),
 ("人像与人物", "baby laughing, chubby cheeks, soft blanket, warm window light, adorable, realistic, shallow DOF, bokeh", "情绪动词 laughing + 可爱度词共同驱动表情；暖窗光定调。"),
 ("人像与人物", "[old man:young man:0.5], standing in a field, oil painting style, visible brush strokes", "[from:to:0.5] 分步替换：前 50% 步画老人、后 50% 画青年，得到融合年龄。"),
 ("人像与人物", "(face focus:1.4), asian woman, elegant, traditional hanfu, red and gold, soft studio light, 8k, highly detailed skin", "把抽象构图意图 face focus 当成可加权词，配合皮肤质感词。"),
 ("人像与人物", "crowd of diverse people, street photography, candid, natural lighting, 35mm, documentary style, grain", "纪实摄影调性靠 documentary + grain；35mm 广角交代环境。"),
 ("人像与人物", "woman, (silhouette:1.2), backlit by sunset, rim lighting, dramatic, moody atmosphere, cinematic", "剪影 + 逆光组合，用少量词建立强情绪。"),
 ("人像与人物", "male elf archer, intricate leather armor, glowing arrow, ancient forest, dappled light, fantasy illustration, sharp focus", "幻想角色给「道具 + 材质 + 光斑」三件套，比空写 fantasy 更具体。"),
 ("人像与人物", "(split screen:1.1), left side calm, right side angry, same person, studio lighting, photorealistic", "把分屏当作构图词加权，左右语义用逗号并列描述。"),
 ("人像与人物", "a portrait in the style of (Leonardo da Vinci:1.2) and (modern photography:0.8), sfumato, soft light, renaissance", "多风格分别给主次权重；sfumato 这类专业术语能精准调风格。"),
 ("人像与人物", "woman with glasses, reading a book, cozy cafe, warm ambient light, depth of field, photorealistic, 8k", "日常场景靠「动作 + 环境光」建立生活感，不必堆画质词。"),

 ("风景与自然", "(mountain landscape:1.3), snow-capped peaks, alpine lake reflection, golden hour, dramatic clouds, national geographic, ultra-wide, 8k", "主体加权 + 倒影构图 + 杂志级风格词，风景三板斧。"),
 ("风景与自然", "tropical beach, turquoise water, white sand, palm trees, clear sky, bright sunlight, vacation photo, wide angle, highly detailed", "用具体颜色词 turquoise 而非 blue，色彩更可控。"),
 ("风景与自然", "forest path, ancient trees, fog, (god rays:1.2), mystical atmosphere, cinematic lighting, photorealistic", "雾 + 耶稣光加权，是神秘森林最省词的配方。"),
 ("风景与自然", "(aerial view:1.2), winding river through canyon, red rock formations, sunset, drone photography, ultra-detailed", "视角词前置并加权，直接决定整张图的透视。"),
 ("风景与自然", "(aurora borealis:1.3) over snowy mountains, starry sky, milky way, long exposure, night photography, 8k", "极光加权；long exposure 触发长曝光夜景质感。"),
 ("风景与自然", "desert dunes, camel caravan, heat haze, sunset, golden sand, cinematic, vast scale, ultra-wide shot", "heat haze 制造热浪扰动；vast scale 拉宏大尺度。"),
 ("风景与自然", "japanese garden, koi pond, cherry blossoms, stone lantern, soft light, peaceful, photorealistic, shallow depth of field", "文化元素清单式罗列，配合「平和」情绪词统一氛围。"),
 ("风景与自然", "(waterfall:1.2) in lush rainforest, mist, ferns, tropical birds, vibrant green, bright, ultra-detailed", "水雾 + 植被层次 + 色彩饱和度一起写。"),
 ("风景与自然", "autumn forest, red and orange leaves, sunbeams through trees, ground covered in leaves, warm tones, peaceful, 8k", "季节色 + warm tones 全局定调，避免颜色打架。"),
 ("风景与自然", "icelandic black sand beach, dramatic waves, basalt columns, overcast sky, moody, cinematic wide shot", "写具体地名/地貌，比泛写 beach 更有辨识度。"),
 ("风景与自然", "(underwater scene:1.2), coral reef, tropical fish, crystal clear water, sun rays from surface, hyperdetailed", "水下场景要补「水面入射光」，否则容易发灰。"),
 ("风景与自然", "rolling hills at dawn, dewy grass, soft pink sky, mist in valleys, peaceful, landscape photography, 8k", "黎明柔光 + 露水细节，靠时间词控制色温。"),
 ("风景与自然", "(volcano eruption:1.3), lava flowing, smoke plume, night, dramatic red glow, cinematic, ultra-wide", "灾害主体强加权，再用单一红光统一夜景。"),
 ("风景与自然", "misty mountains layered in the distance, traditional chinese ink painting style, minimal, elegant, negative space", "水墨风 + negative space 留白，减法构图。"),
 ("风景与自然", "field of lavender, endless purple rows, provence, golden hour, bees, dreamy, photorealistic, ultra-detailed", "地名 Provence 触发典型色彩记忆；bees 增加细节密度。"),

 ("动物与生物", "majestic lion, african savanna, tall grass, golden hour, intense gaze, wildlife photography, 600mm lens, sharp", "600mm 长焦是野生动物摄影的标志性写法。"),
 ("动物与生物", "(eagle in flight:1.2), wings spread wide, mountain backdrop, dramatic sky, motion blur on wings, hyperdetailed", "动作加权 + 局部运动模糊，静态图也能有速度感。"),
 ("动物与生物", "cute kitten, big eyes, fluffy fur, sitting on windowsill, soft sunlight, adorable, photorealistic, 8k", "fluffy fur 专攻毛绒质感，配合可爱度词。"),
 ("动物与生物", "(wolf howling:1.2) at full moon, snowy forest, cold blue light, dramatic, cinematic, detailed fur", "情绪动作 + 冷色调情境，一条词讲完故事。"),
 ("动物与生物", "colorful peacock, feathers fully spread, iridescent, garden background, vibrant, ultra-detailed, sharp focus", "iridescent 虹彩质感词，专治羽毛/金属/贝壳。"),
 ("动物与生物", "(dolphin jumping:1.1) out of ocean, splash, tropical sun, blue water, dynamic, wildlife photography", "抓拍瞬间 + 水花细节，动态词 dynamic 辅助。"),
 ("动物与生物", "giant panda eating bamboo, adorable, soft light, photorealistic, shallow depth of field, 8k", "行为细节比静态站姿更生动；景深收掉杂乱背景。"),
 ("动物与生物", "(dragon:1.3), fire breathing, massive wings, dark fantasy, intricate scales, dramatic lighting, epic, concept art", "幻想生物强加权 + 鳞片纹理 + 史诗概念艺术。"),
 ("动物与生物", "chameleon on branch, color-shifting skin, tropical, macro photography, extreme detail, vivid colors", "macro photography 切微距，细节密度立刻上一个量级。"),
 ("动物与生物", "(flock of birds:1.2) flying at sunset, silhouette, dramatic sky, cinematic wide shot, golden and purple tones", "群体构图 + 剪影 + 撞色，宽幅最有张力。"),

 ("建筑与城市", "(futuristic city:1.3), neon lights, towering skyscrapers, flying cars, cyberpunk night, rain, reflections, 8k", "赛博夜景三件套：霓虹、雨、地面反射。"),
 ("建筑与城市", "gothic cathedral, intricate stained glass, towering spires, dramatic light beams, interior wide shot, photorealistic", "彩窗光束 + 内景广角，写出建筑体积感。"),
 ("建筑与城市", "(japanese temple:1.2), cherry blossoms, stone path, soft sunlight, peaceful, traditional architecture, ultra-detailed", "建筑主体加权，季节元素做氛围叠加。"),
 ("建筑与城市", "ancient greek ruins, marble columns, blue sky, olive trees, golden hour, historical, cinematic wide shot", "材质 marble + 历史形容词，避免建筑风格漂移。"),
 ("建筑与城市", "(modern minimalist house:1.2), glass walls, infinity pool, desert mountains, sunset, architecture photography, clean lines", "clean lines 是极简建筑的高频有效词。"),
 ("建筑与城市", "cozy cottage, thatched roof, smoke from chimney, snowy village, warm window light, fairytale, storybook illustration", "暖窗光对冷雪景，是童话插画的经典对比。"),
 ("建筑与城市", "(interior of library:1.2), tall wooden bookshelves, warm lamps, cozy reading nooks, classical, detailed, cinematic", "内景先写光源（warm lamps），再写陈设。"),
 ("建筑与城市", "space station interior, futuristic corridors, glowing panels, zero gravity, sci-fi, clean design, hyperdetailed", "发光面板 + 失重，用物理状态词强化科幻感。"),
 ("建筑与城市", "(venice canal:1.1), gondola, historic buildings, golden reflection on water, sunset, romantic, photorealistic, 8k", "地标 + 水面倒影 + 情绪词 romantic。"),
 ("建筑与城市", "(isometric city:1.2), low poly style, pastel colors, miniature, clean, 3d render, soft lighting", "isometric 等距视角 + low poly，一秒切 3D 小景。"),

 ("艺术风格专项", "portrait of a woman, (oil painting:1.2), visible brush strokes, rich colors, classical renaissance style, masterpiece", "画种加权 + 笔触可见，比只写 oil painting 更像油画。"),
 ("艺术风格专项", "landscape, (watercolor:1.3), wet-on-wet, ink washes, soft edges, white paper texture, artistic, loose style", "湿画法 wet-on-wet 与纸纹是水彩的关键限定词。"),
 ("艺术风格专项", "cityscape, (impressionism:1.2), dappled light, vibrant brush strokes, monet style, outdoor scene, 8k", "流派 + 画家名双触发，风格更锁定。"),
 ("艺术风格专项", "portrait, (pixel art:1.3), 16-bit, retro game style, dithering, limited palette, nostalgic", "dithering 抖动 + limited palette 限定色板，像素味才正。"),
 ("艺术风格专项", "character, (comic book style:1.2), bold outlines, halftone dots, vibrant inks, dynamic pose, pop art", "halftone dots 半调网点是美漫印刷感的来源。"),
 ("艺术风格专项", "scene, (3d render:1.2), octane render, unreal engine 5, ray tracing, subsurface scattering, hyperrealistic, 8k", "渲染引擎名 + 次表面散射，专攻皮肤/蜡质通透感。"),
 ("艺术风格专项", "portrait, (charcoal sketch:1.2), hand-drawn, cross-hatching, monochrome, rough paper, artistic study", "cross-hatching 交叉排线决定素描的「手绘感」。"),
 ("艺术风格专项", "landscape, (ukiyo-e:1.2), japanese woodblock print, flat colors, bold outlines, hokusai style, waves", "woodblock print 版画工艺词 + 平涂限定。"),
 ("艺术风格专项", "portrait, (pop surrealism:1.2), dreamlike, vibrant colors, margaret keane eyes, lowbrow art, whimsical", "用特征词 Keane eyes 精确引用某种视觉符号。"),
 ("艺术风格专项", "scene, (low poly:1.3), geometric, faceted, pastel gradient background, minimalist 3d, soft ambient occlusion", "ambient occlusion 环境光遮蔽让低多边形不「飘」。"),
 ("艺术风格专项", "portrait, (art nouveau:1.2), decorative patterns, elegant curves, alphonse mucha, poster style, ornate", "新艺术靠装饰曲线 + 海报构图，而非人物本身。"),
 ("艺术风格专项", "landscape, (cyberpunk anime:1.2), neon, cel shading, blade runner, japanese aesthetic, vibrant night", "平涂 + 霓虹 + 电影名，混合风格分别落词。"),
 ("艺术风格专项", "portrait, (double exposure:1.2), blended with forest, artistic, dreamlike, conceptual photography, ethereal", "双重曝光是构图技法，可直接当提示词用。"),
 ("艺术风格专项", "scene, (vaporwave:1.2), 80s aesthetic, pink and cyan grid, retro computer, glitch, distorted, lo-fi", "年代美学 + 故障艺术，靠配色和道具锁定。"),
 ("艺术风格专项", "portrait, (renaissance oil:1.1) + (modern neon:0.6), mixed media, striking contrast, avant-garde, gallery", "用 + 连接两个独立权重块，做主次分明的东西方混搭。"),

 ("摄影/镜头/光线", "portrait, (85mm lens:1.2), f/1.4, shallow DOF, sharp eyes, blurred background, professional photography, 8k", "焦距 + 光圈 f/1.4 一起写，景深最可预测。"),
 ("摄影/镜头/光线", "street scene, (wide angle 24mm:1.2), distorted perspective, dynamic, urban photography, candid, natural light", "广角畸变本身可作为风格，不必回避。"),
 ("摄影/镜头/光线", "(telephoto compression:1.1), city skyline, layered buildings, 200mm, sharp, haze, architectural photography", "长焦压缩把远景「压」成层次。"),
 ("摄影/镜头/光线", "portrait, (golden hour:1.3), warm side light, long shadows, lens flare, cinematic, romantic, photorealistic", "黄金时刻 + 镜头光晕，一套词定全天色温。"),
 ("摄影/镜头/光线", "scene, (blue hour:1.2), city lights, twilight sky, moody, reflections on wet street, cinematic night photography", "蓝调时刻与湿街反射是夜景最稳的组合。"),
 ("摄影/镜头/光线", "still life, (studio lighting:1.2), softbox, seamless backdrop, product photography, sharp, commercial, 8k", "无缝背景 seamless backdrop 是产品图标志词。"),
 ("摄影/镜头/光线", "portrait, (rim lighting:1.2), dark background, glowing edge, dramatic, moody, low key photography", "low key 暗调摄影，靠轮廓光把主体从黑底里剥出来。"),
 ("摄影/镜头/光线", "scene, (high key:1.2), bright white, soft pastel, minimal shadows, airy, dreamy, fashion photography", "high key 高调：亮、柔、少阴影，与 low key 正好相反。"),
 ("摄影/镜头/光线", "(macro photography:1.3), dewdrop on leaf, refracted miniature world, extreme detail, shallow DOF, 8k", "微距 + 折射小世界，用构思代替堆细节词。"),
 ("摄影/镜头/光线", "portrait, (dramatic chiaroscuro:1.2), strong contrast, single light source, caravaggio style, painterly", "明暗对照法 + 单光源，古典绘画光直接迁移到摄影。"),

 ("科幻/奇幻/概念", "(spaceship:1.2) hovering over alien planet, two moons, ringed planet in sky, sci-fi, epic, matte painting, 8k", "天体外景 + matte painting 电影绘景词。"),
 ("科幻/奇幻/概念", "(floating island:1.3), waterfalls into sky, fantasy, lush vegetation, golden light, epic, concept art, ArtStation", "反重力构思靠主体强加权才不会被引力「修正」。"),
 ("科幻/奇幻/概念", "cyborg warrior, (mechanical details:1.2), glowing cybernetic eye, neon-lit alley, rain, Blade Runner style, hyperdetailed", "机械细节加权，避免赛博格变成普通人脸。"),
 ("科幻/奇幻/概念", "(dragon's lair:1.2), treasure hoard, dark cave, golden glow, atmospheric, epic fantasy, detailed, cinematic", "写「场景 + 叙事道具」，比只写 dragon 更有故事。"),
 ("科幻/奇幻/概念", "alien landscape, (bioluminescent plants:1.3), glowing mushrooms, purple and teal, strange creatures, otherworldly", "生物荧光 + 异星配色，otherworldly 收束整体调性。"),
 ("科幻/奇幻/概念", "(robot portrait:1.2), humanoid chrome face, reflective metal, studio light, sleek design, photorealistic, 8k", "镀铬反射必须配 studio light 才有金属感。"),
 ("科幻/奇幻/概念", "wizard casting spell, (magic particles:1.2), glowing runes, ancient roves, dark forest, fantasy illustration, detailed", "粒子 + 发光符文，把「施法」可视化。"),
 ("科幻/奇幻/概念", "(post-apocalyptic city:1.2), overgrown ruins, rusted vehicles, fog, muted colors, atmospheric, cinematic wide shot", "锈蚀 + 低饱和，末世感靠材质与色彩而非废墟堆砌。"),
 ("科幻/奇幻/概念", "(underwater city:1.2), domed structures, exotic fish, rays of light, futuristic, fantasy, hyperdetailed, 8k", "穹顶结构 + 穿透光线，水下科幻的空间感来源。"),
 ("科幻/奇幻/概念", "gnome village, (tiny houses:1.2), mushrooms, fairy lights, magical atmosphere, storybook, whimsical, detailed", "微缩尺度词 tiny + 童话光源，奇想调性一目了然。"),

 ("特定用途/构图/格式", "(product shot:1.3), perfume bottle on marble, soft reflection, studio light, advertising, clean, commercial, 8k", "产品广告：反射台面 + 干净背景 + 商业感词。"),
 ("特定用途/构图/格式", "(logo design:1.2), minimalist, geometric, flat vector, white background, clean, modern, graphic design", "flat vector + white background 是标志设计的硬约束。"),
 ("特定用途/构图/格式", "(isometric room:1.2), cozy interior, plants, warm light, lo-fi aesthetic, 3d render, soft colors", "等距房间 + lo-fi，适合做壁纸与插画素材。"),
 ("特定用途/构图/格式", "(vertical phone wallpaper:1.2), mountain landscape, minimalist, pastel, 9:16, aesthetic, soft light", "把画幅 9:16 写进提示词，配合输出分辨率锁定竖构图。"),
 ("特定用途/构图/格式", "(t-shirt design:1.2), centered graphic, vintage skull roses, flat colors, screen print, white background", "screen print 丝网印刷，限定印花工艺质感。"),
 ("特定用途/构图/格式", "(tattoo design:1.2), fine line, blackwork, geometric mandala, minimalist, body art, white background", "fine line blackwork 是纹身稿的精确风格词。"),
 ("特定用途/构图/格式", "(icon:1.2), app icon, rounded square, glossy, gradient, sparkles, clean, modern UI design", "圆角方形 + 光泽渐变，UI 图标的结构约束。"),
 ("特定用途/构图/格式", "(pattern design:1.2), seamless floral, repeating, watercolor, pastel, textile, tileable, decorative", "seamless / tileable 让模型理解「可平铺」。"),
 ("特定用途/构图/格式", "(book cover:1.2), fantasy novel, dramatic title space, dark forest, glowing eyes, cinematic, atmospheric", "预留标题空间 title space，是封面构图的实用技巧。"),
 ("特定用途/构图/格式", "(poster:1.2), movie poster style, centered figure, dramatic lighting, negative space for text, cinematic, 8k", "negative space for text 主动为后期排版留白。"),

 ("进阶语法演示", 'portrait, (large text "HELLO" in neon:1.2), woman with neon sign, cyberpunk, night, 8k', "提示词内指定文字内容；SD1.5 较弱，SDXL/FLUX 更可靠。"),
 ("进阶语法演示", "scene, [cat:dog:0.5], sitting on chair, soft light, photorealistic", "[from:to:step] 分步替换，可生成猫狗过渡形态。"),
 ("进阶语法演示", "portrait, <lora:detail_tweaker:0.8>, masterpiece, best quality, ultra-detailed, woman, elegant, studio light", "<lora:名称:权重> 挂载 LoRA，权重常取 0.5~0.9。"),
 ("进阶语法演示", "(masterpiece, best quality:1.2), (intricate details:1.1), (8k:1.1), scene description here, ultra-detailed, award-winning", "把画质词打包成可复用增强前缀，统一加权。"),
 ("进阶语法演示", "(subject:1.2), (detail:1.1), [weak detail], environment, lighting, camera, style, quality tags", "综合模板：加权 / 弱化 / 结构分层 / 风格 / 画质一次排好，替换括号即可复用。"),
]

# 修正上一轮的一处笔误（保持提示词可直接复制）
for i, it in enumerate(LEGACY):
    if "futuristic city:1.3}" in it[1]:
        LEGACY[i] = (it[0], it[1].replace("futuristic city:1.3}", "futuristic city:1.3)"), it[2])
    if "ancient roves" in it[1]:
        LEGACY[i] = (it[0], it[1].replace("ancient roves", "ancient robes"), it[2])

# 把原「特定用途/构图/格式」细分为两个更利于筛选的类别
for i, (cat, p, tip) in enumerate(LEGACY):
    if cat == "特定用途/构图/格式":
        nc = "特定用途·商业设计" if 85 <= i <= 89 else "特定用途·印刷版式"
        LEGACY[i] = (nc, p, tip)

def legacy_subject(p):
    s = p.split(",")[0]
    s = re.sub(r"[()\[\]{}<>]", "", s).split(":")[0].strip()
    return s[:48] or "subject"

items = []
for idx, (cat, prompt, tip) in enumerate(LEGACY, 1):
    items.append(dict(id=idx, cat=cat, prompt=prompt, tip=tip,
                      subject=legacy_subject(prompt),
                      tech="原100条精选", legacy=True))

# ---------------------------------------------------------------- 新增 50 类 × 10 条
# 每行: (类别, 主体池|分隔, 环境池|分隔, 风格池|分隔)
CATS_NEW = [
 ("美食与饮品", "steaming ramen bowl|sushi platter on slate|pour-over coffee with latte art|butter croissant and jam|colorful macaron tower|grilled steak with rosemary|bubble tea with tapioca pearls|mooncake and porcelain tea set|ice cream sundae|rustic sourdough loaf", "wooden table, warm window light|dark moody backdrop, side light|marble counter, soft studio light|cafe table, morning sun", "food photography|commercial advertising|editorial food styling"),
 ("静物与产品", "vintage brass compass|ceramic vase with single branch|leather notebook and fountain pen|crystal perfume flacon|mechanical pocket watch|amber glass apothecary bottle|stack of old books|handmade soap bars|copper kettle|minimalist desk lamp", "linen cloth, soft north light|dark gradient backdrop, rim light|concrete plinth, hard shadow|window sill, dust motes", "product photography|still life painting|minimalist commercial"),
 ("花卉与植物", "single white peony|monstera leaf with raindrops|wildflower bouquet in jar|cherry blossom branch|succulent arrangement|cactus in terracotta pot|lotus in still pond|sunflower field close-up|fern unfurling|dried pampas grass", "soft beige backdrop, diffuse light|misty greenhouse, cool light|garden bokeh, golden hour|white seamless, high key", "botanical illustration|macro photography|watercolor study"),
 ("车辆与交通", "classic 1960s sports car|matte black supercar|vintage steam locomotive|retro yellow tram|cargo ship at dusk|floating maglev train|rally car kicking dust|wooden sailboat|art deco motorcycle|hot air balloon over fields", "wet city street, neon reflections|mountain pass, sunrise|harbor, overcast sky|desert highway, heat haze", "automotive photography|concept vehicle render|cinematic wide shot"),
 ("时尚与服饰", "tailored wool coat on model|silk evening gown in motion|streetwear layered look|traditional kimono with obi|denim jacket flat lay|haute couture feather dress|leather boots on gravel|knitted sweater close-up|avant-garde paper garment|linen summer dress", "studio seamless, softbox|Parisian street, overcast|runway, dramatic spotlights|sunlit terrace, warm tones", "fashion editorial|Vogue style photography|illustrated fashion sketch"),
 ("节日与庆典", "lantern festival at night|Christmas market with snow|Diwali oil lamps and rangoli|carnival masks and confetti|Chinese New Year dragon dance|midsummer flower crowns|Halloween pumpkin display|wedding arch at sunset|birthday cake with candles|Oktoberfest beer tents", "crowd, warm festive lights|night sky with fireworks|town square, golden hour|cozy interior, candlelight", "festive photography|storybook illustration|documentary style"),
 ("天气与天象", "thunderstorm over prairie|falling snow in pine forest|heavy rain on glass window|rolling fog across valley|rainbow after storm|sandstorm approaching dunes|frost patterns on leaves|heat lightning at night|drizzle on neon street|sunshower over meadow", "dramatic dark sky, high contrast|soft overcast, muted palette|backlit droplets, warm sun|blue twilight, moody", "cinematic weather photography|atmospheric landscape|impressionist study"),
 ("海洋与水下", "coral reef with clownfish|sunken shipwreck|humpback whale underwater|jellyfish drifting in blue|sea turtle over seagrass|underwater cave with light shaft|school of sardines|manta ray silhouette|tidepool with anemones|deep sea submersible", "crystal water, caustic light patterns|dark blue abyss, single beam|shallow lagoon, turquoise|surface ripples from below", "underwater photography|marine documentary|dreamlike digital painting"),
 ("太空与天文", "ringed gas giant from orbit|astronaut on moon surface|nebula in violet and teal|space station against earthrise|comet crossing star field|alien planet with two suns|rover on martian dunes|galaxy spiral top-down|solar eclipse from orbit|asteroid field with distant sun", "black space, hard starlight|deep field, long exposure|lens flare, vacuum clarity|earth glow, blue rim", "astrophotography|sci-fi matte painting|NASA style render"),
 ("微观与科学", "diatom under microscope|pollen grain macro|snowflake crystal structure|cell division diagram|neural network glowing nodes|mineral thin section in polarized light|virus capsid 3d model|butterfly wing scales|water droplet impact|magnetic field lines visualization", "black field, extreme magnification|clean lab white, even light|dark gradient, subsurface glow|grid overlay, technical", "scientific illustration|electron microscopy style|clean infographic"),
 ("运动与竞技", "sprinter leaving starting blocks|surfer inside barrel wave|skateboarder mid-air trick|ballet dancer en pointe|boxer under ring lights|cyclist peloton on alpine road|rock climber on overhang|soccer player volley shot|skiier carving powder|archer at full draw", "stadium floodlights, motion blur|golden dust, frozen action|rain-soaked track, dramatic|arena crowd bokeh", "sports photography|dynamic action illustration|high speed shutter"),
 ("儿童与家庭", "child blowing dandelion seeds|kids building blanket fort|family picnic on checkered blanket|grandparent reading aloud|toddler with rubber duck|siblings flying a kite|baby feet close-up|child painting with fingers|family silhouette at sunset|little girl with oversized hat", "sunny backyard, warm light|cozy living room, lamp glow|park lawn, soft bokeh|golden hour, lens flare", "lifestyle photography|storybook illustration|candid documentary"),
 ("职业与职场", "surgeon in operating theatre|chef plating in busy kitchen|architect over blueprint table|lighthouse keeper at dusk|beekeeper among hives|street musician with violin|potter at spinning wheel|firefighter in smoke|astronomer at telescope|barista pouring latte", "industrial task lighting, gritty|warm workshop, dust in air|modern office, cool daylight|night shift, single lamp", "documentary photography|cinematic character portrait|editorial reportage"),
 ("历史古文明", "Roman forum at dawn|Egyptian scribe with papyrus|Terracotta army chamber|Mayan pyramid in jungle|Silk Road caravan|Viking longship at sea|Greek pottery workshop|medieval scribe illuminations|Inca terrace at sunrise|ancient library of Alexandria", "golden hour, dust and haze|torchlight, deep shadows|overcast, weathered stone|sunbeams through columns", "historical reconstruction|cinematic epic|museum diorama"),
 ("神话与宗教", "Greek goddess on marble throne|Norse valkyrie over battlefield|Buddhist temple interior with incense|Chinese dragon deity in clouds|Celtic knot stone circle|angelic figure in stained glass|Japanese kitsune at shrine|Egyptian jackal guardian|medieval stained glass saints|zen monk in bamboo grove", "divine backlight, volumetric rays|candlelit shrine, warm gold|stormy sky, ethereal mist|quiet dawn, minimal", "religious iconography|mythological painting|ethereal concept art"),
 ("暗黑与恐怖", "abandoned asylum corridor|foggy graveyard at midnight|creature silhouette in doorway|rusted doll on shelf|haunted Victorian portrait|candlelit occult ritual|overgrown crypt entrance|empty subway platform at 3am|cracked mirror with reflection|swamp with twisted trees", "single cold light source, deep shadows|desaturated green, heavy fog|flickering candle, high contrast|moonlight through broken glass", "horror movie still|dark fantasy illustration|low key cinematography"),
 ("治愈系Lo-fi", "rainy window with warm desk lamp|cat sleeping on stack of books|lo-fi study room at night|steaming mug beside notebook|tiny balcony with plants|quiet library corner|sunbeam on wooden floor|record player with vinyl|cozy bed and fairy lights|slow morning with toast", "soft pastel palette, gentle grain|warm amber, low contrast|dusk blue and orange|muted tones, soft focus", "lo-fi illustration|cozy anime background|soft 3d render"),
 ("游戏美术资产", "fantasy sword concept sheet|pixel art village tileset|character turnaround sheet|RPG inventory icons|stylized tree asset pack|sci-fi crate prop|boss creature concept|isometric dungeon room|weapon material variants|game UI frame elements", "neutral grey backdrop, ortho view|clean turnaround grid|flat lighting for readability|transparent background feel", "game concept art|asset sheet|stylized 3d render"),
 ("UI与信息图", "dashboard with clean charts|weather widget glassmorphism|minimal onboarding screen|data flow diagram|timeline infographic|mobile app wireframe|map pin interface|progress ring set|kanban board UI|neon HUD overlay", "white canvas, crisp alignment|dark mode, subtle glow|grid guides, 8pt spacing|soft shadows, rounded corners", "modern UI design|flat vector infographic|dribbble style"),
 ("材质与纹理", "brushed stainless steel close-up|cracked dry earth|wet cobblestone reflection|translucent alabaster slab|worn leather grain|iridescent soap bubble|molten glass surface|rough concrete macro|velvet fabric folds|oxidized copper patina", "raking side light to reveal texture|neutral grey studio, even|macro, extreme detail|gradient backdrop", "material study|texture photography|PBR render"),
 ("抽象与几何", "intersecting translucent spheres|impossible staircase structure|fluid gradient ribbons|fractal spiral in monochrome|floating concentric rings|tessellated hexagon field|Bauhaus shape composition|parametric wave sculpture|golden ratio spiral|soft cubic forms in fog", "seamless gradient background|dark void, single spotlight|pastel field, ambient occlusion|white cyclorama", "abstract 3d render|generative art|minimalist poster"),
 ("地图与等距", "isometric fantasy village map|old parchment treasure map|subway transit diagram|top-down city block plan|contour mountain relief map|hand-drawn travel map|battlemap with grid|antique world map|miniature island diorama|floor plan with furniture", "flat overhead lighting, no perspective|parchment texture, ink lines|clean vector, labeled zones|soft shadows on paper", "cartographic illustration|isometric 3d|technical drawing"),
 ("文字与排版", 'bold serif headline "DREAM" on poster|neon kanji sign in rain|chalk lettering on blackboard|embossed gold type on leather|3d chrome logotype|hand-lettered quote card|kinetic typography swirl|vintage circus type|type specimen sheet|calligraphy ink stroke', "high contrast, centered composition|dark backdrop, glowing edges|paper texture, letterpress|clean grid, generous margins", "typography design|graphic poster|editorial layout"),
 ("群像与互动", "three friends laughing at cafe table|orchestra mid-performance|market crowd haggling|family dinner conversation|team huddle before match|dance circle at festival|two rivals facing off|classroom of students|queuing at food stall|choir in candlelit hall", "environmental light, layered depth|candid 35mm, natural|warm interior, soft bokeh|stage spotlights, haze", "group portrait photography|candid documentary|ensemble illustration"),
 ("四季与昼夜", "first snow on quiet street|spring blossoms after rain|summer noon on empty plaza|autumn leaves swirling|blue hour over rooftops|dawn mist on lake|midnight city with wet asphalt|late afternoon long shadows|monsoon clouds gathering|winter sun through bare branches", "season-specific color palette|time-of-day lighting|soft atmospheric haze|single dominant temperature", "seasonal landscape photography|atmospheric painting|cinematic still"),
 ("电影分镜与镜头语言", "extreme close-up on trembling hand|dutch angle in narrow corridor|over-the-shoulder conversation shot|slow dolly toward doorway|wide establishing shot of town|match cut composition|low angle hero reveal|POV from inside helmet|tracking shot beside runner|two-shot with negative space", "anamorphic lens flare, 2.39:1|practical lights, shallow focus|storyboard pencil, greyscale|teal and orange grade", "cinematic storyboard|film still|anamorphic photography"),
 ("画种扩展", "gouache mountain study|tempera icon panel|airbrush retro poster|linocut two-color print|pastel on toned paper|sumi-e bamboo|screenprint gig poster|acrylic palette knife scene|egg tempera portrait|digital matte painting", "visible medium texture, paper tooth|limited ink layers, registration|bold flat shapes|layered washes", "traditional painting medium|printmaking|painterly concept art"),
 ("艺术家风格扩展", "in the style of Syd Mead sleek futurism|Moebius clean line sci-fi|Wes Anderson symmetrical pastel set|Greg Rutkowski epic fantasy|Hayao Miyazaki lush countryside|H.R. Giger biomechanical|Edward Hopper lonely diner|Yayoi Kusama dotted infinity|Beeple surreal 3d|Alphonse Mucha decorative panel", "artist-specific palette and composition|signature lighting setup|characteristic line work|period-appropriate medium", "artist reference|stylistic emulation|concept art"),
 ("地域文化", "Kyoto alley with paper lanterns|Marrakech riad courtyard|Santorini whitewashed steps|Hangzhou West Lake in mist|Norwegian fjord wooden cabin|Rajasthan haveli doorway|Buenos Aires tango street|Istanbul bazaar spices|Tibetan prayer flags|Provence stone farmhouse", "local midday light, authentic materials|golden hour, warm plaster|cool coastal haze|festival decorations", "travel photography|cultural illustration|architectural documentary"),
 ("朋克变体", "steampunk brass airship deck|dieselpunk 1940s war factory|atompunk retro-future diner|solarpunk green rooftop city|cyberpunk noodle stall|biopunk glowing lab garden|clockpunk gear cathedral|nanopunk translucent clinic|raypunk chrome rocket|frostpunk snowbound generator", "genre-specific material palette|period lighting, smoke|layered pipes and cables|optimistic or gritty grade", "retro-futurism concept art|genre worldbuilding|matte painting"),
 ("古生物与恐龙", "T-Rex in fern forest|brontosaurus at misty lake|triceratops herd crossing plain|pterosaur over cliff|ammonite fossil in rock|velociraptor in tall grass|mammoth on tundra|dinosaur skeleton museum hall|hatchling emerging from egg|marine mosasaur silhouette", "prehistoric haze, volumetric sun|moody overcast, wet foliage|museum spotlights|golden backlight", "paleoart|natural history illustration|cinematic creature shot"),
 ("昆虫与节肢", "morpho butterfly on leaf|praying mantis macro|honeybee covered in pollen|stag beetle on bark|dragonfly over pond|ant column carrying leaf|ladybird on dewy grass|tarantula in burrow|cicada shell close-up|fireflies in jar", "macro depth of field, crisp eyes|backlit wings, translucent|dark forest floor, damp|soft bokeh greenery", "macro insect photography|scientific illustration|jewel-toned render"),
 ("深海与奇异生物", "anglerfish with glowing lure|giant squid in dark water|bioluminescent jelly bloom|dumbo octopus drifting|viperfish with fang teeth|deep sea hydrothermal vent|glass squid translucent body|sea angel swimming|isopod on seabed|alien-like larvacean", "absolute darkness, single biolume|blue-black gradient, particles|submersible spotlight beam|faint marine snow", "deep sea documentary|otherworldly creature art|bioluminescent render"),
 ("神话生物", "phoenix rising from embers|mermaid in moonlit tidepool|centaur in moonlit glade|griffin on cliff nest|kraken surfacing near ship|kitsune with nine tails|unicorn in misty wood|basilisk in ruined crypt|qilin among clouds|werewolf silhouette at full moon", "mythic backlight, drifting particles|stormy sky, dramatic rim|cold moonlight, mist|golden divine glow", "mythological creature art|epic fantasy illustration|dark fairytale"),
 ("室内与家具", "scandinavian living room with oak floor|japandi bedroom with linen|mid-century lounge chair corner|industrial loft with exposed brick|art deco hotel lobby|tiny house interior with loft|library ladder and reading nook|kitchen with open shelving|sunlit artist studio|minimalist bathroom with stone", "large window, soft daylight|warm lamplight, evening|architectural digest even light|single pendant, cozy", "interior design photography|architectural render|3d visualization"),
 ("珠宝与腕表", "diamond ring on black velvet|art deco emerald necklace|skeleton mechanical watch macro|pearl strand on silk|gold signet ring engraving|sapphire earrings with caustics|vintage chronograph dial|raw gemstone in matrix|silver filigree brooch|watch movement exploded view", "dark field, pinpoint specular|soft light tent, no harsh shadow|macro, reflective caustics|luxury gradient backdrop", "luxury product photography|jewelry macro|commercial still life"),
 ("乐器与音乐", "grand piano in empty concert hall|violin close-up with bow|vintage electric guitar on amp|jazz trumpet under spotlight|harp strings backlit|drum kit in fog|theremin in retro lab|accordion on cobbled street|vinyl record and tonearm|bamboo flute in mist", "stage spotlight, dust motes|warm wood, low key|soft window light|concert haze, blue rim", "music photography|concert still|moody product shot"),
 ("舞蹈与舞台", "ballet dancer mid-pirouette|contemporary dancer in fog|flamenco with red skirt swirl|kabuki performer in makeup|breakdancer freeze on pavement|ballroom couple under chandelier|butoh in dim theatre|ribbon gymnast arc|tap dancer on wet stage|shadow theatre silhouettes", "single overhead spotlight, long shadow|haze and colored gels|dark stage, rim only|glittering backdrop, bokeh", "stage photography|dance poster|theatrical illustration"),
 ("建筑蓝图与剖面", "architectural blueprint of villa|cutaway section of cathedral|exploded axonometric house|floor plan with dimension lines|structural wireframe of bridge|section through subway station|elevation drawing with annotations|site plan with contour lines|construction detail sketch|isometric MEP diagram", "white paper, cyan ink lines|dark blueprint, crisp white lines|technical grid, no shading|drafting pencil, light smudge", "technical drawing|architectural blueprint|CAD style"),
 ("纸艺与手作", "intricate kirigami paper city|layered papercut forest scene|quilled paper flower|origami crane mid-fold|pop-up book castle|paper maché mask|shadow box diorama|woven paper basket|cut-paper portrait silhouette|handmade zine spread", "soft side light casting paper shadows|flat overhead, crisp edges|warm pastel paper palette|single color, layered depth", "paper craft photography|papercut illustration|handmade aesthetic"),
 ("黏土与微缩模型", "claymation character with fingerprints|miniature diorama of cafe|polymer clay food keychain|tilt-shift model village|super sculpey creature bust|LEGO brick city block|felt needle animal|resin miniature landscape|stop-motion set with practical lights|tiny clay robot on desk", "macro tilt-shift, shallow focus|tabletop practical lighting|soft pastel clay palette|visible handmade imperfections", "stop motion still|miniature photography|tactile 3d render"),
 ("玻璃/液体/烟雾/火焰", "ink swirling in water|smoke plume on black backdrop|molten glass being blown|flame licking metal surface|splash crown of milk|colored dye in oil|frost spreading on glass|bubble cluster macro|liquid mercury droplets|fire embers drifting upward", "black background, high speed flash|backlit to reveal translucency|single hard side light|slow shutter, motion trails", "fluid photography|high speed capture|abstract elemental art"),
 ("体积光与焦散", "god rays through cathedral window|caustic light patterns on pool floor|volumetric fog in pine forest|projector beam in dusty room|sun shaft through attic window|laser grid in smoke|light leaking through blinds|underwater caustics on skin|dust particles in single beam|prism rainbow on white wall", "dark surroundings to reveal beam|haze density, soft falloff|high contrast, low ambient|clean white surface", "volumetric lighting study|cinematic light photography|optical render"),
 ("色彩方案", "monochrome teal portrait|complementary orange and teal street|analogous autumn palette forest|pastel macaron still life|morandi muted interior|neon magenta and cyan portrait|triadic primary poster|split-complementary desert|earth tone ceramic set|high saturation candy product", "single hue lighting, subtle variation|graded cinematic palette|soft neutral surround|color gel lighting", "color graded photography|palette-driven illustration|design system"),
 ("构图法则", "rule of thirds lone tree|golden spiral seashell|leading lines railway platform|frame within frame through archway|perfect symmetry palace facade|negative space minimal portrait|diagonal dynamic stairwell|foreground framing with branches|centered radial mandala|layered depth with foreground midground background", "wide angle to emphasise geometry|clean background, one subject|balanced visual weight|soft even light", "compositional study|fine art photography|graphic layout"),
 ("特殊视角", "extreme low angle skyscraper|bird's eye view of crossroads|fisheye skateboard trick|worm's eye view of mushrooms|top-down flat lay of desk|dutch angle alleyway|POV from inside a helmet|through-the-glass rainy view|mirror reflection composition|underwater looking up at surface", "perspective-defining lens choice|distortion kept intentional|single vanishing point|reflection as second subject", "perspective photography|creative angle|immersive POV"),
 ("画幅比例", "ultra-wide 21:9 desert panorama|9:16 vertical mountain wallpaper|1:1 square portrait|2.39:1 anamorphic film still|4:3 retro TV frame|16:9 documentary landscape|tall 3:4 book cover|panoramic 360 equirectangular|banner 3:1 header|cinemascope letterbox scene", "composition tuned to the ratio|subject placed for crop safety|letterbox friendly negative space|centered or rule-of-thirds accordingly", "aspect ratio study|wallpaper design|cinematic framing"),
 ("提示词高级语法", "(subject:1.4) with ((nested emphasis:1.2):1.15)|[weak background] with (main:1.3)|(A:B:0.6) blend of marble and water|AND composable: portrait AND landscape|BREAK to separate style from content|[cat|dog] alternating words|<lora:film_grain:0.6> with (grain:1.2)|(masterpiece, best quality:1.25) quality prefix|embedding:detailed_eyes with (eyes:1.2)|(style1:1.1) + (style2:0.7) mixed media", "flat neutral backdrop, even light|studio softbox, no distraction|clean grey sweep|simple single light", "syntax demonstration|prompt engineering|technical test"),
 ("模型适配写法", "SDXL: highly detailed photograph of a glassblower at work, warm workshop light, natural language description, no weight syntax|FLUX: a long descriptive sentence about a quiet harbor at dawn with soft fog and pastel sky, photorealistic|SD1.5: masterpiece, best quality, ultra-detailed, 1girl, garden, soft light|Pony style: score_9, score_8_up, anime, expressive eyes, cel shading|SD3: clean editorial photo of ceramic bowls on linen, soft daylight|anime model: (detailed eyes:1.2), clean lineart, flat color|photoreal model: (skin pores:1.1), 85mm, f/2.0|LoRA stack: <lora:style:0.7><lora:detail:0.5>, subject, soft light|negative-heavy SD1.5 with quality prefix|long caption style with camera, lighting, color, mood in order", "model-appropriate level of detail|matching the training caption style|avoiding unsupported syntax|keeping token order intentional", "model-specific prompting|caption engineering|compatibility notes"),
 ("商业设计交付", "e-commerce hero banner with product and copy space|packaging mockup on kraft paper|restaurant menu board layout|business card front and back|social media carousel tile|app splash screen illustration|conference poster with title zone|sticker sheet with die-cut outlines|email header illustration|brand pattern with logo lockup", "brand color palette, clean light|isolated on white, soft shadow|grid aligned, print ready|neutral backdrop for recolor", "commercial design|brand asset|advertising layout"),
]

# ---------------------------------------------------------------- 22 个技巧模板
TECHS = [
 dict(label="权重强化", tpl="({s}:1.35), {e}, {st}, (cinematic lighting:1.2), 8k, ultra-detailed",
      tips=["给主体 (词:1.35) 加权：数值 >1 提高其在去噪中的优先级，是控制画面主角最直接的手段。",
            "权重不是越大越好，1.2~1.4 通常最稳；超过 1.6 容易让色彩过饱和、结构崩坏。",
            "先写主体再加权，词序本身也带权重：越靠前的 token 影响越大。"]),
 dict(label="嵌套加重", tpl="(({s}:1.2):1.15), {e}, {st}, (sharp focus:1.1)",
      tips=["括号可嵌套：((词:1.2):1.15) 实际约等于 1.2×1.15≈1.38，权重会叠乘。",
            "嵌套写法适合需要「再强调一点」又不想把数字写得很夸张的场景。",
            "注意不同前端对嵌套括号的解析略有差异，出图异常时改回单层权重。"]),
 dict(label="降权弱化", tpl="{s}, [{e}], ({st}:1.2), (soft light:1.1)",
      tips=["[词] 等价于约 ×0.9，用来压低环境、背景等次要元素，比堆负面词更温和。",
            "多重方括号 [[词]] 会继续递减，适合把干扰元素「几乎抹掉」但保留一点氛围。",
            "降权和负面提示词的区别：降权仍在正面采样里，只是话语权变小。"]),
 dict(label="分步混合", tpl="({s}:{st}:0.6), {e}, (soft rim light:1.15)",
      tips=["(A:B:0.6) 表示采样进行到 60% 时从 A 切换到 B，前段定构图、后段定风格。",
            "这个三段式语法是 prompt editing 的一种，切换步数越靠后，A 的形态保留越多。",
            "想做「主体真实、后期风格化」的效果，把风格词放在 B 位置最合适。"]),
 dict(label="分步替换", tpl="[{s}:{st}:0.5], {e}, (gentle key light:1.2)",
      tips=["[from:to:0.5] 前 50% 步画 from、之后画 to，能生成两个概念的融合体。",
            "与圆括号三段式不同，方括号版本按步数直接替换整段词，适合形态混合。",
            "把切换点调到 0.2 会更偏向后者，0.8 则几乎只保留前者。"]),
 dict(label="交替词", tpl="[{s}|{st}], {e}, (sharp focus:1.2), highly detailed",
      tips=["[A|B] 让两个词在采样步之间交替生效，常得到兼具两者特征的混合质感。",
            "交替词适合做材质/风格融合，不适合需要精确结构的人体与文字。",
            "可配合较低 CFG 使用，避免交替带来的语义拉扯。"]),
 dict(label="AND合成", tpl="({s}:1.15), {e} AND ({st}:0.9), (soft light:1.1)",
      tips=["AND 把左右两段分别去噪再合成（Composable Diffusion），适合叠加互不干扰的概念。",
            "WebUI 里可写成 `A:1 AND B:1.2` 给两段配不同强度。",
            "AND 与逗号的区别：逗号是同一段里的并列，AND 是两条独立条件流。"]),
 dict(label="BREAK分段", tpl="({s}:1.2), {e} BREAK ({st}:1.1), (volumetric light:1.15), masterpiece",
      tips=["BREAK 强制结束当前 token 段、另起一段编码，缓解长提示词后半段被稀释。",
            "SD1.5 的 75 token 边界尤其适合用 BREAK 显式切开主体与风格。",
            "BREAK 后面通常放风格、光线、画质词，前面放主体与场景。"]),
 dict(label="LoRA调用", tpl="<lora:style_xl:0.75>, ({s}:1.2), {e}, {st}, (crisp details:1.1)",
      tips=["<lora:名称:权重> 挂载 LoRA，权重常取 0.5~0.9；多个 LoRA 可连续书写。",
            "LoRA 通常需要配套触发词，只写标签不写触发词往往效果打折。",
            "LoRA 权重过高会压过提示词本身，先固定提示词再调 LoRA 更高效。"]),
 dict(label="Embedding触发", tpl="({s}:1.2), {e}, {st}, (embedding:detail_eyes:1.1)",
      tips=["Textual Inversion 用「触发词」调用，触发词本身也可以再加权。",
            "负面 embedding（如 badhand 类）应放进负面提示词栏，别写在正面。",
            "不同模型的 embedding 不通用，SD1.5 的通常不能直接用于 SDXL。"]),
 dict(label="画质前缀", tpl="(masterpiece, best quality, ultra-detailed:1.2), ({s}:1.15), {e}, {st}, 8k",
      tips=["把画质词打包成一个加权块做成可复用前缀，换主体时整段照搬即可。",
            "SD1.5 对画质词非常敏感；SDXL / FLUX 则更吃具体描述，画质词可精简。",
            "画质词放最前，利用词序优势，同时避免占用主体位置的表达空间。"]),
 dict(label="镜头参数", tpl="({s}:1.2), {e}, (85mm lens:1.1), f/1.8, (shallow DOF:1.15), {st}",
      tips=["焦距 + 光圈写进提示词，能稳定控制景深与透视，比只写 bokeh 精确。",
            "85mm/f1.8 人像、24mm 广角、200mm 长焦压缩，是三组最值得记的镜头词。",
            "镜头词与风格词冲突时（如像素画 + 85mm），优先保留风格词。"]),
 dict(label="光线控制", tpl="({s}:1.2), {e}, (volumetric lighting:1.25), (god rays:1.1), {st}",
      tips=["体积光、丁达尔、耶稣光这类词加权后，能直接改变画面的空气感。",
            "写光之前先写「暗环境」，有暗才有光束，否则容易变成一片过曝。",
            "光线词最好只选一种主光，多重主光会让模型无所适从。"]),
 dict(label="多风格混搭", tpl="({s}:1.2), {e}, ({st}:1.1), (minimalist line art:0.65), mixed media",
      tips=["两个风格分别给 1.1 与 0.65，主次分明，比各写 1.0 更不容易糊成一团。",
            "混搭时给二者指定不同「作用面」：一个管色彩、一个管线条，成功率更高。",
            "出现风格打架时，把次要风格降到 0.5 以下，或改用分步混合语法。"]),
 dict(label="显式降权", tpl="({s}:1.25), (busy cluttered background:0.6), {e}, {st}",
      tips=["权重 <1 是主动压低某个元素，比把它扔进负面词更柔和、更可控。",
            "适合处理「想要一点氛围但别抢戏」的背景、装饰、杂色。",
            "配合方括号 [词] 使用，可以做出多层级的注意力分配。"]),
 dict(label="画幅控制", tpl="({s}:1.2), {e}, {st}, (vertical composition:1.1), 9:16 aspect ratio, wallpaper",
      tips=["把画幅比例写进提示词，再配合输出分辨率，竖构图/宽幅才稳定。",
            "画幅词要和构图词配合：9:16 适合中心主体，21:9 适合引导线与留白。",
            "只改分辨率不改提示词时，模型常把主体拉变形，画幅词能缓解。"]),
 dict(label="色彩方案", tpl="({s}:1.2), {e}, (complementary orange-teal grading:1.2), {st}",
      tips=["写「色彩关系」（互补/邻近/莫兰迪）比只罗列颜色更可控。",
            "色彩方案词建议在风格词之后、画质词之前，避免压过主体语义。",
            "想要统一色调，可同时指定一个主色 + 一个「muted / pastel」类限定。"]),
 dict(label="构图法则", tpl="({s}:1.2), {e}, (rule of thirds:1.15), (leading lines:1.1), {st}",
      tips=["三分法、引导线、框中框这类术语是有效的构图指令，不只是描述。",
            "构图词与视角词一起用（低角度 + 引导线）能显著增强纵深。",
            "极简画面改用 negative space，比继续堆构图词更干净。"]),
 dict(label="特殊视角", tpl="(low angle view:1.25), ({s}:1.2), {e}, {st}",
      tips=["视角词前置并加权，能一次性决定整张图的透视关系。",
            "俯视/仰视/鱼眼/POV 都属于强约束，尽量不要同时写两个。",
            "视角词与镜头焦距要自洽：俯视配广角、压缩配长焦。"]),
 dict(label="材质质感", tpl="({s}:1.2), (brushed metal:1.25), (translucent:1.1), {e}, {st}",
      tips=["材质词加权决定表面反射、通透度与粗糙度，是产品/静物图的核心。",
            "材质必须配对应光线：金属要柔光箱，玻璃要背光，织物要侧掠光。",
            "iridescent / subsurface scattering 这类进阶词能补一层真实感。"]),
 dict(label="长句自然语言", tpl="A highly detailed photograph of {s}, set in {e}, with soft directional light, in {st} style, (natural skin and material detail:1.15)",
      tips=["FLUX / SD3 偏好完整自然语言长句，弱化权重语法、靠描述顺序控制重点。",
            "长句里把「主体—环境—光—风格—细节」按序写，比堆关键词更稳定。",
            "这类模型对负面提示词依赖低，可留空或只保留最关键几条。"]),
]

# 语法特性标签
def auto_tags(prompt, tech_label, cat):
    t = [cat, tech_label]
    if "<lora:" in prompt: t.append("LoRA")
    if " AND " in prompt: t.append("AND合成")
    if " BREAK " in prompt: t.append("BREAK")
    if "[from:" in prompt or re.search(r"\([^()]*:[^():]+:[\d.]+\)", prompt): t.append("分步语法")
    if "[" in prompt and "]" in prompt: t.append("括号语法")
    if re.search(r"\d+mm|f/\d", prompt): t.append("镜头")
    if re.search(r"\d+:\d+", prompt): t.append("画幅")
    if "<lora:" in prompt or "embedding:" in prompt: t.append("外部模型")
    if "9:16" in prompt or "21:9" in prompt: t.append("画幅")
    return t

SPECIAL = {
 "提示词高级语法": ("语法演示", "{s}, {e}, ({st}:1.1), (clean technical render:1.15)", [
   "直接展示语法本身：注意圆括号、方括号、尖括号在同一条提示词里如何共存与互相嵌套。",
   "把语法演示放在中性环境和简单风格下，才能看清每种写法单独造成的差异。",
   "建议固定 seed 逐条对比，观察权重、分步与合成语法对构图的实际影响。"]),
 "模型适配写法": ("模型适配", "{s}, {e}, ({st}:1.1), (native caption style:1.15)", [
   "不同模型吃不同写法：SD1.5 靠画质词，FLUX / SD3 靠完整长句，Pony 靠评分触发词。",
   "照搬该模型训练时的 caption 风格，比强行堆权重语法更有效。",
   "跨模型迁移提示词时，先删掉对方不支持的语法，再微调措辞顺序。"]),
 "画幅比例": ("画幅比例", "{s}, {e}, ({st}:1.1), (crop-safe framing:1.15)", [
   "画幅比例写进提示词并配合输出分辨率，才能稳定得到目标构图。",
   "宽幅适合引导线与留白，竖幅适合中心主体；构图词要跟着比例一起换。",
   "只改分辨率不改提示词，主体常被拉变形，画幅词能明显缓解。"]),
}

def split_pool(s):
    # 提示词里 [A|B] 交替词本身含管道符，先保护再切分
    guard = "\uE100"
    return [x.strip().replace(guard, "|") for x in
            s.replace("[cat|dog]", "[cat" + guard + "dog]").split("|")]

for ci, (cat, subj_s, env_s, style_s) in enumerate(CATS_NEW):
    subs = split_pool(subj_s)
    envs = split_pool(env_s)
    styles = split_pool(style_s)
    assert len(subs) == 10, (cat, len(subs))
    for i in range(10):
        s, e, st = subs[i], envs[i % len(envs)], styles[i % len(styles)]
        if cat in SPECIAL:
            tech, tpl, tips = SPECIAL[cat]
            prompt = tpl.format(s=s, e=e, st=st)
            tip = tips[(ci + i) % 3]
        else:
            t = TECHS[(ci + i * 2) % len(TECHS)]
            tech = t["label"]
            prompt = t["tpl"].format(s=s, e=e, st=st)
            tip = t["tips"][(ci + i) % 3]
        idx = len(items) + 1
        items.append(dict(id=idx, cat=cat, prompt=prompt, tip=tip,
                          subject=s[:56], tech=tech, legacy=False,
                          tags=auto_tags(prompt, tech, cat)))

for it in items:
    if it.get("legacy"):
        p = it["prompt"]; c = it["cat"]
        tg = [c, "原100条精选"]
        if "<lora:" in p: tg.append("LoRA")
        if re.search(r"\[[^\[\]]+:[^\[\]]+:[\d.]+\]", p): tg.append("分步语法")
        if "[" in p: tg.append("括号语法")
        if re.search(r"\d+mm|f/\d", p): tg.append("镜头")
        if re.search(r"\d+:\d+", p): tg.append("画幅")
        it["tags"] = tg

assert len(items) == 600, len(items)
cats = []
for it in items:
    if it["cat"] not in cats: cats.append(it["cat"])
assert len(cats) == 60, len(cats)
techs_all = []
for it in items:
    if it["tech"] not in techs_all: techs_all.append(it["tech"])
tag_all = []
for it in items:
    for x in it["tags"]:
        if x not in tag_all: tag_all.append(x)
assert len(set(x["prompt"] for x in items)) > 580

DATA = dict(items=items, cats=cats, techs=techs_all, tags=tag_all)

NEG_FULL = "(worst quality, low quality:1.4), (lowres:1.2), bad anatomy, bad hands, missing fingers, extra digits, fused fingers, too many fingers, missing limbs, extra limbs, malformed limbs, mutated hands, poorly drawn hands, poorly drawn face, poorly drawn feet, missing arms, missing legs, extra arms, extra legs, disfigured, deformed, mutation, boolean, textureless, blurry, jpeg artifacts, watermark, signature, username, text, error, cropped, out of frame, low quality, normal quality, bad composition, tiling, airbrush, multiple views, multiple panels, monochrome, oversaturated, undersaturated, bad perspective, distorted, unnatural pose, cross-eyed, lazy eye, bad eyes, extra pupils, missing eyes, asymmetrical eyes, long neck, bad neck, duplicate, morbid, mutilated, extra breasts, missing breasts, amputation, incomplete, unfinished, (bad proportions:1.2), cloned face, gross proportions, malformed, unclear details, static, noise, pixelated, overexposed, underexposed, flat lighting, harsh lighting, artifacts, glitch, distortion, unnatural colors, ugly, boring, duplicate face, duplicate body, extra heads, faceless, conceal face"
NEG_PHOTO = "(worst quality, low quality:1.4), lowres, bad anatomy, bad hands, missing fingers, extra digits, blurry, jpeg artifacts, watermark, text, signature, username, deformed, disfigured, mutated, out of frame, cropped, duplicate, morbid, mutilated, bad proportions, ugly"
NEG_ANIME = "(worst quality, low quality:1.4), lowres, bad anatomy, bad hands, missing fingers, extra digits, bad eyes, multiple tails, extra tail, monochrome, sketch, watermark, signature, username, text, blurry, jpeg artifacts, out of frame, cropped, bad proportions, deformed, mutated, ugly"

json_str = json.dumps(DATA, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stable Diffusion 提示词卡片库 · 600 条</title>
<style>
:root{
  --bg:#0d1117; --bg2:#111823; --card:#171f2b; --card2:#1c2634;
  --line:#2a3646; --txt:#e6edf5; --dim:#93a3b8; --dim2:#6f8199;
  --acc:#7c9cff; --acc2:#4fd1c5; --gold:#ffd479; --red:#ff8f8f;
  --mono:ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",Menlo,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei","WenQuanYi Micro Hei",sans-serif;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--txt);font-family:var(--sans);font-size:14px;line-height:1.6}
a{color:var(--acc)}
.wrap{max-width:1480px;margin:0 auto;padding:0 22px 120px}
header{padding:34px 0 20px;border-bottom:1px solid var(--line);margin-bottom:18px}
h1{margin:0 0 8px;font-size:27px;letter-spacing:.5px}
h1 span{color:var(--acc)}
.sub{color:var(--dim);font-size:13.5px}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:9px 15px}
.stat b{font-size:19px;color:var(--acc2);font-family:var(--mono)}
.stat small{color:var(--dim);display:block;font-size:11px}
details.guide{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:16px 0;padding:0 16px}
details.guide summary{cursor:pointer;padding:13px 0;font-weight:600;color:var(--acc)}
details.guide .in{padding:0 0 16px;color:var(--dim);font-size:13px}
details.guide code{background:#0b1017;color:var(--gold);padding:1px 6px;border-radius:4px;font-family:var(--mono);font-size:12px}
table{width:100%;border-collapse:collapse;margin:10px 0;font-size:12.5px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{background:#0b1017;color:var(--acc2);white-space:nowrap}
td code{font-family:var(--mono);color:var(--gold)}
.toolbar{position:sticky;top:0;z-index:20;background:rgba(13,17,23,.94);backdrop-filter:blur(12px);
  border:1px solid var(--line);border-radius:14px;padding:13px 15px;margin:18px 0 20px;
  display:flex;gap:10px;flex-wrap:wrap;align-items:center;box-shadow:0 8px 28px rgba(0,0,0,.35)}
.toolbar label{font-size:11.5px;color:var(--dim2);display:block;margin-bottom:3px}
.field{display:flex;flex-direction:column}
input[type=text],select,textarea{background:#0b1017;color:var(--txt);border:1px solid var(--line);
  border-radius:8px;padding:8px 10px;font-family:var(--sans);font-size:13px;outline:none}
input[type=text]:focus,select:focus,textarea:focus{border-color:var(--acc)}
#q{min-width:230px}
select{min-width:150px;max-width:230px}
.btn{background:var(--card2);color:var(--txt);border:1px solid var(--line);border-radius:8px;
  padding:8px 13px;cursor:pointer;font-size:12.5px;font-family:var(--sans);transition:.15s}
.btn:hover{border-color:var(--acc);color:var(--acc)}
.btn.primary{background:var(--acc);color:#0b1017;border-color:var(--acc);font-weight:600}
.btn.primary:hover{background:#96afff;color:#0b1017}
.btn.ghost{background:transparent}
.btn.on{background:var(--acc2);color:#08201d;border-color:var(--acc2);font-weight:600}
.global{display:flex;align-items:center;gap:9px;background:#0b1017;border:1px solid var(--line);
  border-radius:8px;padding:6px 11px}
.global span{font-size:11.5px;color:var(--dim);white-space:nowrap}
.global b{font-family:var(--mono);color:var(--gold);min-width:38px;text-align:right;font-size:12px}
input[type=range]{-webkit-appearance:none;appearance:none;height:4px;background:#334155;border-radius:4px;outline:none;cursor:pointer}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:13px;height:13px;border-radius:50%;
  background:var(--gold);border:2px solid #0b1017;box-shadow:0 0 0 1px var(--gold)}
input[type=range]::-moz-range-thumb{width:13px;height:13px;border-radius:50%;background:var(--gold);border:2px solid #0b1017}
#globalMul{width:110px}
.hint{color:var(--dim2);font-size:12px;margin:0 0 14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(390px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:14px;display:flex;flex-direction:column;gap:10px;transition:.18s}
.card:hover{border-color:#3d5480;transform:translateY(-1px)}
.chead{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.num{font-family:var(--mono);font-size:11px;color:var(--dim2)}
.badge{font-size:10.5px;padding:2px 8px;border-radius:20px;border:1px solid var(--line);color:var(--dim);white-space:nowrap}
.badge.cat{color:var(--acc2);border-color:#2b5c58;background:#102421}
.badge.tech{color:var(--gold);border-color:#5c4a22;background:#241d0e}
.star{margin-left:auto;background:none;border:none;color:var(--dim2);cursor:pointer;font-size:16px;line-height:1;padding:2px 4px}
.star.on{color:var(--gold)}
.prompt{background:#0b1017;border:1px solid #1d2836;border-radius:9px;padding:11px 12px;
  font-family:var(--mono);font-size:12.2px;line-height:1.75;color:#cfdbea;word-break:break-word;
  min-height:74px;white-space:pre-wrap}
.prompt .w{color:var(--gold);background:#2a2210;border-radius:3px;padding:0 2px;box-shadow:inset 0 -1px 0 #7a6020}
.prompt .subw{color:var(--acc2);background:#0f2a27;border-radius:3px;padding:0 2px}
.tip{font-size:12px;color:var(--dim);border-left:2px solid var(--acc);padding-left:10px;line-height:1.6}
.slidwrap{background:#111a25;border:1px solid #223044;border-radius:9px;padding:9px 11px;display:flex;flex-direction:column;gap:7px}
.sl-title{font-size:10.5px;color:var(--dim2);letter-spacing:.6px;text-transform:uppercase}
.sl{display:grid;grid-template-columns:1fr 96px 78px;gap:8px;align-items:center;font-size:11.5px}
.sl .lab{color:var(--dim);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:var(--mono)}
.sl .val{font-family:var(--mono);font-size:11px;color:var(--gold);text-align:right;white-space:nowrap}
.sl.sub .lab{color:var(--acc2)}
.cfoot{display:flex;gap:7px;flex-wrap:wrap;margin-top:auto}
.cfoot .btn{padding:6px 11px;font-size:11.5px}
.empty{grid-column:1/-1;text-align:center;color:var(--dim2);padding:60px 0}
#more{display:block;margin:22px auto 0;min-width:200px}
.section{margin-top:42px;border-top:1px solid var(--line);padding-top:26px}
.section h2{font-size:19px;margin:0 0 6px}
.section .desc{color:var(--dim);font-size:13px;margin-bottom:16px}
.neg{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
.negbox{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px}
.negbox h3{margin:0 0 8px;font-size:13.5px;color:var(--acc2)}
.negbox textarea{width:100%;height:118px;resize:vertical;font-family:var(--mono);font-size:11.5px;line-height:1.6}
.negbox .row{display:flex;justify-content:space-between;align-items:center;margin-top:8px}
.negbox .row small{color:var(--dim2)}
.traybox{position:fixed;right:18px;bottom:18px;z-index:40;width:360px;max-width:calc(100vw - 36px)}
.trayhead{background:var(--acc);color:#0b1017;border-radius:12px 12px 0 0;padding:10px 14px;
  display:flex;justify-content:space-between;align-items:center;cursor:pointer;font-weight:600;font-size:13px}
.traybody{background:var(--card2);border:1px solid var(--line);border-top:none;border-radius:0 0 12px 12px;
  padding:12px;max-height:340px;overflow:auto;display:none}
.traybox.open .traybody{display:block}
.trayitem{background:#0b1017;border:1px solid var(--line);border-radius:7px;padding:7px 9px;margin-bottom:7px;
  font-family:var(--mono);font-size:11px;color:#cfdbea;display:flex;gap:8px;align-items:flex-start}
.trayitem span{flex:1;word-break:break-word;max-height:52px;overflow:hidden}
.trayitem button{background:none;border:none;color:var(--red);cursor:pointer;font-size:13px}
.trayctl{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-top:9px}
.trayctl select{padding:5px 7px;font-size:11.5px;min-width:96px}
.trayctl .btn{padding:6px 10px;font-size:11.5px}
#toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(20px);opacity:0;
  background:var(--acc2);color:#08201d;padding:9px 18px;border-radius:24px;font-weight:600;font-size:13px;
  transition:.25s;pointer-events:none;z-index:60}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
footer{color:var(--dim2);font-size:12px;text-align:center;margin-top:46px}
@media(max-width:640px){.grid{grid-template-columns:1fr}.wrap{padding:0 12px 110px}#q{min-width:100%}.sl{grid-template-columns:1fr 80px 70px}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>Stable Diffusion <span>提示词卡片库</span></h1>
  <div class="sub">600 条可复制提示语 · 60 个场景类别 · 权重滑块实时调节 · 类别 / 技巧 / 关键词筛选 · 拼装台 · 离线单文件</div>
  <div class="stats">
    <div class="stat"><b id="stTotal">600</b><small>提示语总数</small></div>
    <div class="stat"><b id="stCat">60</b><small>场景类别</small></div>
    <div class="stat"><b id="stTech">23</b><small>技巧类型</small></div>
    <div class="stat"><b id="stShown">0</b><small>当前筛选结果</small></div>
  </div>
</header>

<details class="guide">
  <summary>① 提示词结构速览与语法小抄（建议先读）</summary>
  <div class="in">
    <p><b>通用结构：</b><code>主体 subject + 动作/细节 detail + 环境 environment + 光线 lighting + 镜头 camera + 风格 style + 画质 quality</code>。越靠前的词权重越高；逗号分段比长句更利于 SD1.5 解析。</p>
    <table>
      <tr><th>语法</th><th>写法</th><th>作用</th></tr>
      <tr><td>加权 / 降权</td><td><code>(word:1.3)</code> / <code>(word:0.7)</code></td><td>&gt;1 加强，&lt;1 压低；1.2~1.4 最稳</td></tr>
      <tr><td>简写加权</td><td><code>(word)</code> ≈1.1 · <code>((word))</code> ≈1.21 · <code>[word]</code> ≈0.9</td><td>括号叠乘，方括号递减</td></tr>
      <tr><td>分步混合</td><td><code>(A:B:0.6)</code></td><td>到第 60% 采样步从 A 切到 B</td></tr>
      <tr><td>分步替换</td><td><code>[from:to:0.5]</code></td><td>前 50% 步画 from，之后画 to</td></tr>
      <tr><td>交替词</td><td><code>[A|B]</code></td><td>按采样步轮流生效，得到混合质感</td></tr>
      <tr><td>合成 / 分段</td><td><code>A:1 AND B:1.2</code> · <code>… BREAK …</code></td><td>独立条件流合成 / 强制换段编码</td></tr>
      <tr><td>外部模型</td><td><code>&lt;lora:name:0.75&gt;</code> · <code>embedding:xxx</code></td><td>挂载 LoRA / Textual Inversion 触发词</td></tr>
      <tr><td>风格混搭</td><td><code>(styleA:1.1) + (styleB:0.6)</code></td><td>主次分明的双风格</td></tr>
      <tr><td>画质前缀</td><td><code>(masterpiece, best quality:1.2)</code></td><td>整组打包加权，可复用</td></tr>
      <tr><td>镜头 / 画幅</td><td><code>85mm, f/1.4</code> · <code>9:16</code></td><td>配合输出分辨率控制景深与构图</td></tr>
    </table>
    <p><b>模型差异：</b>SD1.5 吃画质词与负面词；SDXL 对负面词依赖降低；FLUX / SD3 更偏好完整自然语言长句，权重语法可弱化。LoRA / Embedding 一般不能跨模型系列混用。</p>
  </div>
</details>

<div class="toolbar">
  <div class="field"><label>关键词搜索</label><input type="text" id="q" placeholder="搜主体 / 风格 / 技巧…"></div>
  <div class="field"><label>按类别筛选</label><select id="catFilter"></select></div>
  <div class="field"><label>按技巧筛选</label><select id="techFilter"></select></div>
  <div class="field"><label>语法特性</label><select id="tagFilter"></select></div>
  <div class="field"><label>快捷</label><div style="display:flex;gap:7px">
    <button class="btn" id="favBtn">★ 仅收藏</button>
    <button class="btn" id="resetBtn">重置</button>
  </div></div>
  <div class="global"><span>全局权重倍率</span><input type="range" id="globalMul" min="0.5" max="1.6" step="0.05" value="1"><b id="gmVal">×1.00</b></div>
  <div class="field"><label>导出</label><div style="display:flex;gap:7px">
    <button class="btn" id="copyShown">复制筛选结果</button>
    <button class="btn" id="exportTxt">下载 .txt</button>
  </div></div>
</div>
<p class="hint">拖动卡片里的滑块可实时改写提示词（金色为原有数值权重、青色为新增的主体前置权重）；复制按钮始终复制<b>当前预览文本</b>。点击「＋拼装台」可把多条提示词拼成一条复合提示词。</p>

<div class="grid" id="grid"></div>
<button class="btn primary" id="more">加载更多（+24）</button>

<div class="section" id="negSec">
  <h2>② 全面通用负面提示词</h2>
  <div class="desc">覆盖画质崩坏、肢体畸形、构图问题、水印文字与低质量。SD1.5 建议用完整版；SDXL / FLUX 可只保留 <code>worst quality, low quality, blurry, watermark, text</code>。文本框可自行编辑后再复制。</div>
  <div class="neg">
    <div class="negbox"><h3>完整版（通用 / SD1.5）</h3><textarea id="neg0">__NEG0__</textarea>
      <div class="row"><small>适配写实 / 动漫 / 插画</small><button class="btn primary cpneg" data-t="0">复制</button></div></div>
    <div class="negbox"><h3>精简版 · 写实 / 摄影向</h3><textarea id="neg1">__NEG1__</textarea>
      <div class="row"><small>更省 token，聚焦结构崩坏</small><button class="btn primary cpneg" data-t="1">复制</button></div></div>
    <div class="negbox"><h3>精简版 · 动漫 / 插画向</h3><textarea id="neg2">__NEG2__</textarea>
      <div class="row"><small>补了 bad eyes / extra tail</small><button class="btn primary cpneg" data-t="2">复制</button></div></div>
  </div>
  <div class="guide" style="margin-top:14px;background:transparent;border:none;padding:0;color:var(--dim);font-size:12.5px">
    使用建议：负面词同样可加权，如 <code>(worst quality:1.4)</code>；若某个负面词导致画面异常（例如「手」被过度抽象、写实图被迫去色），把它降权或删掉即可。SDXL / FLUX 对负面词敏感度低，堆太多反而可能伤画质。
  </div>
</div>

<footer>单文件离线卡片库 · 收藏与拼装台保存在浏览器本地 · 共 600 条提示语 / 60 类 / 权重滑块实时演示</footer>
</div>

<div class="traybox" id="tray">
  <div class="trayhead" id="trayHead"><span>拼装台 <b id="trayCount">0</b></span><span id="trayArrow">▾</span></div>
  <div class="traybody">
    <div id="trayList"></div>
    <div class="trayctl">
      <select id="sep"><option value=", ">逗号 , </option><option value=" AND ">AND 合成</option><option value=" BREAK ">BREAK 分段</option><option value="\n">换行</option></select>
      <button class="btn primary" id="copyTray">复制拼装结果</button>
      <button class="btn ghost" id="clearTray">清空</button>
    </div>
  </div>
</div>
<div id="toast">已复制</div>

<script id="DATA" type="application/json">__PROMPT_DATA__</script>
<script>
(function(){
"use strict";
const D = JSON.parse(document.getElementById('DATA').textContent);
const ITS = D.items, CATS = D.cats, TECHS = D.techs, TAGS = D.tags;
const $ = s => document.querySelector(s);
const $$ = (s, root) => Array.from((root||document).querySelectorAll(s));
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const T0 = String.fromCharCode(0xE000), T1 = String.fromCharCode(0xE001);
const RE_TOK = new RegExp(T0+'(\\d+)'+T1,'g');
const RE_LORA = /<lora:([^:>]+):([\d.]+)>/g;
const RE_W = /\(([^()<>]*?):([\d.]+)\)/g;
const RE_STEP = /\[([^\[\]:]+):([^\[\]:]+):([\d.]+)\]/g;

const state = {
  cat:'ALL', tech:'ALL', tag:'ALL', q:'', favOnly:false,
  globalMul:1, shown:24,
  fav:new Set(JSON.parse(localStorage.getItem('sd_prompt_fav')||'[]')),
  tray:[], vals:{}   // vals[itemId] = {subW, w:{index:value}}
};
function stOf(id){
  if(!state.vals[id]) state.vals[id] = {subW:1, w:{}};
  return state.vals[id];
}
function parse(p){
  let ms=[];
  const grab=(re,type)=>{re.lastIndex=0;let m;while((m=re.exec(p))!==null){
    const base = type==='step' ? parseFloat(m[3]) : parseFloat(m[2]);
    ms.push({start:m.index,end:m.index+m[0].length,raw:m[0],type:type,base:base,m:m});
  }};
  grab(RE_LORA,'lora'); grab(RE_W,'w'); grab(RE_STEP,'step');
  ms.sort((a,b)=>a.start-b.start || b.end-a.end);
  const keep=[]; let last=-1;
  for(const x of ms){ if(x.start>=last){ keep.push(x); last=x.end; } }
  let text='', cur=0, defs=[];
  keep.forEach((x,i)=>{ text += p.slice(cur,x.start)+T0+i+T1; cur=x.end; defs.push(x); });
  text += p.slice(cur);
  return {text:text, defs:defs};
}
const cache = {};
function parsed(it){ if(!cache[it.id]) cache[it.id]=parse(it.prompt); return cache[it.id]; }
function fmt(v){ return String(Number(v.toFixed(2))); }
function finalVal(d, st, i){
  const base = (st.w[i]!==undefined) ? st.w[i] : d.base;
  return d.type==='w' ? base*state.globalMul : base;
}
function rebuild(d, v){
  const f = fmt(v);
  if(d.type==='lora') return '<lora:'+d.m[1]+':'+f+'>';
  if(d.type==='step') return '['+d.m[1]+':'+d.m[2]+':'+f+']';
  const mm = /^(\()(.*):([\d.]+)(\))$/.exec(d.raw);
  return mm ? mm[1]+mm[2]+':'+f+mm[4] : d.raw;
}
function label(d){
  if(d.type==='lora') return 'lora:'+d.m[1];
  if(d.type==='step') return '切换步 '+d.m[1]+'→'+d.m[2];
  const mm = /^\((.*):([\d.]+)\)$/.exec(d.raw);
  return (mm?mm[1]:d.raw).slice(0,42);
}
function plain(it){
  const P=parsed(it), st=stOf(it.id);
  let prefix = st.subW!==1 ? '('+it.subject+':'+fmt(st.subW)+'), ' : '';
  let out = prefix + P.text.replace(RE_TOK, (_,i)=> rebuild(P.defs[+i], finalVal(P.defs[+i], st, +i)));
  return out;
}
function previewHtml(it){
  const P=parsed(it), st=stOf(it.id);
  let prefix = st.subW!==1 ? '<span class="subw">('+esc(it.subject)+':'+fmt(st.subW)+')</span>, ' : '';
  return prefix + esc(P.text).replace(RE_TOK, (_,i)=>{
    const d=P.defs[+i];
    return '<span class="w" data-i="'+i+'">'+esc(rebuild(d, finalVal(d, st, +i)))+'</span>';
  });
}
function slidersHtml(it){
  const P=parsed(it), st=stOf(it.id);
  let rows = '<div class="sl sub"><span class="lab">主体前置权重 → '+esc(it.subject.slice(0,30))+'</span>'+
    '<input type="range" class="subw" min="0.5" max="1.8" step="0.05" value="'+st.subW+'">'+
    '<span class="val" data-sub="1">'+fmt(st.subW)+'</span></div>';
  P.defs.forEach((d,i)=>{
    const min = (d.type==='step'||d.type==='lora')?0:0.1;
    const max = d.type==='step'?1:(d.type==='lora'?1.5:Math.max(2, Math.ceil(d.base*15)/10));
    const stepv = 0.05;
    const v = (st.w[i]!==undefined)?st.w[i]:d.base;
    rows += '<div class="sl"><span class="lab" title="'+esc(d.raw)+'">'+esc(label(d))+'</span>'+
      '<input type="range" class="wr" data-i="'+i+'" min="'+min+'" max="'+max+'" step="'+stepv+'" value="'+v+'">'+
      '<span class="val" data-v="'+i+'">'+fmt(v)+(d.type==='w'&&state.globalMul!==1?' → '+fmt(v*state.globalMul):'')+'</span></div>';
  });
  if(P.defs.length===0) rows += '<div class="sl"><span class="lab">本条使用无数值语法，可用上方主体权重体验加权</span><span></span><span></span></div>';
  return '<div class="slidwrap"><div class="sl-title">权重可视化滑块（拖动即时改写提示词）</div>'+rows+'</div>';
}
function cardHtml(it){
  const on = state.fav.has(it.id);
  return '<div class="card" data-id="'+it.id+'">'+
    '<div class="chead"><span class="num">#'+String(it.id).padStart(3,'0')+'</span>'+
      '<span class="badge cat">'+esc(it.cat)+'</span><span class="badge tech">'+esc(it.tech)+'</span>'+
      '<button class="star'+(on?' on':'')+'" data-act="fav" title="收藏">'+(on?'★':'☆')+'</button></div>'+
    '<div class="prompt">'+previewHtml(it)+'</div>'+
    slidersHtml(it)+
    '<div class="tip">💡 '+esc(it.tip)+'</div>'+
    '<div class="cfoot"><button class="btn primary" data-act="copy">复制提示词</button>'+
      '<button class="btn" data-act="tray">＋拼装台</button>'+
      '<button class="btn ghost" data-act="reset">重置权重</button>'+
      (it.tags||[]).slice(2,5).map(t=>'<span class="badge">'+esc(t)+'</span>').join('')+'</div></div>';
}
function filtered(){
  const q = state.q.trim().toLowerCase();
  return ITS.filter(it=>{
    if(state.cat!=='ALL' && it.cat!==state.cat) return false;
    if(state.tech!=='ALL' && it.tech!==state.tech) return false;
    if(state.tag!=='ALL' && !(it.tags||[]).includes(state.tag)) return false;
    if(state.favOnly && !state.fav.has(it.id)) return false;
    if(q){ const hay=(it.prompt+' '+it.tip+' '+it.cat+' '+it.tech+' '+(it.tags||[]).join(' ')).toLowerCase();
      if(!hay.includes(q)) return false; }
    return true;
  });
}
function render(){
  const f = filtered();
  $('#stShown').textContent = f.length;
  const slice = f.slice(0, state.shown);
  $('#grid').innerHTML = slice.length ? slice.map(cardHtml).join('') : '<div class="empty">没有匹配的提示语，试试重置筛选条件。</div>';
  $('#more').style.display = f.length>state.shown ? 'block':'none';
  $('#more').textContent = '加载更多（再显示 '+Math.min(24, f.length-state.shown)+' 条）';
}
function refreshCard(el){
  const it = ITS[+el.dataset.id-1], st=stOf(it.id), P=parsed(it);
  el.querySelector('.prompt').innerHTML = previewHtml(it);
  $$('.wr', el).forEach(inp=>{
    const i=+inp.dataset.i, d=P.defs[i], v=st.w[i]!==undefined?st.w[i]:d.base;
    inp.value=v;
    const val=el.querySelector('[data-v="'+i+'"]');
    if(val) val.textContent = fmt(v)+(d.type==='w'&&state.globalMul!==1?' → '+fmt(v*state.globalMul):'');
  });
  const sw=el.querySelector('.subw'), sv=el.querySelector('[data-sub]');
  if(sw) sw.value=st.subW; if(sv) sv.textContent=fmt(st.subW);
}
function toast(msg){ const t=$('#toast'); t.textContent=msg; t.classList.add('show'); clearTimeout(t._t); t._t=setTimeout(()=>t.classList.remove('show'),1400); }
function copy(text, msg){
  const done=()=>toast(msg||'已复制到剪贴板');
  if(navigator.clipboard && window.isSecureContext){ navigator.clipboard.writeText(text).then(done).catch(()=>fallback()); }
  else fallback();
  function fallback(){ const ta=document.createElement('textarea'); ta.value=text; ta.style.position='fixed'; ta.style.opacity='0';
    document.body.appendChild(ta); ta.select(); try{document.execCommand('copy');done();}catch(e){toast('复制失败，请手动选择文本');} document.body.removeChild(ta); }
}
function opts(sel, list, allLabel){
  sel.innerHTML = '<option value="ALL">'+allLabel+'</option>'+list.map(x=>'<option value="'+esc(x)+'">'+esc(x)+'</option>').join('');
}
function init(){
  $('#stTotal').textContent = ITS.length; $('#stCat').textContent = CATS.length; $('#stTech').textContent = TECHS.length;
  const catSel=$('#catFilter');
  catSel.innerHTML='<option value="ALL">全部类别（'+ITS.length+'）</option>'+CATS.map(c=>{
    const n=ITS.filter(x=>x.cat===c).length;
    return '<option value="'+esc(c)+'">'+esc(c)+'（'+n+'）</option>';
  }).join('');
  opts($('#techFilter'), TECHS, '全部技巧');
  opts($('#tagFilter'), TAGS.filter(t=>!CATS.includes(t)), '全部语法特性');
  render();
  catSel.addEventListener('change', e=>{state.cat=e.target.value;state.shown=24;render();});
  $('#techFilter').addEventListener('change', e=>{state.tech=e.target.value;state.shown=24;render();});
  $('#tagFilter').addEventListener('change', e=>{state.tag=e.target.value;state.shown=24;render();});
  let qt; $('#q').addEventListener('input', e=>{clearTimeout(qt);qt=setTimeout(()=>{state.q=e.target.value;state.shown=24;render();},180);});
  $('#favBtn').addEventListener('click', e=>{state.favOnly=!state.favOnly;e.target.classList.toggle('on',state.favOnly);state.shown=24;render();});
  $('#resetBtn').addEventListener('click', ()=>{
    state.cat='ALL';state.tech='ALL';state.tag='ALL';state.q='';state.favOnly=false;state.shown=24;state.globalMul=1;
    catSel.value='ALL';$('#techFilter').value='ALL';$('#tagFilter').value='ALL';$('#q').value='';
    $('#favBtn').classList.remove('on');$('#globalMul').value=1;$('#gmVal').textContent='×1.00';render();
  });
  $('#globalMul').addEventListener('input', e=>{
    state.globalMul=parseFloat(e.target.value); $('#gmVal').textContent='×'+state.globalMul.toFixed(2);
    $$('#grid .card').forEach(refreshCard);
  });
  $('#more').addEventListener('click', ()=>{state.shown+=24;render();});
  $('#grid').addEventListener('click', ev=>{
    const btn=ev.target.closest('[data-act]'); if(!btn) return;
    const card=btn.closest('.card'); const it=ITS[+card.dataset.id-1]; const act=btn.dataset.act;
    if(act==='fav'){ if(state.fav.has(it.id))state.fav.delete(it.id);else state.fav.add(it.id);
      localStorage.setItem('sd_prompt_fav',JSON.stringify(Array.from(state.fav)));
      btn.classList.toggle('on',state.fav.has(it.id)); btn.textContent=state.fav.has(it.id)?'★':'☆';
      if(state.favOnly) render(); return; }
    if(act==='copy'){ copy(plain(it),'已复制 #'+it.id+' 提示词'); return; }
    if(act==='tray'){ state.tray.push({id:it.id,text:plain(it)}); renderTray(); $('#tray').classList.add('open'); $('#trayArrow').textContent='▴'; toast('已加入拼装台'); return; }
    if(act==='reset'){ delete state.vals[it.id]; refreshCard(card); return; }
  });
  $('#grid').addEventListener('input', ev=>{
    const inp=ev.target; if(inp.type!=='range') return;
    const card=inp.closest('.card'); const it=ITS[+card.dataset.id-1]; const st=stOf(it.id);
    if(inp.classList.contains('subw')){ st.subW=parseFloat(inp.value);
      card.querySelector('[data-sub]').textContent=fmt(st.subW); card.querySelector('.prompt').innerHTML=previewHtml(it); return; }
    const i=+inp.dataset.i; st.w[i]=parseFloat(inp.value);
    const P=parsed(it), d=P.defs[i];
    const span=card.querySelector('.prompt .w[data-i="'+i+'"]');
    if(span) span.textContent=rebuild(d, finalVal(d,st,i));
    const val=card.querySelector('[data-v="'+i+'"]');
    if(val) val.textContent=fmt(st.w[i])+(d.type==='w'&&state.globalMul!==1?' → '+fmt(st.w[i]*state.globalMul):'');
  });
  $('#copyShown').addEventListener('click', ()=>{
    const f=filtered().slice(0,50);
    copy(f.map(x=>'#'+x.id+' ['+x.cat+'] '+plain(x)).join('\n\n'), '已复制前 '+f.length+' 条（上限 50）');
  });
  $('#exportTxt').addEventListener('click', ()=>{
    const f=filtered();
    const txt='SD 提示词卡片库 · 筛选导出（'+f.length+' 条）\n\n'+f.map(x=>'#'+x.id+' ['+x.cat+' / '+x.tech+']\n'+plain(x)+'\n技巧：'+x.tip).join('\n\n')+'\n\n--- 通用负面提示词 ---\n'+$('#neg0').value;
    const b=new Blob([txt],{type:'text/plain;charset=utf-8'}); const a=document.createElement('a');
    a.href=URL.createObjectURL(b); a.download='SD提示词_筛选导出.txt'; a.click(); URL.revokeObjectURL(a.href);
    toast('已导出 '+f.length+' 条');
  });
  $$('.cpneg').forEach(b=>b.addEventListener('click',()=>copy($('#neg'+b.dataset.t).value,'已复制负面提示词')));
  $('#trayHead').addEventListener('click',()=>{const t=$('#tray');t.classList.toggle('open');$('#trayArrow').textContent=t.classList.contains('open')?'▴':'▾';});
  $('#clearTray').addEventListener('click',()=>{state.tray=[];renderTray();});
  $('#copyTray').addEventListener('click',()=>{
    if(!state.tray.length){toast('拼装台是空的');return;}
    let sep=$('#sep').value; if(sep==='\\n')sep='\n';
    copy(state.tray.map(x=>x.text).join(sep),'已复制拼装结果（'+state.tray.length+' 条）');
  });
  renderTray();
}
function renderTray(){
  $('#trayCount').textContent=state.tray.length;
  $('#trayList').innerHTML=state.tray.length?state.tray.map((x,i)=>
    '<div class="trayitem"><span>#'+x.id+' '+esc(x.text.slice(0,120))+(x.text.length>120?'…':'')+'</span><button data-k="'+i+'" title="移除">✕</button></div>').join('')
    :'<div style="color:var(--dim2);font-size:12px;text-align:center;padding:14px 0">还没有内容，点击卡片上的「＋拼装台」添加</div>';
  $$('#trayList button').forEach(b=>b.addEventListener('click',()=>{state.tray.splice(+b.dataset.k,1);renderTray();}));
}
init();
})();
</script>
</body>
</html>
"""

HTML = HTML.replace("__PROMPT_DATA__", json_str)
HTML = HTML.replace("__NEG0__", _html.escape(NEG_FULL).replace("&#x27;", "'"))
HTML = HTML.replace("__NEG1__", _html.escape(NEG_PHOTO).replace("&#x27;", "'"))
HTML = HTML.replace("__NEG2__", _html.escape(NEG_ANIME).replace("&#x27;", "'"))

out = "/data/workspace/SD提示词卡片库.html"
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML)

# 自检
raw = open(out, encoding="utf-8").read()
m = re.search(r'<script id="DATA" type="application/json">(.*?)</script>', raw, re.S)
chk = json.loads(m.group(1))
print("file:", out)
print("bytes:", len(raw.encode("utf-8")))
print("items:", len(chk["items"]), "cats:", len(chk["cats"]), "techs:", len(chk["techs"]), "tags:", len(chk["tags"]))
print("legacy:", sum(1 for x in chk["items"] if x["legacy"]), "new:", sum(1 for x in chk["items"] if not x["legacy"]))
print("unique prompts:", len(set(x["prompt"] for x in chk["items"])))
print("has slider js:", "globalMul" in raw and "权重可视化滑块" in raw)

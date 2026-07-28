import json
from collections import Counter

data = [json.loads(l) for l in open(r'D:\AI-agent\YuanQi Agent\agent\data\medical.json', encoding='utf-8')]

print('=== 数据概览 ===')
print(f'总记录数: {len(data)}')
print(f'文件大小: ~45MB')
print()

print('=== 字段列表与类型 ===')
for k, v in data[0].items():
    print(f'  {k}: {type(v).__name__}')
print()

print('=== 字段非空统计 ===')
keys = data[0].keys()
total = len(data)
for k in keys:
    filled = sum(1 for d in data if d.get(k))
    print(f'  {k}: {filled}/{total} ({filled*100//total}%)')
print()

print('=== 科室分布 ===')
cats = Counter(c for d in data for c in d.get('category', []))
for c, n in cats.most_common(15):
    print(f'  {c}: {n}')
print()

print('=== 样例疾病(前15) ===')
for d in data[:15]:
    print(f'  {d["name"]}')
print()

# 检查是否有重复疾病名
names = [d['name'] for d in data]
dup = Counter(names)
dups = {k: v for k, v in dup.items() if v > 1}
print(f'=== 重复疾病名: {len(dups)} 个 ===')
for k, v in list(dups.items())[:10]:
    print(f'  {k}: {v}次')
print()

# 检查字段中有do_eat, not_eat, recommand_eat
has_do_eat = sum(1 for d in data if d.get('do_eat'))
has_not_eat = sum(1 for d in data if d.get('not_eat'))
has_recommand_eat = sum(1 for d in data if d.get('recommand_eat'))
print(f'=== 饮食相关字段 ===')
print(f'  do_eat: {has_do_eat}/{total}')
print(f'  not_eat: {has_not_eat}/{total}')
print(f'  recommand_eat: {has_recommand_eat}/{total}')
print()

# 检查字段中是否有easy_get
has_easy_get = sum(1 for d in data if d.get('easy_get'))
print(f'=== 易感人群字段 ===')
print(f'  easy_get: {has_easy_get}/{total}')

import json, urllib.request, re, sys, os
from datetime import datetime, timezone, timedelta

API = 'https://api.hostmonit.com/get_optimization_ip'
PORTS = os.environ.get('PORTS', '443,2053,8443').split(',')
MAX_PER_COLO = int(os.environ.get('MAX_PER_COLO', '3'))

ALLOWED_COLOS = {'HKG', 'NRT', 'KIX', 'ICN', 'SIN', 'LAX', 'SJC', 'SEA', 'ORD', 'IAD', 'LHR'}

COLO_FLAG = {
    'HKG': '🇭🇰HK', 'NRT': '🇯🇵JP', 'KIX': '🇯🇵JP',
    'ICN': '🇰🇷KR', 'SIN': '🇸🇬SG',
    'LAX': '🇺🇸LA', 'SJC': '🇺🇸SJ', 'SEA': '🇺🇸SE', 'ORD': '🇺🇸CH', 'IAD': '🇺🇸DC',
    'LHR': '🇬🇧UK',
}

ISP_NAME = {'CM': '移动', 'CU': '联通', 'CT': '电信'}

# 额外 IP 列表源（纯文本 / HTML）
IP_LIST_URLS = {
    'ipdb优选': 'https://ipdb.030101.xyz/bestcfv4/',
    'WeTest优选': 'https://www.wetest.vip/page/cloudflare/address_v4.html',
}

# GitHub CSV 源（Actions 可直连 GitHub，无需代理）
CSV_URLS = {
    'IPDB-CSV': 'https://raw.githubusercontent.com/ymyuuu/IPDB/refs/heads/main/BestCF/ipv4.csv',
}


def fetch_url(url, timeout=10):
    """通用 URL 获取"""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read().decode('utf-8')


def fetch_ip_list(name, url):
    """从纯文本或 HTML 中提取 IPv4 地址"""
    try:
        text = fetch_url(url)
        raw = re.findall(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', text)
        ips = []
        for ip in raw:
            octets = ip.split('.')
            if all(0 <= int(o) <= 255 for o in octets):
                first = int(octets[0])
                if first in (10, 127, 0) or ip.startswith('192.168.'):
                    continue
                ips.append(ip)
        ips = list(dict.fromkeys(ips))  # 去重保序
        print(f'  {name}: {len(ips)} 个 IP')
        return ips
    except Exception as e:
        print(f'  {name}: 获取失败 - {e}')
        return []


def fetch_csv(name, url):
    """从 CSV 文件提取 IP（第一列为 IP）"""
    try:
        text = fetch_url(url)
        lines = text.strip().split('\n')
        ips = []
        for line in lines:
            ip = line.split(',')[0].strip()
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                ips.append(ip)
        ips = list(dict.fromkeys(ips))
        print(f'  {name}: {len(ips)} 个 IP (CSV)')
        return ips
    except Exception as e:
        print(f'  {name}: 获取失败 - {e}')
        return []


# ===== 主逻辑 =====

# 1. hostmonit API
all_ips = {}  # ip -> item（保留最低延迟）
for isp in ['CM', 'CU', 'CT']:
    try:
        req = urllib.request.Request(API, method='POST',
            data=json.dumps({'key': 'iDetkOys', 'type': 'v4', 'isp': isp}).encode(),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read())

        items = data.get('info', [])
        print(f'\n--- {ISP_NAME[isp]}({isp}) 返回 {len(items)} 条 ---')
        for item in items:
            colo = item.get('colo', '?')
            print(f'  {item["ip"]:>15}  {item["latency"]:>4}ms  colo={colo}  node={item.get("node", "?")}')
        for item in items:
            ip = item['ip']
            if ip not in all_ips or item['latency'] < all_ips[ip]['latency']:
                item['source'] = 'hostmonit'
                all_ips[ip] = item
    except Exception as e:
        print(f'{ISP_NAME.get(isp, isp)} 获取失败: {e}', file=sys.stderr)

# 2. 额外 IP 列表源
extra_ips = {}  # ip -> source_name
print(f'\n--- 额外 IP 列表源 ---')
for name, url in IP_LIST_URLS.items():
    ips = fetch_ip_list(name, url)
    for ip in ips:
        if ip not in extra_ips:
            extra_ips[ip] = name

for name, url in CSV_URLS.items():
    ips = fetch_csv(name, url)
    for ip in ips:
        if ip not in extra_ips:
            extra_ips[ip] = name

# 将额外 IP 合并到 all_ips（如果不存在的话，记录来源）
for ip, src_name in extra_ips.items():
    if ip not in all_ips:
        all_ips[ip] = {'ip': ip, 'colo': 'Unknown', 'latency': 0, 'source': src_name}

print(f'\n合并后总计: {len(all_ips)} 个唯一 IP')

# 3. 按地区分组
grouped = {}
ungrouped = []
for item in all_ips.values():
    colo = item.get('colo', 'Unknown')
    if colo in ALLOWED_COLOS:
        grouped.setdefault(colo, []).append(item)
    else:
        ungrouped.append(item)

# 4. 生成结果
bjt = datetime.now(timezone(timedelta(hours=8)))
lines = [f'# 更新时间: {bjt.strftime("%Y-%m-%d %H:%M")} 北京时间  |  端口: {",".join(p.strip() for p in PORTS)}']
seen = set()

# 先输出有地区标签的
for colo in sorted(grouped.keys()):
    ips = grouped[colo]
    ips.sort(key=lambda x: x.get('latency', 9999))
    flag = COLO_FLAG.get(colo, colo)
    for item in ips[:MAX_PER_COLO]:
        for port in PORTS:
            key = f'{item["ip"]}:{port.strip()}'
            if key not in seen:
                seen.add(key)
                lines.append(f'{key}#{flag}')

# 再输出无地区标签的（额外源补充的 IP）
for item in ungrouped:
    src = item.get('source', 'CF')
    for port in PORTS:
        key = f'{item["ip"]}:{port.strip()}'
        if key not in seen:
            seen.add(key)
            lines.append(f'{key}#{src}')

output = '\n'.join(lines)

os.makedirs('public', exist_ok=True)
with open('public/cfip.txt', 'w', encoding='utf-8') as f:
    f.write(output)

# 输出摘要
print(f'\n=== 最终结果 ===')
print(f'唯一 IP: {len(all_ips)} 个')
print(f'有地区标签: {sum(len(v) for v in grouped.values())} 个 ({", ".join(sorted(grouped.keys()))})')
print(f'无地区标签: {len(ungrouped)} 个')
print(f'输出条目: {len(lines) - 1} 条')
print(f'端口: {", ".join(p.strip() for p in PORTS)}')
print(f'\n{output}')

import urllib.request
import re
import sys
import os

PORTS = os.environ.get('PORTS', '443,2053,8443').split(',')
# 由于不再按地区分组，这里设置每个源最多提取的 IP 数量，避免生成文件过大
MAX_IPS_PER_SOURCE = int(os.environ.get('MAX_IPS', '20')) 

# 仅保留您指定的两个优选源
IP_LIST_URLS = {
    'ipdb优选': 'https://ipdb.030101.xyz/bestcfv4/',
    'WeTest优选': 'https://www.wetest.vip/page/cloudflare/address_v4.html',
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
        # 正则匹配 IPv4
        raw = re.findall(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', text)
        ips = []
        for ip in raw:
            octets = ip.split('.')
            if all(0 <= int(o) <= 255 for o in octets):
                first = int(octets[0])
                # 过滤局域网和特殊 IP
                if first in (10, 127, 0) or ip.startswith('192.168.'):
                    continue
                ips.append(ip)
        ips = list(dict.fromkeys(ips))  # 去重保序
        print(f'  {name}: 成功抓取 {len(ips)} 个 IP')
        return ips
    except Exception as e:
        print(f'  {name}: 获取失败 - {e}', file=sys.stderr)
        return []

# ===== 主逻辑 =====
all_ips = {}

print(f'\n--- 开始获取额外 IP 列表源 ---')
for name, url in IP_LIST_URLS.items():
    ips = fetch_ip_list(name, url)
    # 取前 MAX_IPS_PER_SOURCE 个 IP，您也可以去掉切片限制以获取全部 IP
    for ip in ips[:MAX_IPS_PER_SOURCE]:
        if ip not in all_ips:
            all_ips[ip] = name

# 生成结果
lines = []
seen = set()

for ip, source_name in all_ips.items():
    for port in PORTS:
        key = f'{ip}:{port.strip()}'
        if key not in seen:
            seen.add(key)
            # 这里的备注（Flag）使用源名称，不再使用 Colo 地区代码
            lines.append(f'{key}#{source_name}')

output = '\n'.join(lines)

os.makedirs('public', exist_ok=True)
with open('public/cfip.txt', 'w', encoding='utf-8') as f:
    f.write(output)

# 输出摘要
print(f'\n=== 最终结果 ===')
print(f'唯一 IP: {len(all_ips)} 个')
print(f'来源覆盖: {", ".join(IP_LIST_URLS.keys())}')
print(f'输出条目: {len(lines)} 条')
print(f'端口: {", ".join(p.strip() for p in PORTS)}')
print(f'\n{output}')

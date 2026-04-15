import json, urllib.request, sys, os
from datetime import datetime

API = 'https://api.hostmonit.com/get_optimization_ip'
PORTS = os.environ.get('PORTS', '443,2053,8443').split(',')
MAX_PER_COLO = int(os.environ.get('MAX_PER_COLO', '3'))
COLO_FLAG = {
    'HKG': '🇭🇰HK', 'SIN': '🇸🇬SG', 'NRT': '🇯🇵JP', 'ICN': '🇰🇷KR',
    'LAX': '🇺🇸LA', 'SJC': '🇺🇸SJ', 'SEA': '🇺🇸SE', 'FRA': '🇩🇪DE',
    'LHR': '🇬🇧UK', 'CDG': '🇫🇷FR', 'KIX': '🇯🇵JP', 'TPE': '🇹🇼TW',
}

all_ips = {}
for isp in ['CM', 'CU', 'CT']:
    try:
        req = urllib.request.Request(API, method='POST',
            data=json.dumps({'key': 'iDetkOys', 'type': 'v4', 'isp': isp}).encode(),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read())
        for item in data.get('info', []):
            ip = item['ip']
            if ip not in all_ips or item['latency'] < all_ips[ip]['latency']:
                all_ips[ip] = item
    except Exception as e:
        print(f'{isp} 获取失败: {e}', file=sys.stderr)

grouped = {}
for item in all_ips.values():
    colo = item.get('colo', 'Unknown')
    grouped.setdefault(colo, []).append(item)

lines = [f'# 更新时间: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}']
for colo, ips in sorted(grouped.items()):
    ips.sort(key=lambda x: x['latency'])
    flag = COLO_FLAG.get(colo, colo)
    for item in ips[:MAX_PER_COLO]:
        for port in PORTS:
            lines.append(f'{item["ip"]}:{port.strip()}#{flag}-{item["latency"]}ms')

output = '\n'.join(lines)
print(output)

os.makedirs('public', exist_ok=True)
with open('public/cfip.txt', 'w') as f:
    f.write(output)

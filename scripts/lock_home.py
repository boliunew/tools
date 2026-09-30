# Usage: python3 scripts/lock_home.py <password> index.html   (re-run to change the password)
import hashlib, os, sys, re
pw = sys.argv[1]; path = sys.argv[2]
salt = os.urandom(12).hex()
h = hashlib.sha256((salt + pw).encode()).digest()
for _ in range(19999): h = hashlib.sha256(h).digest()
k = h.hex(); check = hashlib.sha256(k.encode()).hexdigest()
gate = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'home_gate.js')).read().replace('__SALT__', salt).replace('__CHECK__', check)
s = open(path).read()
s = re.sub(r'\n<!--GATE-->.*?<!--/GATE-->', '', s, flags=re.S)
s = re.sub(r'\n<!--GATEUI-->.*?<!--/GATEUI-->', '', s, flags=re.S)
s = re.sub(r'<button class="lockbtn".*?</button>\n', '', s)
head = """
<!--GATE--><meta name="robots" content="noindex,nofollow">
<style>
html.locked main{display:none}
#gate{display:none;max-width:360px;margin:0 auto;padding:18vh 16px 40px;text-align:center}
html.locked #gate{display:block}
#gate h2{font-size:22px;margin:0 0 6px}#gate p{color:var(--soft);font-size:14px;margin:0 0 18px}
#gate input[type=password]{width:100%;font-size:17px;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--ink)}
#gate button{width:100%;margin-top:10px;font-size:16px;font-weight:600;padding:12px;border:0;border-radius:12px;background:var(--accent);color:#fff;cursor:pointer}
#gate label{display:block;margin-top:12px;font-size:14px;color:var(--soft)}
#gmsg{min-height:22px;margin-top:10px;color:#C8412B;font-size:14px}
.lockbtn{display:block;margin:24px auto 0;background:none;border:0;color:var(--soft);font-size:13px;cursor:pointer}
</style>
<script>""" + gate + """</script><!--/GATE-->"""
s = s.replace('</head>', head + '\n</head>', 1)
ui = """
<!--GATEUI--><div id="gate"><h2>🔒 我的工具</h2><p>请输入密码</p><form onsubmit="return __gate()"><input type="password" id="gpw" autocomplete="current-password" placeholder="密码"><button type="submit">进入</button><label><input type="checkbox" id="grem" checked> 在这台设备上记住我</label></form><div id="gmsg"></div></div><!--/GATEUI-->"""
s = s.replace('<body>', '<body>' + ui, 1)
s = s.replace('</main>', '<button class="lockbtn" onclick="__lock()">🔒 退出（这台设备需要重新输密码）</button>\n</main>', 1)
open(path, 'w').write(s)
print('ok', salt)

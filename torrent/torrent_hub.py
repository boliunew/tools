# -*- coding: utf-8 -*-
"""
🧲 种子下载器 · 边下边播（torrent_hub.py）

在自己电脑上跑的网页版下载器：
  · 磁力链接、.torrent 文件 / 网址、http(s) / ftp 直链、迅雷 thunder://、QQ旋风 qqdl://、快车 flashget:// 都能加
  · 每个文件都能「▶ 直接播」：边下边播，拖进度条会优先下载那一段；浏览器放不了的格式一键交给 VLC / PotPlayer
  · 关掉再开会接着下（自动保存进度）

用法（Windows / Mac / Linux 都行）：
    pip install libtorrent
    python torrent_hub.py              只在本机用：浏览器打开 http://127.0.0.1:8800
    python torrent_hub.py --lan        让同一个 Wi-Fi / Tailscale 里的手机也能打开和播放
    python torrent_hub.py --port 9000 --dir D:\\Downloads

只用到 Python 自带的库和 libtorrent，一个文件。
"""
import argparse, base64, json, mimetypes, os, re, shutil, socket, subprocess, sys, threading, time, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    import libtorrent as lt
except ImportError:
    print("没装 libtorrent。先运行：pip install libtorrent")
    sys.exit(1)

VERSION = "2.0"
HOME = os.path.expanduser("~")
STATE_DIR = os.path.join(HOME, ".torrent_hub")
os.makedirs(STATE_DIR, exist_ok=True)
CONF_PATH = os.path.join(STATE_DIR, "config.json")
MEDIA = {".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".wmv", ".flv", ".ts", ".m2ts", ".mpg", ".mpeg", ".rmvb", ".rm", ".3gp",
         ".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus", ".ape", ".wma"}
AUDIO = {".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus", ".ape", ".wma"}
SUBS = {".srt", ".vtt", ".ass", ".ssa"}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def load_conf():
    c = {"dir": os.path.join(HOME, "Downloads", "TorrentHub"), "pause_done": False, "max_down": 0, "max_up": 0}
    try:
        with open(CONF_PATH, encoding="utf-8") as f:
            c.update(json.load(f))
    except Exception:
        pass
    return c


CONF = load_conf()


def save_conf():
    with open(CONF_PATH, "w", encoding="utf-8") as f:
        json.dump(CONF, f, ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ libtorrent 会话
SES = lt.session({
    "listen_interfaces": "0.0.0.0:6881,[::]:6881",
    "enable_dht": True, "enable_lsd": True, "enable_upnp": True, "enable_natpmp": True,
    "alert_mask": lt.alert_category.status | lt.alert_category.error | lt.alert_category.storage,
    "user_agent": "TorrentHub/" + VERSION + " libtorrent/" + lt.__version__,
    "download_rate_limit": int(CONF.get("max_down", 0)) * 1024,
    "upload_rate_limit": int(CONF.get("max_up", 0)) * 1024,
    # 常用的公共 DHT 引导节点，磁力链接没 tracker 时也能找到人
    "dht_bootstrap_nodes": "router.bittorrent.com:6881,router.utorrent.com:6881,dht.transmissionbt.com:6881,dht.libtorrent.org:25401",
})
LOCK = threading.RLock()
MAGNETS = {}          # hash -> 磁力链接（还没拿到种子信息时用来恢复）
ADDED = {}            # hash -> 添加时间
STREAMING = {}        # hash -> 最后一次播放的时间（播放中的任务优先按顺序下）
MAG_PATH = os.path.join(STATE_DIR, "magnets.json")
TRACKERS = [   # 给磁力链接补几个公共 tracker，找人更快
    "udp://tracker.opentrackr.org:1337/announce", "udp://open.stealth.si:80/announce", "udp://tracker.torrent.eu.org:451/announce",
    "udp://exodus.desync.com:6969/announce", "udp://open.demonii.com:1337/announce", "udp://tracker.openbittorrent.com:6969/announce",
]


def ih(h):
    try:
        return str(h.info_hashes().get_best())
    except Exception:
        return str(h.info_hash())


def handles():
    return [h for h in SES.get_torrents() if h.is_valid()]


def find(hs):
    for h in handles():
        if ih(h) == hs:
            return h
    return None


def save_magnets():
    with LOCK:
        with open(MAG_PATH, "w", encoding="utf-8") as f:
            json.dump({"m": MAGNETS, "t": ADDED}, f)


def add_params(atp):
    atp.save_path = CONF["dir"]
    os.makedirs(CONF["dir"], exist_ok=True)
    for t in TRACKERS:
        if t not in atp.trackers:
            atp.trackers.append(t)
    h = SES.add_torrent(atp)
    hs = ih(h)
    with LOCK:
        ADDED.setdefault(hs, time.time())
    return h, hs


def add_magnet(uri):
    atp = lt.parse_magnet_uri(uri)
    peers = list(atp.peers)
    h, hs = add_params(atp)
    for pe in peers:          # 磁力里带了 x.pe 节点：已有的任务也直接连上去
        try:
            h.connect_peer(pe)
        except Exception:
            pass
    with LOCK:
        MAGNETS.setdefault(hs, uri)
    save_magnets()
    return hs


def add_torrent_bytes(data):
    ti = lt.torrent_info(lt.bdecode(data))
    atp = lt.add_torrent_params()
    atp.ti = ti
    h, hs = add_params(atp)
    save_magnets()
    h.save_resume_data(lt.save_resume_flags_t.save_info_dict)
    return hs


def restore():
    try:
        with open(MAG_PATH, encoding="utf-8") as f:
            d = json.load(f)
            MAGNETS.update(d.get("m", {}))
            ADDED.update(d.get("t", {}))
    except Exception:
        pass
    done = set()
    for fn in os.listdir(STATE_DIR):
        if not fn.endswith(".resume"):
            continue
        try:
            with open(os.path.join(STATE_DIR, fn), "rb") as f:
                atp = lt.read_resume_data(f.read())
            h = SES.add_torrent(atp)
            done.add(ih(h))
        except Exception as e:
            print("恢复失败", fn, e)
    for hs, uri in list(MAGNETS.items()):
        if hs not in done:
            try:
                atp = lt.parse_magnet_uri(uri)
                atp.save_path = CONF["dir"]
                SES.add_torrent(atp)
            except Exception as e:
                print("恢复磁力失败", hs, e)


def resume_path(hs):
    return os.path.join(STATE_DIR, hs + ".resume")


def save_all_resume():
    for h in handles():
        try:
            if h.need_save_resume_data() or True:
                h.save_resume_data(lt.save_resume_flags_t.save_info_dict)
        except Exception:
            pass


def alert_loop():
    last_save = time.time()
    while True:
        SES.wait_for_alert(500)
        for a in SES.pop_alerts():
            try:
                if isinstance(a, lt.save_resume_data_alert):
                    data = lt.write_resume_data_buf(a.params)
                    hs = ih(a.handle)
                    with open(resume_path(hs), "wb") as f:
                        f.write(data)
                elif isinstance(a, lt.metadata_received_alert):
                    a.handle.save_resume_data(lt.save_resume_flags_t.save_info_dict)
                elif isinstance(a, lt.torrent_finished_alert):
                    a.handle.save_resume_data(lt.save_resume_flags_t.save_info_dict)
                    if CONF.get("pause_done"):
                        a.handle.unset_flags(lt.torrent_flags.auto_managed)
                        a.handle.pause()
            except Exception as e:
                print("alert", e)
        if time.time() - last_save > 60:
            last_save = time.time()
            save_all_resume()
        # 播放超过 10 分钟没动静，就不再强制按顺序下
        now = time.time()
        for hs, t in list(STREAMING.items()):
            if now - t > 600:
                STREAMING.pop(hs, None)
                h = find(hs)
                if h:
                    set_seq(h, False)


def set_seq(h, on):
    try:
        if on:
            h.set_flags(lt.torrent_flags.sequential_download)
        else:
            h.unset_flags(lt.torrent_flags.sequential_download)
    except Exception:
        try:
            h.set_sequential_download(on)
        except Exception:
            pass


def is_pad(fs, i):
    try:
        return bool(fs.file_flags(i) & lt.file_storage.flag_pad_file)
    except Exception:
        return "/.pad/" in fs.file_path(i).replace("\\", "/")


def is_paused(st):
    try:
        return bool(st.flags & lt.torrent_flags.paused)
    except Exception:
        return bool(getattr(st, "paused", False))


STATES = {0: "排队检查", 1: "检查文件", 2: "找种子信息", 3: "下载中", 4: "已完成", 5: "做种中", 6: "分配空间", 7: "检查续传"}


def torrent_json(h, files=False):
    st = h.status()
    hs = ih(h)
    d = {"id": hs, "kind": "bt", "name": st.name or MAGNETS.get(hs, hs)[:60], "progress": round(st.progress * 100, 1),
         "down": st.download_rate, "up": st.upload_rate, "peers": st.num_peers, "seeds": st.num_seeds,
         "size": st.total_wanted, "done": st.total_wanted_done, "meta": st.has_metadata, "paused": is_paused(st),
         "state": STATES.get(int(st.state), str(st.state)), "added": ADDED.get(hs, 0), "streaming": hs in STREAMING,
         "dir": st.save_path, "err": str(st.errc.message()) if st.errc.value() else ""}
    if st.has_metadata:      # 「直接播」：挑最大的视频/音频文件，同时带上字幕
        try:
            fs0 = h.torrent_file().files()
            best, subs = -1, []
            for i in range(fs0.num_files()):
                if is_pad(fs0, i):
                    continue
                ext = os.path.splitext(fs0.file_path(i))[1].lower()
                if ext in SUBS:
                    subs.append(i)
                elif ext in MEDIA and (best < 0 or fs0.file_size(i) > fs0.file_size(best)):
                    best = i
            if best >= 0:
                n0 = os.path.basename(fs0.file_path(best))
                d["play"] = {"i": best, "name": n0, "s": ",".join(map(str, subs)) if os.path.splitext(n0)[1].lower() not in AUDIO else ""}
        except Exception:
            pass
    left = st.total_wanted - st.total_wanted_done
    d["eta"] = int(left / st.download_rate) if st.download_rate > 1024 and left > 0 else -1
    if files and st.has_metadata:
        ti = h.torrent_file()
        fs = ti.files()
        prog = h.file_progress()
        prio = h.get_file_priorities()
        out = []
        for i in range(fs.num_files()):
            if is_pad(fs, i):      # 种子里用来对齐的空白填充文件，不显示
                continue
            p = fs.file_path(i)
            ext = os.path.splitext(p)[1].lower()
            sz = fs.file_size(i)
            out.append({"i": i, "path": p, "name": os.path.basename(p), "size": sz, "done": prog[i], "pct": round(prog[i] * 100.0 / sz, 1) if sz else 100,
                        "media": ext in MEDIA, "audio": ext in AUDIO, "sub": ext in SUBS, "skip": prio[i] == 0})
        d["files"] = out
    return d


# ------------------------------------------------------------------ 直链下载（http / ftp）
DIRECT = {}   # id -> dict


def decode_link(s):
    """迅雷 / QQ旋风 / 快车的专用链接，里面其实是 base64 包着的普通网址"""
    s = s.strip()
    low = s.lower()
    try:
        if low.startswith("thunder://"):
            u = base64.b64decode(s[10:] + "===").decode("utf-8", "ignore")
            return u[2:-2] if u.startswith("AA") and u.endswith("ZZ") else u
        if low.startswith("qqdl://"):
            return base64.b64decode(s[7:] + "===").decode("utf-8", "ignore")
        if low.startswith("flashget://"):
            u = base64.b64decode(s[11:].split("&")[0] + "===").decode("utf-8", "ignore")
            return u.replace("[FLASHGET]", "")
    except Exception:
        pass
    return s


def safe_name(n):
    n = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", n).strip(" .")
    return n[:180] or "download"


def direct_worker(t):
    url = t["url"]
    try:
        while True:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            have = os.path.getsize(t["path"]) if os.path.exists(t["path"]) else 0
            if have:
                req.add_header("Range", "bytes=%d-" % have)
            r = urllib.request.urlopen(req, timeout=30)
            if have and r.status != 206:
                have = 0
            total = r.headers.get("Content-Range")
            if total and "/" in total:
                t["size"] = int(total.split("/")[-1]) if total.split("/")[-1].isdigit() else 0
            elif r.headers.get("Content-Length"):
                t["size"] = have + int(r.headers["Content-Length"])
            t["done"] = have
            t["state"] = "下载中"
            last, lastb = time.time(), have
            with open(t["path"], "ab" if have else "wb") as f:
                while True:
                    if t.get("stop"):
                        t["state"] = "已暂停"
                        t["rate"] = 0
                        return
                    b = r.read(256 * 1024)
                    if not b:
                        break
                    f.write(b)
                    t["done"] += len(b)
                    now = time.time()
                    if now - last >= 1:
                        t["rate"] = int((t["done"] - lastb) / (now - last))
                        last, lastb = now, t["done"]
            break
        t["rate"] = 0
        t["state"] = "已完成" if not t["size"] or t["done"] >= t["size"] else "未下完（服务器断开）"
    except Exception as e:
        t["rate"] = 0
        t["state"] = "出错"
        t["err"] = str(e)[:200]


def add_direct(url, first=None):
    name = safe_name(urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url).path)) or "download")
    os.makedirs(CONF["dir"], exist_ok=True)
    path = os.path.join(CONF["dir"], name)
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(path) and not any(t["path"] == path for t in DIRECT.values()):
        path = "%s (%d)%s" % (base, n, ext)
        n += 1
    tid = "d%d" % int(time.time() * 1000)
    t = {"id": tid, "url": url, "name": os.path.basename(path), "path": path, "size": 0, "done": 0, "rate": 0, "state": "连接中", "added": time.time()}
    DIRECT[tid] = t
    threading.Thread(target=direct_worker, args=(t,), daemon=True).start()
    return tid


def direct_json(t):
    ext = os.path.splitext(t["name"])[1].lower()
    return {"id": t["id"], "kind": "http", "name": t["name"], "progress": round(t["done"] * 100.0 / t["size"], 1) if t["size"] else 0,
            "down": t.get("rate", 0), "up": 0, "peers": 0, "seeds": 0, "size": t["size"], "done": t["done"], "meta": True,
            "paused": t["state"] == "已暂停", "state": t["state"], "added": t["added"], "err": t.get("err", ""), "dir": os.path.dirname(t["path"]),
            "eta": int((t["size"] - t["done"]) / t["rate"]) if t.get("rate") and t["size"] else -1,
            "play": {"i": 0, "name": t["name"], "s": ""} if ext in MEDIA else None,
            "running": t["state"] in ("连接中", "下载中"),
            "files": [{"i": 0, "path": t["name"], "name": t["name"], "size": t["size"], "done": t["done"], "pct": round(t["done"] * 100.0 / t["size"], 1) if t["size"] else 0,
                       "media": ext in MEDIA, "audio": ext in AUDIO, "sub": ext in SUBS, "skip": False}]}


def add_link(s):
    s = decode_link(s)
    if not s:
        return None, "空的"
    if s.lower().startswith("magnet:"):
        return add_magnet(s), None
    if re.fullmatch(r"[0-9a-fA-F]{40}|[A-Z2-7]{32}", s):          # 只给了 info hash
        return add_magnet("magnet:?xt=urn:btih:" + s), None
    if s.lower().startswith("ed2k://"):
        return None, "电驴 ed2k 链接这个工具不支持"
    if not re.match(r"^(https?|ftp)://", s, re.I):
        return None, "认不出这个链接：" + s[:60]
    # 网址：先看看是不是 .torrent
    try:
        req = urllib.request.Request(s, headers={"User-Agent": UA})
        r = urllib.request.urlopen(req, timeout=20)
        ctype = (r.headers.get("Content-Type") or "").lower()
        if "bittorrent" in ctype or s.lower().split("?")[0].endswith(".torrent"):
            data = r.read(20 * 1024 * 1024)
            r.close()
            return add_torrent_bytes(data), None
        r.close()
    except Exception as e:
        return None, "打不开这个网址：" + str(e)[:120]
    return add_direct(s), None


# ------------------------------------------------------------------ 播放：边下边播
def piece_wait(h, ti, p, timeout=90):
    """等第 p 块下好；顺便把后面几块的优先级拉到最高"""
    plen = ti.piece_length()
    n = max(4, int(16 * 1024 * 1024 / plen))      # 往后预读约 16MB：没下的块都设上截止时间，越近越急
    k2 = 0
    for k in range(n):
        q = p + k
        if q < ti.num_pieces() and not h.have_piece(q):
            h.set_piece_deadline(q, 300 + k2 * 250)
            k2 += 1
    if h.have_piece(p):
        return True
    end = time.time() + timeout
    while time.time() < end:
        if h.have_piece(p):
            return True
        time.sleep(0.15)
    return False


def start_stream(h, idx):
    """开始播某个文件：这个文件最高优先级、按顺序下，先把开头和结尾几块要来（mp4/mkv 的索引常在文件末尾）"""
    hs = ih(h)
    STREAMING[hs] = time.time()
    ti = h.torrent_file()
    if ti is None:
        return
    fs = ti.files()
    prio = h.get_file_priorities()
    if prio[idx] < 7:
        prio[idx] = 7
        h.prioritize_files(prio)
    set_seq(h, True)
    if is_paused(h.status()):
        h.set_flags(lt.torrent_flags.auto_managed)
        h.resume()
    size = fs.file_size(idx)
    if size <= 0:
        return
    first = ti.map_file(idx, 0, 1).piece
    last = ti.map_file(idx, max(0, size - 1), 1).piece
    for k in range(3):
        if first + k <= last:
            h.set_piece_deadline(first + k, 200 + k * 100)
        if last - k >= first:
            h.set_piece_deadline(last - k, 400 + k * 100)


CT = {".mkv": "video/webm", ".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm", ".mov": "video/mp4", ".ts": "video/mp2t",
      ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac", ".flac": "audio/flac", ".wav": "audio/wav", ".ogg": "audio/ogg", ".opus": "audio/ogg"}


def ctype(name):
    ext = os.path.splitext(name)[1].lower()
    return CT.get(ext) or mimetypes.guess_type(name)[0] or "application/octet-stream"


def parse_range(hdr, size):
    m = re.match(r"bytes=(\d*)-(\d*)", hdr or "")
    if not m or size <= 0:
        return None
    a, b = m.group(1), m.group(2)
    if a == "":
        n = int(b or 0)
        return max(0, size - n), size - 1
    a = int(a)
    b = int(b) if b else size - 1
    if a >= size:
        return "bad"
    return a, min(b, size - 1)


def srt_to_vtt(raw):
    for enc in ("utf-8-sig", "gb18030", "big5", "utf-16"):
        try:
            txt = raw.decode(enc)
            break
        except Exception:
            continue
    else:
        txt = raw.decode("utf-8", "ignore")
    txt = txt.replace("\r\n", "\n")
    if txt.lstrip().startswith("WEBVTT"):
        return txt
    if "[Script Info]" in txt[:400] or "Dialogue:" in txt:   # .ass：只取对白
        out = ["WEBVTT", ""]
        for line in txt.split("\n"):
            if line.startswith("Dialogue:"):
                parts = line.split(",", 9)
                if len(parts) == 10:
                    def ts(x):
                        hh, mm, ss = x.strip().split(":")
                        return "%02d:%02d:%06.3f" % (int(hh), int(mm), float(ss))
                    body = re.sub(r"\{[^}]*\}", "", parts[9]).replace("\\N", "\n").replace("\\n", "\n")
                    try:
                        out += [ts(parts[1]) + " --> " + ts(parts[2]), body, ""]
                    except Exception:
                        pass
        return "\n".join(out)
    txt = re.sub(r"(\d\d:\d\d:\d\d),(\d\d\d)", r"\1.\2", txt)
    return "WEBVTT\n\n" + txt


def find_players():
    """电脑上装了哪些本地播放器"""
    c = []
    if os.name == "nt":
        pf = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), os.path.join(HOME, "AppData", "Local")]
        cand = [("VLC", r"VideoLAN\VLC\vlc.exe"), ("PotPlayer", r"DAUM\PotPlayer\PotPlayerMini64.exe"), ("PotPlayer", r"DAUM\PotPlayer\PotPlayerMini.exe"),
                ("mpv", r"mpv\mpv.exe"), ("MPC-HC", r"MPC-HC\mpc-hc64.exe")]
        for name, rel in cand:
            for base in pf:
                p = os.path.join(base, rel)
                if os.path.exists(p) and name not in [x[0] for x in c]:
                    c.append((name, p))
    else:
        for name, exe in (("VLC", "vlc"), ("mpv", "mpv"), ("IINA", "iina")):
            p = shutil.which(exe)
            if p:
                c.append((name, p))
        if sys.platform == "darwin" and os.path.exists("/Applications/VLC.app"):
            c.append(("VLC", "/Applications/VLC.app/Contents/MacOS/VLC"))
    return c


# ------------------------------------------------------------------ 网页
class H(BaseHTTPRequestHandler):
    server_version = "TorrentHub/" + VERSION
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def send(self, code, body, ctype_="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype_)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    # ---------------- GET
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        p = u.path
        try:
            if p == "/":
                return self.send(200, PAGE.replace("__VER__", VERSION), "text/html; charset=utf-8")
            if p == "/api/list":
                with LOCK:
                    items = [torrent_json(h) for h in handles()] + [direct_json(t) for t in DIRECT.values()]
                items.sort(key=lambda x: -x["added"])
                st = SES.status()
                return self.send(200, {"items": items, "down": st.payload_download_rate, "up": st.payload_upload_rate, "dht": st.dht_nodes,
                                       "conf": CONF, "players": [x[0] for x in find_players()], "lan": LAN_URLS})
            if p == "/api/files":
                tid = q.get("id", [""])[0]
                if tid in DIRECT:
                    return self.send(200, direct_json(DIRECT[tid]))
                h = find(tid)
                return self.send(200, torrent_json(h, True) if h else {"err": "没有这个任务"})
            if p.startswith("/play/"):
                return self.send(200, PLAYER, "text/html; charset=utf-8")
            if p.startswith("/stream/"):
                return self.stream(p)
            if p.startswith("/sub/"):
                return self.sub(p)
            if p == "/api/prog":     # 播放页显示：这个文件下了多少，当前位置之后连续可播多少
                return self.prog(q)
            return self.send(404, {"err": "not found"})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def locate(self, p):
        """/stream/<id>/<idx>/<名字> → (handle 或 None, 直链任务或 None, idx, 文件路径, 大小, 名字)"""
        parts = p.split("/")
        tid, idx = parts[2], int(parts[3])
        if tid in DIRECT:
            t = DIRECT[tid]
            return None, t, 0, t["path"], t["size"] or t["done"], t["name"]
        h = find(tid)
        if not h or not h.status().has_metadata:
            return None, None, idx, None, 0, ""
        ti = h.torrent_file()
        fs = ti.files()
        return h, None, idx, os.path.join(h.status().save_path, fs.file_path(idx)), fs.file_size(idx), os.path.basename(fs.file_path(idx))

    def stream(self, p):
        h, t, idx, path, size, name = self.locate(p)
        if not path:
            return self.send(404, {"err": "还没拿到种子信息"})
        if h:
            start_stream(h, idx)
        rg = parse_range(self.headers.get("Range"), size)
        if rg == "bad":
            return self.send(416, b"", "text/plain", {"Content-Range": "bytes */%d" % size})
        a, b = rg if rg else (0, size - 1)
        self.send_response(206 if rg else 200)
        self.send_header("Content-Type", ctype(name))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(b - a + 1))
        if rg:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command == "HEAD":
            return
        pos = a
        ti = h.torrent_file() if h else None
        plen = ti.piece_length() if ti else 0
        f = None
        try:
            while pos <= b:
                if h:
                    STREAMING[ih(h)] = time.time()
                    pr = ti.map_file(idx, pos, 1)
                    if not piece_wait(h, ti, pr.piece):
                        break
                    n = min(plen - pr.start, b - pos + 1, 512 * 1024)
                else:   # 直链：等文件写到这个位置
                    end = time.time() + 90
                    while t["done"] <= pos and time.time() < end and t["state"] in ("连接中", "下载中"):
                        time.sleep(0.2)
                    if t["done"] <= pos:
                        break
                    n = min(t["done"] - pos, b - pos + 1, 512 * 1024)
                if f is None:
                    for _ in range(50):
                        if os.path.exists(path):
                            break
                        time.sleep(0.1)
                    f = open(path, "rb")
                f.seek(pos)
                chunk = f.read(n)
                if not chunk:
                    time.sleep(0.2)
                    continue
                self.wfile.write(chunk)
                pos += len(chunk)
        finally:
            if f:
                f.close()

    def sub(self, p):
        h, t, idx, path, size, name = self.locate(p)
        if not path:
            return self.send(404, "")
        if h:
            prio = h.get_file_priorities()
            if prio[idx] < 7:
                prio[idx] = 7
                h.prioritize_files(prio)
            ti = h.torrent_file()
            first = ti.map_file(idx, 0, 1).piece
            last = ti.map_file(idx, max(0, size - 1), 1).piece
            for k in range(first, last + 1):
                if not piece_wait(h, ti, k, 30):
                    return self.send(503, "")
        try:
            with open(path, "rb") as f:
                raw = f.read(size)
        except OSError:
            return self.send(404, "")
        return self.send(200, srt_to_vtt(raw), "text/vtt; charset=utf-8")

    def prog(self, q):
        tid = q.get("id", [""])[0]
        idx = int(q.get("i", ["0"])[0])
        at = float(q.get("at", ["0"])[0])   # 当前播放位置占全片的比例
        if tid in DIRECT:
            t = DIRECT[tid]
            return self.send(200, {"pct": round(t["done"] * 100.0 / t["size"], 1) if t["size"] else 0, "ahead": max(0, t["done"]), "rate": t.get("rate", 0), "peers": 0})
        h = find(tid)
        if not h or not h.status().has_metadata:
            return self.send(200, {"pct": 0, "ahead": 0, "rate": 0, "peers": 0})
        ti = h.torrent_file()
        fs = ti.files()
        size = fs.file_size(idx)
        pos = int(size * max(0.0, min(1.0, at)))
        p0 = ti.map_file(idx, min(pos, max(0, size - 1)), 1).piece
        plast = ti.map_file(idx, max(0, size - 1), 1).piece
        k = p0
        while k <= plast and h.have_piece(k):
            k += 1
        ahead = (k - p0) * ti.piece_length()
        st = h.status()
        prog = h.file_progress()[idx]
        return self.send(200, {"pct": round(prog * 100.0 / size, 1) if size else 0, "ahead": ahead, "rate": st.download_rate, "peers": st.num_peers})

    # ---------------- POST
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        p = u.path
        try:
            if p == "/api/add":
                d = json.loads(self.body() or b"{}")
                ok, errs = [], []
                for line in re.split(r"[\r\n]+", d.get("links", "")):
                    line = line.strip()
                    if not line:
                        continue
                    tid, err = add_link(line)
                    (ok if tid else errs).append(tid or err)
                for fb in d.get("files", []):        # .torrent 文件，base64
                    try:
                        ok.append(add_torrent_bytes(base64.b64decode(fb)))
                    except Exception as e:
                        errs.append("种子文件读不了：" + str(e)[:80])
                return self.send(200, {"ok": ok, "errs": errs})
            if p == "/api/act":
                d = json.loads(self.body() or b"{}")
                return self.send(200, act(d))
            if p == "/api/conf":
                d = json.loads(self.body() or b"{}")
                if "dir" in d and d["dir"].strip():
                    CONF["dir"] = os.path.expanduser(d["dir"].strip())
                    os.makedirs(CONF["dir"], exist_ok=True)
                for k in ("pause_done",):
                    if k in d:
                        CONF[k] = bool(d[k])
                for k in ("max_down", "max_up"):
                    if k in d:
                        CONF[k] = max(0, int(d[k] or 0))
                SES.apply_settings({"download_rate_limit": CONF["max_down"] * 1024, "upload_rate_limit": CONF["max_up"] * 1024})
                save_conf()
                return self.send(200, {"ok": 1, "conf": CONF})
            return self.send(404, {"err": "not found"})
        except Exception as e:
            return self.send(500, {"err": str(e)[:300]})


def open_path(path):
    if os.name == "nt":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def act(d):
    tid, a = d.get("id", ""), d.get("a", "")
    if tid in DIRECT:
        t = DIRECT[tid]
        if a == "pause":
            t["stop"] = True
        elif a == "resume" and t["state"] != "下载中":
            t["stop"] = False
            t["state"] = "连接中"
            threading.Thread(target=direct_worker, args=(t,), daemon=True).start()
        elif a in ("remove", "delete"):
            t["stop"] = True
            DIRECT.pop(tid, None)
            if a == "delete":
                time.sleep(0.5)
                try:
                    os.remove(t["path"])
                except Exception:
                    pass
        elif a == "folder":
            open_path(os.path.dirname(t["path"]))
        elif a == "player":
            return launch_player("http://127.0.0.1:%d/stream/%s/0/%s" % (PORT, tid, urllib.parse.quote(t["name"])), t["path"] if t["state"] == "已完成" else None)
        return {"ok": 1}
    h = find(tid)
    if not h:
        return {"err": "没有这个任务"}
    if a == "pause":
        h.unset_flags(lt.torrent_flags.auto_managed)
        h.pause()
    elif a == "resume":
        h.set_flags(lt.torrent_flags.auto_managed)
        h.resume()
    elif a in ("remove", "delete"):
        hs = ih(h)
        flag = 0
        if a == "delete":
            flag = getattr(getattr(lt, "options_t", None), "delete_files", None) or getattr(lt.session, "delete_files", 1)
        SES.remove_torrent(h, flag)
        with LOCK:
            MAGNETS.pop(hs, None)
            ADDED.pop(hs, None)
            STREAMING.pop(hs, None)
        save_magnets()
        try:
            os.remove(resume_path(hs))
        except Exception:
            pass
    elif a == "skip":       # 某个文件下 / 不下
        i = int(d.get("i", 0))
        prio = h.get_file_priorities()
        prio[i] = 0 if prio[i] else 4
        h.prioritize_files(prio)
    elif a == "folder":
        st = h.status()
        path = st.save_path
        if st.has_metadata:
            fs = h.torrent_file().files()
            top = fs.file_path(0).split(os.sep)[0].split("/")[0]
            cand = os.path.join(path, top)
            if fs.num_files() > 1 and os.path.isdir(cand):
                path = cand
        open_path(path)
    elif a == "player":
        i = int(d.get("i", 0))
        fs = h.torrent_file().files()
        start_stream(h, i)
        full = os.path.join(h.status().save_path, fs.file_path(i))
        done = h.file_progress()[i] >= fs.file_size(i)
        return launch_player("http://127.0.0.1:%d/stream/%s/%d/%s" % (PORT, tid, i, urllib.parse.quote(os.path.basename(fs.file_path(i)))), full if done else None)
    elif a == "recheck":
        h.force_recheck()
    return {"ok": 1}


def launch_player(url, local_file=None):
    ps = find_players()
    if not ps:
        if local_file:
            open_path(local_file)
            return {"ok": 1, "msg": "已用系统默认播放器打开"}
        return {"err": "电脑上没找到 VLC / PotPlayer / mpv。装一个 VLC（免费）就能边下边播所有格式"}
    name, exe = ps[0]
    subprocess.Popen([exe, local_file or url])
    return {"ok": 1, "msg": "已用 %s 打开" % name}


# ------------------------------------------------------------------ 页面（主界面 + 播放页）
PAGE = r"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>🧲 种子下载器</title><style>
:root{--bg:#F3F4F6;--card:#fff;--ink:#17202A;--soft:#5D6B78;--faint:#98A3AE;--line:#E1E5EA;--ac:#2563EB;--acs:#E3ECFD;--ok:#16803C;--bad:#C2410C}
@media (prefers-color-scheme:dark){:root{--bg:#111418;--card:#1A1F25;--ink:#E7EBEF;--soft:#A0ABB6;--faint:#68737E;--line:#2A3139;--ac:#6EA0FF;--acs:#1B2A44;--ok:#5BD38A;--bad:#FF9466}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
main{max-width:860px;margin:0 auto;padding:18px 14px 80px}h1{font-size:22px;margin:0}
.top{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}.top .sp{margin-left:auto;font-size:13px;color:var(--soft)}
.add{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px;margin:14px 0}
textarea{width:100%;min-height:74px;border:1px solid var(--line);border-radius:10px;padding:10px;font:14px/1.5 ui-monospace,Consolas,monospace;background:var(--bg);color:var(--ink);resize:vertical}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:8px}
button,.btn{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;padding:7px 12px;font-size:14px;cursor:pointer;text-decoration:none;font-family:inherit}
button.pri{background:var(--ac);border-color:var(--ac);color:#fff;font-weight:600}
.hint{font-size:12.5px;color:var(--faint)}
.drop{border:2px dashed var(--ac);background:var(--acs)}
.task{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin-bottom:10px}
.task .nm{font-weight:600;word-break:break-all}.task .mt{font-size:12.5px;color:var(--soft);margin-top:3px}
.bar{height:6px;background:var(--line);border-radius:3px;overflow:hidden;margin-top:8px}.bar i{display:block;height:100%;background:var(--ac)}
.task.done .bar i{background:var(--ok)}.task .err{color:var(--bad);font-size:12.5px}
.files{margin-top:10px;border-top:1px dashed var(--line)}
.f{display:flex;gap:8px;align-items:center;padding:7px 0;border-bottom:1px solid var(--line);font-size:13.5px}
.f .fn{flex:1;min-width:0;word-break:break-all}.f .fn small{display:block;color:var(--faint)}.f.skip .fn{opacity:.45;text-decoration:line-through}
.play1{background:var(--ac);color:#fff;border-color:var(--ac);font-weight:700}
.f .play{background:var(--ac);color:#fff;border-color:var(--ac);font-weight:600;padding:5px 12px;white-space:nowrap}
.f .sm{padding:4px 8px;font-size:12.5px;white-space:nowrap}
details.set{margin-top:14px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:10px 14px}
details.set summary{cursor:pointer;font-weight:600}details.set label{display:block;margin:8px 0;font-size:14px}
details.set input[type=text],details.set input[type=number]{border:1px solid var(--line);border-radius:8px;padding:6px 8px;background:var(--bg);color:var(--ink);font-size:14px}
.empty{text-align:center;color:var(--faint);padding:30px 0}
.toast{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);background:#222;color:#fff;padding:8px 16px;border-radius:999px;font-size:14px;opacity:0;transition:opacity .2s;pointer-events:none;max-width:90vw}
.toast.on{opacity:1}
</style></head><body><main>
<div class="top"><h1>🧲 种子下载器</h1><span class="hint">边下边播 · v__VER__</span><span class="sp" id="sp"></span></div>
<div class="add" id="add">
<textarea id="links" placeholder="粘贴链接，一行一个：磁力 magnet:?…、.torrent 网址、http/https/ftp 直链、thunder:// 迅雷链接都可以。&#10;也可以把 .torrent 文件拖到这里。"></textarea>
<div class="row"><button class="pri" id="go">＋ 开始下载</button><label class="btn">📄 选种子文件<input type="file" id="tf" accept=".torrent" multiple hidden></label><button id="paste">📋 粘贴</button><span class="hint" id="addmsg"></span></div>
</div>
<div id="list"><div class="empty">加载中…</div></div>
<details class="set"><summary>⚙️ 设置</summary>
<label>下载到：<br><input type="text" id="cdir" style="width:100%"></label>
<label>限速（KB/s，0 = 不限）：下载 <input type="number" id="cdn" style="width:90px"> 上传 <input type="number" id="cup" style="width:90px"></label>
<label><input type="checkbox" id="cpd"> 下完自动暂停（不再上传）</label>
<button id="csave">保存</button> <span class="hint" id="cinfo"></span>
<p class="hint" id="lan"></p>
</details>
</main><div class="toast" id="toast"></div>
<script>
var $=function(i){return document.getElementById(i)},OPEN={},FILES={},PLAYERS=[];
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function sz(n){if(!n)return '0';var u=['B','KB','MB','GB','TB'],i=0;while(n>=1024&&i<4){n/=1024;i++}return (i?n.toFixed(n<10?2:1):n)+' '+u[i]}
function eta(s){if(s<0)return '';if(s<60)return s+' 秒';if(s<3600)return Math.round(s/60)+' 分钟';return (s/3600).toFixed(1)+' 小时'}
function toast(m){var t=$('toast');t.textContent=m;t.className='toast on';clearTimeout(t._t);t._t=setTimeout(function(){t.className='toast'},2800)}
function api(p,d,cb){var x=new XMLHttpRequest();x.open(d?'POST':'GET',p);x.onload=function(){var r={};try{r=JSON.parse(x.responseText)}catch(e){}cb&&cb(r)};x.onerror=function(){cb&&cb({err:'连不上下载器（它关了？）'})};x.send(d?JSON.stringify(d):null)}
function add(files){
  var links=$('links').value;if(!links.trim()&&!(files&&files.length)){toast('先粘贴链接或选种子文件');return}
  $('addmsg').textContent='添加中…';
  api('/api/add',{links:links,files:files||[]},function(r){
    $('addmsg').textContent='';if(r.ok&&r.ok.length){$('links').value='';toast('已添加 '+r.ok.length+' 个');r.ok.forEach(function(id){OPEN[id]=1})}
    if(r.errs&&r.errs.length)toast(r.errs.join('；'));if(r.err)toast(r.err);load();
  });
}
function readFiles(fl){var out=[],n=fl.length;if(!n)return;Array.prototype.forEach.call(fl,function(f){var rd=new FileReader();rd.onload=function(){out.push(rd.result.split(',')[1]);if(out.length===n)add(out)};rd.readAsDataURL(f)})}
$('go').onclick=function(){add()};
$('tf').onchange=function(){readFiles(this.files);this.value=''};
$('paste').onclick=function(){if(navigator.clipboard&&navigator.clipboard.readText)navigator.clipboard.readText().then(function(t){$('links').value=($('links').value?$('links').value+'\n':'')+t}).catch(function(){toast('浏览器不让读剪贴板，长按输入框粘贴')});else toast('长按输入框粘贴')};
var A=$('add');A.ondragover=function(e){e.preventDefault();A.classList.add('drop')};A.ondragleave=function(){A.classList.remove('drop')};
A.ondrop=function(e){e.preventDefault();A.classList.remove('drop');if(e.dataTransfer.files.length)readFiles(e.dataTransfer.files);else{var t=e.dataTransfer.getData('text');if(t)$('links').value+=($('links').value?'\n':'')+t}};
function fileRows(t){
  var fs=FILES[t.id];if(!fs)return '<div class="hint" style="padding:8px 0">'+(t.meta?'读取文件列表…':'正在通过 DHT 找种子信息（磁力链接第一次要等几秒到几分钟）…')+'</div>';
  if(!fs.files)return '';
  var list=fs.files.slice().sort(function(a,b){return (b.media-a.media)||(b.size-a.size)});
  var subs=list.filter(function(f){return f.sub});
  return list.slice(0,300).map(function(f){
    var sub='';if(f.media&&!f.audio&&subs.length){sub='&s='+subs.map(function(s){return s.i}).join(',')}
    return '<div class="f'+(f.skip?' skip':'')+'"><div class="fn">'+esc(f.path)+'<small>'+sz(f.size)+' · '+f.pct+'%</small></div>'+
      (f.media?'<a class="btn play" target="_blank" href="/play/'+t.id+'/'+f.i+'?n='+encodeURIComponent(f.name)+sub+'">▶ 播放</a>'+(PLAYERS.length?'<button class="sm" data-a="player" data-id="'+t.id+'" data-i="'+f.i+'" title="用电脑上的 '+PLAYERS[0]+' 播，什么格式都能放">🎬 '+esc(PLAYERS[0])+'</button>':''):'')+
      (f.pct>=100?'<a class="btn sm" href="/stream/'+t.id+'/'+f.i+'/'+encodeURIComponent(f.name)+'" download="'+esc(f.name)+'">⬇</a>':'')+
      (t.kind==='bt'?'<button class="sm" data-a="skip" data-id="'+t.id+'" data-i="'+f.i+'">'+(f.skip?'下载':'不下')+'</button>':'')+'</div>';
  }).join('')+(list.length>300?'<div class="hint">还有 '+(list.length-300)+' 个文件没列出</div>':'');
}
function render(d){
  PLAYERS=d.players||[];
  $('sp').textContent='↓ '+sz(d.down)+'/s · ↑ '+sz(d.up)+'/s · DHT '+d.dht;
  if(!$('cdir').value){$('cdir').value=d.conf.dir;$('cdn').value=d.conf.max_down;$('cup').value=d.conf.max_up;$('cpd').checked=d.conf.pause_done;
    $('lan').innerHTML=d.lan&&d.lan.length?'📱 手机可以打开：'+d.lan.map(esc).join(' 或 '):'只在本机能打开。想让手机也能用，用 <code>python torrent_hub.py --lan</code> 启动。';}
  if(!d.items.length){$('list').innerHTML='<div class="empty">还没有任务。粘贴一个磁力链接试试。</div>';return}
  $('list').innerHTML=d.items.map(function(t){
    var done=t.progress>=100,info=[t.state];
    if(t.size)info.push(sz(t.done)+' / '+sz(t.size));
    if(!done&&t.down)info.push('↓ '+sz(t.down)+'/s');if(t.up)info.push('↑ '+sz(t.up)+'/s');
    if(t.kind==='bt')info.push(t.peers+' 人（'+t.seeds+' 个完整源）');if(t.eta>0)info.push('还要 '+eta(t.eta));if(t.streaming)info.push('▶ 正在边下边播');
    return '<div class="task'+(done?' done':'')+'"><div class="nm">'+(t.kind==='bt'?'🧲 ':'🔗 ')+esc(t.name)+'</div><div class="mt">'+info.map(esc).join(' · ')+'</div>'+
      (t.err?'<div class="err">'+esc(t.err)+'</div>':'')+'<div class="bar"><i style="width:'+t.progress+'%"></i></div>'+
      '<div class="row">'+(t.play?'<a class="btn play1" target="_blank" href="/play/'+t.id+'/'+t.play.i+'?n='+encodeURIComponent(t.play.name)+(t.play.s?'&s='+t.play.s:'')+'">▶ 直接播</a>':(t.kind==='bt'&&!t.meta?'<span class="hint">找到种子信息后就能播…</span>':''))+
      '<button data-a="files" data-id="'+t.id+'">'+(OPEN[t.id]?'▾ 收起':'▸ 文件')+'</button>'+
      (t.kind==='http'&&!t.running&&!t.paused?'':(t.paused?'<button data-a="resume" data-id="'+t.id+'">⏯ 继续</button>':'<button data-a="pause" data-id="'+t.id+'">⏸ 暂停</button>'))+
      '<button data-a="folder" data-id="'+t.id+'">📂 文件夹</button><button data-a="remove" data-id="'+t.id+'">✕ 移除</button><button data-a="delete" data-id="'+t.id+'">🗑 连文件删</button></div>'+
      (OPEN[t.id]?'<div class="files">'+fileRows(t)+'</div>':'')+'</div>';
  }).join('');
}
var LAST=null;
function load(){api('/api/list',null,function(d){if(!d.items){$('list').innerHTML='<div class="empty">'+esc(d.err||'出错了')+'</div>';return}LAST=d;
  var need=d.items.filter(function(t){return OPEN[t.id]}),n=need.length;if(!n){render(d);return}
  need.forEach(function(t){api('/api/files?id='+t.id,null,function(f){if(f&&f.files)FILES[t.id]=f;if(--n===0)render(d)})});})}
$('list').onclick=function(e){
  var b=e.target.closest('[data-a]');if(!b)return;var a=b.getAttribute('data-a'),id=b.getAttribute('data-id');
  if(a==='files'){OPEN[id]=!OPEN[id];load();return}
  if(a==='delete'&&!confirm('连同已下载的文件一起删掉？'))return;
  api('/api/act',{id:id,a:a,i:+(b.getAttribute('data-i')||0)},function(r){if(r.err)toast(r.err);else if(r.msg)toast(r.msg);load()});
};
$('csave').onclick=function(){api('/api/conf',{dir:$('cdir').value,max_down:+$('cdn').value,max_up:+$('cup').value,pause_done:$('cpd').checked},function(r){$('cinfo').textContent=r.ok?'已保存（新任务下到这里）':(r.err||'')})};
load();setInterval(function(){if(!document.hidden)load()},2000);
</script></body></html>"""

PLAYER = r"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>▶ 播放</title><style>
body{margin:0;background:#000;color:#ddd;font:14px/1.5 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1200px;margin:0 auto}video,audio{width:100%;max-height:82vh;background:#000;display:block}
.info{padding:10px 14px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.nm{font-weight:600;color:#fff;word-break:break-all;flex-basis:100%}
.st{color:#9aa}
button,a.btn{border:1px solid #444;background:#1c1c1c;color:#eee;border-radius:10px;padding:7px 12px;font-size:14px;cursor:pointer;text-decoration:none}
.warn{background:#3b2410;color:#ffcf9e;border-radius:10px;padding:10px 14px;margin:10px 14px;display:none;line-height:1.7}
.buf{height:4px;background:#222}.buf i{display:block;height:100%;background:#3b82f6;width:0}
</style></head><body><div class="wrap">
<div id="box"></div><div class="buf"><i id="bi"></i></div>
<div class="warn" id="warn"></div>
<div class="info"><div class="nm" id="nm"></div><span class="st" id="st">连接中…</span>
<button id="vlc">🎬 用电脑上的播放器播</button><button id="cp">📋 复制串流地址</button><a class="btn" href="/">← 回下载列表</a></div>
<div class="info" style="color:#778;font-size:12.5px">边下边播：拖进度条，下载器会优先下那一段，等几秒就能接着看。浏览器放不了的格式（常见是 H.265/HEVC 视频、AC3/DTS 音轨），点「用电脑上的播放器播」，或把串流地址复制到手机 / 电脑的 VLC 里打开。</div>
</div><script>
var parts=location.pathname.split('/'),ID=parts[2],I=+parts[3],qs=new URLSearchParams(location.search),NAME=qs.get('n')||'',SUBS=(qs.get('s')||'').split(',').filter(Boolean);
var SRC='/stream/'+ID+'/'+I+'/'+encodeURIComponent(NAME),FULL=location.origin+SRC;
document.title='▶ '+NAME;document.getElementById('nm').textContent=NAME;
var audio=/\.(mp3|m4a|aac|flac|wav|ogg|opus|ape|wma)$/i.test(NAME),m=document.createElement(audio?'audio':'video');
m.controls=true;m.autoplay=true;m.preload='auto';m.setAttribute('playsinline','');m.src=SRC;
SUBS.forEach(function(s,k){var t=document.createElement('track');t.kind='subtitles';t.label='字幕 '+(k+1);t.srclang='zh';t.src='/sub/'+ID+'/'+s+'/x.vtt';if(k===0)t.default=true;m.appendChild(t)});
document.getElementById('box').appendChild(m);
function warn(t){var w=document.getElementById('warn');w.innerHTML=t;w.style.display='block'}
m.addEventListener('error',function(){warn('这个文件浏览器放不了（多半是视频或音轨格式不支持）。点下面「🎬 用电脑上的播放器播」，或者把串流地址复制到 VLC 里打开。')});
var stall=0;m.addEventListener('waiting',function(){stall=Date.now()});
setInterval(function(){
  var at=m.duration?m.currentTime/m.duration:0;
  fetch('/api/prog?id='+ID+'&i='+I+'&at='+at).then(function(r){return r.json()}).then(function(p){
    document.getElementById('bi').style.width=p.pct+'%';
    var s='已下 '+p.pct+'%';if(p.rate)s+=' · '+(p.rate/1048576).toFixed(2)+' MB/s';if(p.peers)s+=' · '+p.peers+' 人';
    if(m.paused&&m.readyState<3)s+=' · 缓冲中…';else if(p.ahead)s+=' · 后面已缓冲 '+(p.ahead/1048576).toFixed(0)+' MB';
    document.getElementById('st').textContent=s;
    if(stall&&m.readyState<3&&Date.now()-stall>25000&&!p.rate)warn('等了好一会儿还没数据：这个资源现在可能没人在线分享，换个时间或换个资源试试。');
  }).catch(function(){});
},1500);
document.getElementById('cp').onclick=function(){var ok=function(){alert('已复制：\n'+FULL+'\n\n在 VLC 里选「打开网络串流」粘贴就能播。手机要能连到这台电脑（启动时加 --lan）。')};
  if(navigator.clipboard)navigator.clipboard.writeText(FULL).then(ok,function(){prompt('复制这个地址：',FULL)});else prompt('复制这个地址：',FULL)};
document.getElementById('vlc').onclick=function(){m.pause();fetch('/api/act',{method:'POST',body:JSON.stringify({id:ID,a:'player',i:I})}).then(function(r){return r.json()}).then(function(r){alert(r.err||r.msg||'已打开')})};
</script></body></html>"""


def lan_urls(port):
    out = []
    try:
        names = set()
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            names.add(info[4][0])
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            names.add(s.getsockname()[0])
        finally:
            s.close()
        for ip in sorted(names):
            if not ip.startswith("127."):
                out.append("http://%s:%d" % (ip, port))
    except Exception:
        pass
    return out


PORT = 8800
LAN_URLS = []


def main():
    global PORT, LAN_URLS
    ap = argparse.ArgumentParser(description="种子下载器 · 边下边播")
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--lan", action="store_true", help="允许同一网络里的手机访问")
    ap.add_argument("--dir", help="下载到哪个文件夹")
    ap.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    a = ap.parse_args()
    PORT = a.port
    if a.dir:
        CONF["dir"] = os.path.abspath(os.path.expanduser(a.dir))
        save_conf()
    os.makedirs(CONF["dir"], exist_ok=True)
    restore()
    threading.Thread(target=alert_loop, daemon=True).start()
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    srv = ThreadingHTTPServer((host, PORT), H)
    srv.daemon_threads = True
    LAN_URLS = lan_urls(PORT) if a.lan else []
    url = "http://127.0.0.1:%d" % PORT
    print("🧲 种子下载器 v%s（libtorrent %s）" % (VERSION, lt.__version__))
    print("   打开：", url)
    for u in LAN_URLS:
        print("   手机：", u)
    print("   下载到：", CONF["dir"])
    print("   按 Ctrl+C 退出（会先保存进度）")
    if not a.no_browser:
        try:
            import webbrowser
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    print("保存进度…")
    save_all_resume()
    time.sleep(1.5)
    for a_ in SES.pop_alerts():
        if isinstance(a_, lt.save_resume_data_alert):
            try:
                with open(resume_path(ih(a_.handle)), "wb") as f:
                    f.write(lt.write_resume_data_buf(a_.params))
            except Exception:
                pass
    print("再见")


if __name__ == "__main__":
    main()

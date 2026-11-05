package io.github.boliunew.tools;

import android.app.Activity;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.MimeTypeMap;
import android.widget.Toast;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.HashMap;
import java.util.Map;

/**
 * 网页里做好的文件（剪好的视频、转好的音频、修好的照片……）只在网页内存里，
 * 系统下载器拿不到。网页把文件分块交给这里，存到手机：
 * 视频 → 相册「Movies/工具箱」，音频 → 「Music/工具箱」，图片 → 「Pictures/工具箱」，其他 → 「下载」。
 * 网页端用法见 savesheet.js（window.ToolsNative）。只给自己的网站用。
 */
public class SaveBridge {
    private final Activity act;
    private final Map<String, Part> parts = new HashMap<>();
    volatile boolean trusted = false;   // MainActivity 按当前页面地址更新：只有 boliunew.github.io 能用

    private static class Part { File file; FileOutputStream out; String name; String mime; }

    SaveBridge(Activity act) { this.act = act; }

    @JavascriptInterface
    public String saveStart(String name, String mime) {
        if (!trusted) return "";
        try {
            String clean = cleanName(name);
            if (mime == null || mime.isEmpty()) {
                String ext = MimeTypeMap.getFileExtensionFromUrl(clean.replace(' ', '_'));
                String m = ext == null ? null : MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext.toLowerCase());
                mime = m == null ? "application/octet-stream" : m;
            }
            File dir = new File(act.getCacheDir(), "saving");
            dir.mkdirs();
            Part p = new Part();
            p.file = File.createTempFile("part_", ".bin", dir);
            p.out = new FileOutputStream(p.file);
            p.name = clean;
            p.mime = mime;
            String id = Long.toString(System.nanoTime(), 36);
            synchronized (parts) { parts.put(id, p); }
            return id;
        } catch (Exception e) {
            return "";
        }
    }

    @JavascriptInterface
    public boolean saveChunk(String id, String b64) {
        Part p;
        synchronized (parts) { p = parts.get(id); }
        if (p == null) return false;
        try {
            p.out.write(Base64.decode(b64, Base64.DEFAULT));
            return true;
        } catch (Exception e) {
            drop(id);
            return false;
        }
    }

    /** 返回给网页看的结果：以「✅」开头表示存好了，否则是出错原因。 */
    @JavascriptInterface
    public String saveEnd(String id) {
        Part p;
        synchronized (parts) { p = parts.remove(id); }
        if (p == null) return "保存失败：数据没传完整";
        try {
            p.out.close();
            String where = store(p);
            toast("✅ 已保存：" + where);
            return "✅ " + where;
        } catch (Exception e) {
            return "保存失败：" + e.getMessage();
        } finally {
            p.file.delete();
        }
    }

    @JavascriptInterface
    public void saveCancel(String id) { drop(id); }

    private void drop(String id) {
        Part p;
        synchronized (parts) { p = parts.remove(id); }
        if (p == null) return;
        try { p.out.close(); } catch (Exception ignored) { }
        p.file.delete();
    }

    private String store(Part p) throws Exception {
        String top, label;
        Uri col;
        if (p.mime.startsWith("video/")) { top = Environment.DIRECTORY_MOVIES; label = "相册 · Movies/工具箱"; }
        else if (p.mime.startsWith("audio/")) { top = Environment.DIRECTORY_MUSIC; label = "Music/工具箱"; }
        else if (p.mime.startsWith("image/")) { top = Environment.DIRECTORY_PICTURES; label = "相册 · Pictures/工具箱"; }
        else { top = Environment.DIRECTORY_DOWNLOADS; label = "下载/工具箱"; }

        if (Build.VERSION.SDK_INT >= 29) {
            if (p.mime.startsWith("video/")) col = MediaStore.Video.Media.EXTERNAL_CONTENT_URI;
            else if (p.mime.startsWith("audio/")) col = MediaStore.Audio.Media.EXTERNAL_CONTENT_URI;
            else if (p.mime.startsWith("image/")) col = MediaStore.Images.Media.EXTERNAL_CONTENT_URI;
            else col = MediaStore.Downloads.EXTERNAL_CONTENT_URI;
            ContentResolver cr = act.getContentResolver();
            ContentValues v = new ContentValues();
            v.put(MediaStore.MediaColumns.DISPLAY_NAME, p.name);
            v.put(MediaStore.MediaColumns.MIME_TYPE, p.mime);
            v.put(MediaStore.MediaColumns.RELATIVE_PATH, top + "/工具箱");
            v.put(MediaStore.MediaColumns.IS_PENDING, 1);
            Uri u = cr.insert(col, v);
            if (u == null) throw new Exception("系统不让存");
            try (InputStream in = new FileInputStream(p.file); OutputStream out = cr.openOutputStream(u)) {
                copy(in, out);
            } catch (Exception e) {
                cr.delete(u, null, null);
                throw e;
            }
            v.clear();
            v.put(MediaStore.MediaColumns.IS_PENDING, 0);
            cr.update(u, v, null, null);
            return label + "/" + p.name;
        }
        // 安卓 9 及以下：存到 App 自己的文件夹（不用存储权限）
        File dir = new File(act.getExternalFilesDir(top), "工具箱");
        dir.mkdirs();
        File dst = new File(dir, p.name);
        try (InputStream in = new FileInputStream(p.file); OutputStream out = new FileOutputStream(dst)) {
            copy(in, out);
        }
        return dst.getAbsolutePath();
    }

    private static void copy(InputStream in, OutputStream out) throws Exception {
        byte[] buf = new byte[1 << 16];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
    }

    private static String cleanName(String n) {
        String s = n == null ? "" : n.replaceAll("[\\\\/:*?\"<>|\\x00-\\x1f]", "_").trim();
        if (s.isEmpty() || s.startsWith(".")) s = "file_" + System.currentTimeMillis() + s;
        return s.length() > 120 ? s.substring(s.length() - 120) : s;
    }

    private void toast(String m) { act.runOnUiThread(() -> Toast.makeText(act, m, Toast.LENGTH_LONG).show()); }

    /** 注入到每个页面：点了 blob: / data: 的下载链接，就交给 App 保存（不然 WebView 会什么都不做）。 */
    static final String HOOK_JS = "(function(){if(window.__toolsSave||!window.ToolsNative)return;" +
        "window.__toolsSave=function(blob,name,onp){return new Promise(function(ok,bad){" +
        "var id=ToolsNative.saveStart(name||'file',blob.type||'');if(!id)return bad(new Error('App 不能保存这个文件'));" +
        "var CH=786432,i=0;function next(){if(i>=blob.size){var r=ToolsNative.saveEnd(id);return r.indexOf('✅')===0?ok(r.slice(2)):bad(new Error(r));}" +
        "var fr=new FileReader();fr.onload=function(){var s=String(fr.result),k=s.indexOf(',');if(!ToolsNative.saveChunk(id,s.slice(k+1))){return bad(new Error('保存失败'));}" +
        "i+=CH;if(onp)onp(Math.min(1,i/blob.size));setTimeout(next,0);};fr.onerror=function(){ToolsNative.saveCancel(id);bad(new Error('读取失败'));};" +
        "fr.readAsDataURL(blob.slice(i,i+CH));}next();});};" +
        "window.__toolsSaveUrl=function(h,name){return fetch(h).then(function(r){return r.blob();}).then(function(b){return window.__toolsSave(b,name);});};" +
        "document.addEventListener('click',function(e){var a=e.target&&e.target.closest&&e.target.closest('a[download]');if(!a)return;" +
        "var h=a.getAttribute('href')||'';if(h.indexOf('blob:')!==0&&h.indexOf('data:')!==0)return;e.preventDefault();e.stopPropagation();" +
        "window.__toolsSaveUrl(a.href,a.getAttribute('download')||'').catch(function(x){alert(x.message);});},true);})();";
}

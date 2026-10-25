package io.github.boliunew.tools;

import android.Manifest;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.PermissionRequest;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import com.google.firebase.messaging.FirebaseMessaging;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * 工具箱 App：全屏打开 https://boliunew.github.io/tools/ ，补上浏览器才有的能力——
 * 拍照 / 选图（拍照识别柜号、验柜拍照）、麦克风（开口说跟读）、定位（天气、附近）、下载、返回键、外部链接用浏览器打开。
 * 网站更新不用重装 App。
 */
public class MainActivity extends Activity {
    private static final String HOME = "https://boliunew.github.io/tools/";
    private static final int REQ_FILE = 1, REQ_MIC = 2, REQ_GEO = 3, REQ_NOTIFY = 4;

    private WebView web;
    private ValueCallback<Uri[]> fileCallback;
    private Uri cameraUri;
    private PermissionRequest pendingMic;
    private GeolocationPermissions.Callback pendingGeo;
    private String pendingGeoOrigin;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        web = new WebView(this);
        setContentView(web);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);   // 网络电台有 http:// 的流
        s.setGeolocationEnabled(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setBuiltInZoomControls(false);
        s.setUserAgentString(s.getUserAgentString() + " ToolsApp/" + BuildConfigVersion());
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
                Uri u = req.getUrl();
                String scheme = u.getScheme() == null ? "" : u.getScheme();
                String host = u.getHost() == null ? "" : u.getHost();
                boolean inApp = (scheme.equals("https") || scheme.equals("http"))
                        && (host.equals("boliunew.github.io") || host.endsWith(".workers.dev") || host.endsWith(".ts.net"));
                if (inApp || !req.isForMainFrame()) return false;
                openExternal(u);   // 其他网站、电话、地图、Telegram……交给系统
                return true;
            }

            @Override
            public void onPageStarted(WebView v, String url, Bitmap favicon) {
                super.onPageStarted(v, url, favicon);
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                super.onPageFinished(v, url);
                registerPush();
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = cb;
                boolean image = false;
                for (String t : p.getAcceptTypes()) if (t != null && t.startsWith("image")) image = true;
                List<Intent> extras = new ArrayList<>();
                Intent camera = null;
                if (image) {
                    try {
                        File dir = new File(getCacheDir(), "photos");
                        dir.mkdirs();
                        File f = File.createTempFile("snap_", ".jpg", dir);
                        cameraUri = FileProvider.getUriForFile(MainActivity.this, "io.github.boliunew.tools.files", f);
                        camera = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
                        camera.putExtra(MediaStore.EXTRA_OUTPUT, cameraUri);
                        camera.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        extras.add(camera);
                    } catch (Exception e) {
                        cameraUri = null;
                    }
                }
                Intent launch;
                if (camera != null && p.isCaptureEnabled()) {
                    launch = camera;                       // capture="environment"：直接开相机
                } else {
                    Intent pick = p.createIntent();
                    if (p.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE) pick.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                    launch = Intent.createChooser(pick, image ? "拍照或选图" : "选择文件");
                    if (!extras.isEmpty()) launch.putExtra(Intent.EXTRA_INITIAL_INTENTS, extras.toArray(new Intent[0]));
                }
                try {
                    startActivityForResult(launch, REQ_FILE);
                } catch (ActivityNotFoundException e) {
                    fileCallback = null;
                    toast("找不到相机或文件选择器");
                    return false;
                }
                return true;
            }

            @Override
            public void onPermissionRequest(PermissionRequest req) {
                runOnUiThread(() -> {
                    boolean mic = false;
                    for (String r : req.getResources()) if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(r)) mic = true;
                    if (!mic) { req.deny(); return; }
                    if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                        req.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                    } else {
                        pendingMic = req;
                        requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);
                    }
                });
            }

            @Override
            public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback cb) {
                if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                        || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
                    cb.invoke(origin, true, false);
                } else {
                    pendingGeo = cb;
                    pendingGeoOrigin = origin;
                    requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_GEO);
                }
            }
        });

        web.setDownloadListener((url, ua, disposition, mime, length) -> {
            if (url.startsWith("http")) {
                try {
                    DownloadManager.Request r = new DownloadManager.Request(Uri.parse(url));
                    String name = URLUtil.guessFileName(url, disposition, mime);
                    r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                    r.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
                    ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(r);
                    toast("开始下载：" + name);
                } catch (Exception e) {
                    openExternal(Uri.parse(url));
                }
            } else {
                toast("这个文件请在浏览器里下载");
            }
        });

        PushService.channel(this);
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIFY);
        }
        if (saved != null) web.restoreState(saved);
        else web.loadUrl(startUrl(getIntent()));
    }

    private boolean pushChecked = false;

    /** 首页解锁后（浏览器里存了密钥），把这台手机登记成推送接收设备。 */
    private void registerPush() {
        if (pushChecked) return;
        web.evaluateJavascript("(function(){try{return localStorage.getItem('home:unlock')||''}catch(e){return ''}})()", v -> {
            String key = v == null ? "" : v.replace("\"", "").trim();
            if (key.isEmpty() || key.equals("null")) return;
            pushChecked = true;
            PushService.prefs(this).edit().putString("tools_key", key).apply();
            try {
                FirebaseMessaging.getInstance().getToken().addOnSuccessListener(token -> {
                    String done = PushService.prefs(this).getString("registered", "");
                    if (!done.equals(key.substring(0, 8) + token)) PushService.register(this, key, token);
                });
            } catch (Exception ignored) { }
        });
    }

    private String startUrl(Intent i) {
        Uri d = i == null ? null : i.getData();
        return d != null && "boliunew.github.io".equals(d.getHost()) ? d.toString() : HOME;
    }

    private String BuildConfigVersion() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception e) {
            return "1";
        }
    }

    private void openExternal(Uri u) {
        try {
            Intent i = "intent".equals(u.getScheme()) ? Intent.parseUri(u.toString(), Intent.URI_INTENT_SCHEME) : new Intent(Intent.ACTION_VIEW, u);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
        } catch (Exception e) {
            toast("没有能打开这个链接的应用");
        }
    }

    private void toast(String m) { Toast.makeText(this, m, Toast.LENGTH_SHORT).show(); }

    @Override
    protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        if (i != null && i.getData() != null) web.loadUrl(startUrl(i));
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != REQ_FILE || fileCallback == null) return;
        Uri[] result = null;
        if (res == RESULT_OK) {
            if (data != null && data.getClipData() != null) {
                int n = data.getClipData().getItemCount();
                result = new Uri[n];
                for (int k = 0; k < n; k++) result[k] = data.getClipData().getItemAt(k).getUri();
            } else if (data != null && data.getData() != null) {
                result = new Uri[]{data.getData()};
            } else if (cameraUri != null) {
                result = new Uri[]{cameraUri};          // 相机拍的照片写在我们给的地址里
            }
        }
        fileCallback.onReceiveValue(result);
        fileCallback = null;
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] grants) {
        boolean ok = grants.length > 0 && grants[0] == PackageManager.PERMISSION_GRANTED;
        if (req == REQ_MIC && pendingMic != null) {
            if (ok) pendingMic.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            else { pendingMic.deny(); toast("没有麦克风权限，跟读功能用不了"); }
            pendingMic = null;
        } else if (req == REQ_GEO && pendingGeo != null) {
            boolean any = false;
            for (int g : grants) if (g == PackageManager.PERMISSION_GRANTED) any = true;
            pendingGeo.invoke(pendingGeoOrigin, any, false);
            pendingGeo = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    protected void onPause() { super.onPause(); web.onPause(); CookieManager.getInstance().flush(); }

    @Override
    protected void onResume() { super.onResume(); web.onResume(); }
}

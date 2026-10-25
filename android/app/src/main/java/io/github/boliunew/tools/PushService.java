package io.github.boliunew.tools;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Map;

/** 收 Firebase 推送 → 弹通知，点一下在 App 里打开对应页面；推送地址变了就重新登记到 Cloudflare 后端。 */
public class PushService extends FirebaseMessagingService {
    static final String API = "https://tools-api.boliunew.workers.dev";
    static final String CHANNEL = "alerts";

    @Override
    public void onNewToken(String token) {
        prefs(this).edit().putString("fcm_token", token).remove("registered").apply();
        String key = prefs(this).getString("tools_key", "");
        if (!key.isEmpty()) register(this, key, token);
    }

    @Override
    public void onMessageReceived(RemoteMessage m) {
        Map<String, String> d = m.getData();
        String title = d.get("title"), body = d.get("body"), url = d.get("url");
        if ((title == null || title.isEmpty()) && m.getNotification() != null) {
            title = m.getNotification().getTitle();
            body = m.getNotification().getBody();
        }
        show(this, title == null ? "工具箱" : title, body == null ? "" : body, url);
    }

    static SharedPreferences prefs(Context c) { return c.getSharedPreferences("push", MODE_PRIVATE); }

    static void channel(Context c) {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "提醒和推送", NotificationManager.IMPORTANCE_HIGH);
            ch.setDescription("股价提醒、信号日报、每日简报、财报提醒、监控……");
            c.getSystemService(NotificationManager.class).createNotificationChannel(ch);
        }
    }

    static void show(Context c, String title, String body, String url) {
        channel(c);
        Intent open = new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        if (url != null && url.startsWith("https://boliunew.github.io/")) open.setData(Uri.parse(url));
        else if (url != null && url.startsWith("http")) open = new Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        int id = (int) (System.currentTimeMillis() % Integer.MAX_VALUE);
        PendingIntent pi = PendingIntent.getActivity(c, id, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(c, CHANNEL) : new Notification.Builder(c);
        b.setSmallIcon(android.R.drawable.stat_notify_more)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .setContentIntent(pi);
        if (Build.VERSION.SDK_INT < 26) b.setPriority(Notification.PRIORITY_HIGH);
        c.getSystemService(NotificationManager.class).notify(id, b.build());
    }

    /** 把这台手机的推送地址登记到 Cloudflare 后端（用首页密码解锁后的密钥认证）。在后台线程里跑。 */
    static void register(Context c, String key, String token) {
        new Thread(() -> {
            try {
                HttpURLConnection h = (HttpURLConnection) new URL(API + "/push/register").openConnection();
                h.setRequestMethod("POST");
                h.setDoOutput(true);
                h.setConnectTimeout(15000);
                h.setReadTimeout(15000);
                h.setRequestProperty("Content-Type", "application/json");
                h.setRequestProperty("User-Agent", "Mozilla/5.0 ToolsApp");
                h.setRequestProperty("X-Tools-Key", key);
                String body = "{\"token\":\"" + token + "\",\"device\":\"" + (Build.MANUFACTURER + " " + Build.MODEL).replace("\"", "") + "\"}";
                try (OutputStream o = h.getOutputStream()) { o.write(body.getBytes(StandardCharsets.UTF_8)); }
                if (h.getResponseCode() == 200) prefs(c).edit().putString("registered", key.substring(0, 8) + token).apply();
                h.disconnect();
            } catch (Exception ignored) { }
        }).start();
    }
}

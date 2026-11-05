package io.github.boliunew.tools;

import android.app.Activity;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * 🔊 朗读：安卓的 WebView 没有浏览器的 speechSynthesis，网页上的「读音」按钮在 App 里都没声音。
 * 这里用手机自带的朗读引擎（TextToSpeech）补上，再用 POLYFILL_JS 在网页里做一个同样用法的 window.speechSynthesis，
 * 所以英语、西语、葡语、中文各页面的代码不用改。
 */
public class TtsBridge {
    /** 网页一开始就注入（WebView 自己有 speechSynthesis 时什么都不做）。 */
    public static final String POLYFILL_JS = "(function(){\n" +
            "if (window.speechSynthesis || !window.ToolsTTS || window.__ttsPoly) return; window.__ttsPoly = 1;\n" +
            "var N = window.ToolsTTS, Q = {}, seq = 0, L = {}, V = null;\n" +
            "function Utt(t) { this.text = t == null ? '' : String(t); this.lang = ''; this.rate = 1; this.pitch = 1; this.volume = 1; this.voice = null;\n" +
            "  this.onstart = this.onend = this.onerror = this.onboundary = this.onpause = this.onresume = this.onmark = null; }\n" +
            "Utt.prototype.addEventListener = function (t, f) { this['_' + t] = (this['_' + t] || []).concat([f]); };\n" +
            "window.SpeechSynthesisUtterance = Utt;\n" +
            "function voices() {\n" +
            "  if (!V) { try { V = JSON.parse(N.voices() || '[]').map(function (v) { return { name: v.name, lang: v.lang, localService: !!v.local, 'default': false, voiceURI: v.name }; }); } catch (e) { V = []; }\n" +
            "    if (!V.length) { V = null; return []; } }\n" +
            "  return V;\n" +
            "}\n" +
            "var S = { speaking: false, pending: false, paused: false, onvoiceschanged: null, getVoices: voices,\n" +
            "  speak: function (u) { if (!u) return; var id = 'u' + (++seq); Q[id] = u; S.speaking = true;\n" +
            "    N.speak(id, String(u.text || ''), String((u.voice && u.voice.lang) || u.lang || document.documentElement.lang || ''), +u.rate || 1, +u.pitch || 1, String((u.voice && u.voice.name) || '')); },\n" +
            "  cancel: function () { Q = {}; S.speaking = false; N.stop(); },\n" +
            "  pause: function () { }, resume: function () { },\n" +
            "  addEventListener: function (t, f) { (L[t] = L[t] || []).push(f); },\n" +
            "  removeEventListener: function (t, f) { var a = L[t] || [], i = a.indexOf(f); if (i >= 0) a.splice(i, 1); } };\n" +
            "window.speechSynthesis = S;\n" +
            "function fire(o, t, e) { var f = o['on' + t]; try { if (f) f.call(o, e); } catch (x) { setTimeout(function () { throw x; }); }\n" +
            "  (o['_' + t] || []).forEach(function (g) { try { g.call(o, e); } catch (x) { } }); }\n" +
            "window.__ttsEvt = function (id, t) { var u = Q[id]; if (!u) return;\n" +
            "  if (t !== 'start') { delete Q[id]; if (!Object.keys(Q).length) S.speaking = false; }\n" +
            "  fire(u, t, { type: t, utterance: u, charIndex: 0, elapsedTime: 0, error: t === 'error' ? 'synthesis-failed' : undefined }); };\n" +
            "window.__ttsReady = function () { V = null; voices(); var e = { type: 'voiceschanged' };\n" +
            "  try { if (S.onvoiceschanged) S.onvoiceschanged(e); } catch (x) { } (L.voiceschanged || []).forEach(function (f) { try { f(e); } catch (x) { } }); };\n" +
            "if (N.ready()) setTimeout(window.__ttsReady, 0);\n" +
            "})();";

    private final Activity act;
    private final WebView web;
    private final TextToSpeech tts;
    private volatile boolean ready = false;
    private String voicesJson = "[]";
    private final Map<String, Voice> byName = new HashMap<>();
    private final List<Object[]> waiting = new ArrayList<>();
    private final Set<String> warned = new HashSet<>();

    public TtsBridge(Activity act, WebView web) {
        this.act = act;
        this.web = web;
        tts = new TextToSpeech(act.getApplicationContext(), status -> {
            if (status != TextToSpeech.SUCCESS) return;
            buildVoices();
            tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                @Override public void onStart(String id) { js("window.__ttsEvt&&__ttsEvt('" + id + "','start')"); }
                @Override public void onDone(String id) { js("window.__ttsEvt&&__ttsEvt('" + id + "','end')"); }
                @Override public void onError(String id) { js("window.__ttsEvt&&__ttsEvt('" + id + "','error')"); }
                @Override public void onStop(String id, boolean interrupted) { }   // 网页调用 cancel() 时不再回调，和浏览器上的用法一致
            });
            ready = true;
            synchronized (waiting) { for (Object[] w : waiting) doSpeak((String) w[0], (String) w[1], (String) w[2], (Float) w[3], (Float) w[4], (String) w[5]); waiting.clear(); }
            js("window.__ttsReady&&__ttsReady()");
        });
    }

    /** 每种语言只留一个声音（优先不用联网的），列表不至于几百条。 */
    private void buildVoices() {
        JSONArray a = new JSONArray();
        try {
            Set<Voice> vs = tts.getVoices();
            Map<String, Voice> best = new HashMap<>();
            if (vs != null) for (Voice v : vs) {
                if (v.getFeatures() != null && v.getFeatures().contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED)) continue;
                String tag = v.getLocale().toLanguageTag();
                Voice b = best.get(tag);
                if (b == null || (b.isNetworkConnectionRequired() && !v.isNetworkConnectionRequired()) || (b.isNetworkConnectionRequired() == v.isNetworkConnectionRequired() && v.getQuality() > b.getQuality())) best.put(tag, v);
            }
            for (Map.Entry<String, Voice> e : best.entrySet()) {
                Voice v = e.getValue();
                byName.put(v.getName(), v);
                JSONObject o = new JSONObject();
                o.put("name", v.getName());
                o.put("lang", e.getKey());
                o.put("local", !v.isNetworkConnectionRequired());
                a.put(o);
            }
        } catch (Exception ignored) { }
        voicesJson = a.toString();
    }

    @JavascriptInterface public boolean ready() { return ready; }
    @JavascriptInterface public String voices() { return voicesJson; }
    @JavascriptInterface public void stop() { if (ready) tts.stop(); synchronized (waiting) { waiting.clear(); } }

    @JavascriptInterface
    public void speak(String id, String text, String lang, float rate, float pitch, String voiceName) {
        if (!ready) { synchronized (waiting) { waiting.add(new Object[]{id, text, lang, rate, pitch, voiceName}); } return; }
        doSpeak(id, text, lang, rate, pitch, voiceName);
    }

    private void doSpeak(String id, String text, String lang, float rate, float pitch, String voiceName) {
        Voice v = voiceName == null ? null : byName.get(voiceName);
        if (v != null) tts.setVoice(v);
        else if (lang != null && !lang.isEmpty()) {
            Locale loc = Locale.forLanguageTag(lang.replace('_', '-'));
            int r = tts.setLanguage(loc);
            if (r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) {
                r = tts.setLanguage(new Locale(loc.getLanguage()));   // pt-BR 没有就退到 pt
                if ((r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) && warned.add(loc.getLanguage())) {
                    act.runOnUiThread(() -> Toast.makeText(act, "手机没有「" + loc.getDisplayLanguage(Locale.CHINESE) + "」朗读语音：到 设置 → 常规管理 → 文字转语音 里下载", Toast.LENGTH_LONG).show());
                }
            }
        }
        tts.setSpeechRate(Math.max(0.3f, Math.min(rate, 3f)));
        tts.setPitch(Math.max(0.5f, Math.min(pitch, 2f)));
        tts.speak(text, TextToSpeech.QUEUE_ADD, null, id);
    }

    private void js(String code) { web.post(() -> web.evaluateJavascript(code, null)); }

    public void pause() { if (ready) tts.stop(); }
    public void shutdown() { tts.shutdown(); }
}

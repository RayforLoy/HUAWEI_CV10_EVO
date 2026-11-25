package org.cv10.displayprobe;

import android.app.Activity;
import android.app.PendingIntent;
import android.app.Presentation;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbManager;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.hardware.display.DisplayManager;
import android.os.Bundle;
import android.util.Log;
import android.view.Display;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public class Probe extends Activity implements DisplayManager.DisplayListener {
    private DisplayManager manager;
    private LinearLayout panel;
    private Presentation presentation;
    private Pattern pattern;
    private int left = 90, right = 270;
    private static final String USB_ACCESS = "org.cv10.displayprobe.USB_ACCESS";
    private UsbManager usb;
    private String result = "";
    private boolean working;
    private final BroadcastReceiver receiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (USB_ACCESS.equals(intent.getAction())) {
                UsbDevice d = PanelControl.find(usb);
                if (d != null && usb.hasPermission(d)) runWake(d);
                else { result = "未取得 USB 访问权限"; refresh(); }
            } else refresh();
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        manager = getSystemService(DisplayManager.class);
        usb = getSystemService(UsbManager.class);
        IntentFilter filter = new IntentFilter(USB_ACCESS);
        filter.addAction(UsbManager.ACTION_USB_DEVICE_ATTACHED);
        filter.addAction(UsbManager.ACTION_USB_DEVICE_DETACHED);
        if (android.os.Build.VERSION.SDK_INT >= 33)
            registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(receiver, filter);
        ScrollView scroll = new ScrollView(this);
        scroll.setFitsSystemWindows(true);
        panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(panel);
        setContentView(scroll);
        if (state == null && getIntent().getBooleanExtra("request_usb", false))
            scroll.post(this::requestWake);
    }

    @Override public void onStart() {
        super.onStart();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        manager.registerDisplayListener(this, null);
        refresh();
        int id = getIntent().getIntExtra("display_id", -1);
        for (Display d : targets()) {
            if (d.getDisplayId() == id || autoSelect(d)) showPattern(d, 0);
        }
    }

    @Override public void onStop() {
        manager.unregisterDisplayListener(this);
        closePattern();
        super.onStop();
    }

    private Display[] targets() {
        return manager.getDisplays(DisplayManager.DISPLAY_CATEGORY_PRESENTATION);
    }

    private void text(String s) {
        TextView t = new TextView(this);
        t.setText(s);
        panel.addView(t);
    }

    private void button(String s, View.OnClickListener f) {
        Button b = new Button(this);
        b.setText(s);
        b.setOnClickListener(f);
        panel.addView(b);
    }

    private void refresh() {
        panel.removeAllViews();
        if (!working) button("通过 USB 识别 CV10 并开屏", v -> requestWake());
        text(working ? "正在读取 PCUI 应答…" : result);
        Display[] displays = targets();
        if (displays.length == 0) text("等待可用于 Presentation 的外接显示器");
        for (Display d : displays) {
            text(d.getName() + "  #" + d.getDisplayId() + "\n当前 " + label(d.getMode()));
            button("显示左右眼测试图 · 系统默认模式", v -> showPattern(d, 0));
            for (Display.Mode m : d.getSupportedModes()) {
                button("请求 " + label(m), v -> showPattern(d, m.getModeId()));
            }
        }
        if (pattern != null) {
            button("左眼旋转 90°", v -> { left = (left + 90) % 360; pattern.invalidate(); });
            button("右眼旋转 90°", v -> { right = (right + 90) % 360; pattern.invalidate(); });
        }
    }

    private void requestWake() {
        UsbDevice d = PanelControl.find(usb);
        if (d == null) { result = "未发现 12d1:107e，请检查连接"; refresh(); return; }
        if (usb.hasPermission(d)) { runWake(d); return; }
        Intent grant = new Intent(USB_ACCESS).setPackage(getPackageName());
        usb.requestPermission(d, PendingIntent.getBroadcast(this, 0, grant, PendingIntent.FLAG_IMMUTABLE));
    }

    private void runWake(UsbDevice d) {
        if (working) return;
        working = true;
        refresh();
        new Thread(() -> {
            String message;
            try { message = PanelControl.wake(usb, d); }
            catch (Exception e) { message = e.toString(); }
            final String captured = message;
            Log.i("Cv10Probe", captured);
            runOnUiThread(() -> {
                working = false;
                result = captured;
                if (!isDestroyed()) refresh();
            });
        }, "cv10-pcui").start();
    }

    @Override protected void onDestroy() {
        unregisterReceiver(receiver);
        super.onDestroy();
    }

    private String label(Display.Mode m) {
        return m.getPhysicalWidth() + " × " + m.getPhysicalHeight() + " @ " + m.getRefreshRate() + " Hz";
    }

    private void closePattern() {
        if (presentation != null) presentation.dismiss();
        presentation = null;
        pattern = null;
    }

    private void showPattern(Display d, int mode) {
        closePattern();
        presentation = new Presentation(this, d);
        pattern = new Pattern(presentation.getContext());
        presentation.setContentView(pattern);
        WindowManager.LayoutParams attrs = presentation.getWindow().getAttributes();
        attrs.preferredDisplayModeId = mode;
        presentation.getWindow().setAttributes(attrs);
        try {
            presentation.show();
            Log.i("Cv10Probe", "Presentation shown on " + d.getName() + " #" + d.getDisplayId()
                    + ", requested mode ID " + mode + ", reported " + label(d.getMode()));
        } catch (WindowManager.InvalidDisplayException e) {
            Log.w("Cv10Probe", "External display unavailable", e);
            closePattern();
        }
        refresh();
    }

    private boolean autoSelect(Display d) {
        return getIntent().getBooleanExtra("auto_cv10", false)
                && "HUAWEIAV03".equalsIgnoreCase(d.getName().trim());
    }

    public void onDisplayAdded(int id) {
        for (Display d : targets()) {
            if (d.getDisplayId() == id && autoSelect(d)) {
                showPattern(d, 0);
                return;
            }
        }
        refresh();
    }
    public void onDisplayChanged(int id) { refresh(); }
    public void onDisplayRemoved(int id) {
        if (presentation != null && presentation.getDisplay().getDisplayId() == id) closePattern();
        refresh();
    }

    private class Pattern extends View {
        private final Paint ink = new Paint(Paint.ANTI_ALIAS_FLAG);
        Pattern(Context c) { super(c); }
        @Override protected void onDraw(Canvas c) {
            float half = getWidth() / 2f;
            for (int i = 0; i < 2; i++) {
                c.save();
                c.clipRect(i * half, 0, (i + 1) * half, getHeight());
                c.drawColor(i == 0 ? 0xff174275 : 0xff854014);
                c.translate((i + 0.5f) * half, getHeight() / 2f);
                c.rotate(i == 0 ? left : right);
                ink.setColor(0xffffffff);
                ink.setTextAlign(Paint.Align.CENTER);
                ink.setTextSize(Math.min(half, getHeight()) / 3f);
                c.drawText(i == 0 ? "L ↑" : "R ↑", 0, ink.getTextSize() / 3f, ink);
                c.restore();
            }
        }
    }
}

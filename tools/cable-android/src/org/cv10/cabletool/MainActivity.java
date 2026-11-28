package org.cv10.cabletool;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;

public final class MainActivity extends Activity {
    private static final int INK = Color.rgb(27, 39, 45);
    private static final int MUTED = Color.rgb(72, 86, 94);
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Firmware[] images = Firmware.values();
    private final RadioButton[] choices = new RadioButton[images.length];
    private UsbCableHost usb;
    private Vl105 cable;
    private TextView state;
    private TextView current;
    private RadioGroup versions;
    private Button read;
    private Button backup;
    private Button flash;
    private boolean busy;
    private Vl105.Snapshot prepared;
    private String preparedHash;

    private interface Operation<T> {
        T run() throws IOException;
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        usb = new UsbCableHost(this, this::progress);
        cable = new Vl105(usb, this::progress);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(249, 250, 251));
        scroll.setOnApplyWindowInsetsListener((view, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(
                        WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            }
            return insets;
        });
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(22), dp(22), dp(22), dp(22));
        scroll.addView(content);
        setContentView(scroll);

        TextView title = label("CV10 线盒工具", 25, INK);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        content.addView(title);
        addSpaced(content, label("原厂手机连接线 · VL105", 15, MUTED), 4);
        current = label("尚未读取线盒", 16, INK);
        current.setTextIsSelectable(true);
        current.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        addSpaced(content, current, 18);
        read = button(content, "读取线盒", 8, this::readCable);
        backup = button(content, "备份与预检", 2, this::backupCable);

        TextView heading = label("目标固件", 17, INK);
        heading.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        addSpaced(content, heading, 18);
        versions = new RadioGroup(this);
        versions.setOrientation(RadioGroup.VERTICAL);
        for (int i = 0; i < images.length; i++) {
            RadioButton option = new RadioButton(this);
            option.setId(View.generateViewId());
            option.setText(images[i].label);
            option.setTextColor(INK);
            option.setMinHeight(dp(46));
            choices[i] = option;
            versions.addView(option);
        }
        content.addView(versions);
        versions.setOnCheckedChangeListener((group, checked) -> updateButtons());
        flash = button(content, "查看风险并确认刷写", 8, this::confirmFlash);
        state = label("备份与预检通过后可确认刷写。", 15, MUTED);
        state.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        addSpaced(content, state, 10);
        updateButtons();
    }

    private void readCable() {
        prepared = null;
        preparedHash = null;
        current.setText("正在读取线盒...");
        run("正在读取 USB 运行版本...", cable::probe, version -> {
            current.setText("线盒运行版本 " + version);
            progress("可执行备份与预检，识别固件的确切构建。");
        });
    }

    private void backupCable() {
        prepared = null;
        preparedHash = null;
        current.setText("正在备份线盒...");
        run("预检会让线盒短暂重启，可能需要重新授予 USB 权限。",
                () -> cable.backup(this::saveBackup), snapshot -> {
                    prepared = snapshot;
                    preparedHash = Firmware.digest(snapshot.image);
                    current.setText(Firmware.buildLabel(snapshot.image) + "\nSHA-256 " + preparedHash);
                    progress("预检通过。原固件已备份。\n" + snapshot.savedAt);
                });
    }

    private void confirmFlash() {
        Firmware firmware = selected();
        Vl105.Snapshot snapshot = prepared;
        if (firmware == null || snapshot == null || firmware.sha256.equals(preparedHash)) return;
        run("正在验证内置固件...", () -> load(firmware), target -> showFlashDialog(snapshot, firmware, target));
    }

    private void showFlashDialog(Vl105.Snapshot snapshot, Firmware firmware, byte[] target) {
        int changed = Vl105.changedSectors(snapshot.image, target).size();
        LinearLayout detail = new LinearLayout(this);
        detail.setOrientation(LinearLayout.VERTICAL);
        detail.setPadding(dp(22), dp(12), dp(22), dp(4));
        String message = "当前固件  " + Firmware.buildLabel(snapshot.image)
                + "\n目标固件  " + firmware.label
                + "\n目标 SHA-256  " + firmware.sha256
                + "\n预计擦写 " + changed + " 个扇区"
                + "\n\n中途断电、拔线或刷入不兼容镜像可能使线盒无法启动，造成眼镜黑屏。刷写期间请保持接线、供电和本工具在前台。";
        if (firmware == Firmware.PHONE_2A || firmware == Firmware.PIN_C) {
            message += "\n\n满足上游 5 V / 3 A 固定档的协商条件时，固件会向手机发布 5 V / 2 A。充电改善和温升仍需实测。";
        }
        if (firmware == Firmware.PIN_C) {
            message += "\n\n群友修改版仅声明 DP Pin C。主机若无法使用该模式，眼镜可能无画面。";
        }
        if (firmware == Firmware.RT9471_PHONE_2A) {
            message += "\n\n此测试版将 RT9471 输入限流提高到 2.5 A。上游完成 5 V / 3 A 协商后，手机端可公布 5 V / 2 A。实际取电、压降和温升仍需实测。";
        }
        TextView summary = label(message, 15, INK);
        detail.addView(summary);
        CheckBox confirmed = new CheckBox(this);
        confirmed.setText("我已阅读风险，并确认目标固件");
        addSpaced(detail, confirmed, 10);
        ScrollView dialogScroll = new ScrollView(this);
        dialogScroll.addView(detail);
        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("刷写线盒固件")
                .setView(dialogScroll)
                .setNegativeButton("取消", (ignored, action) -> progress("已取消。预检备份仍可用。"))
                .setPositiveButton("开始刷写", (ignored, action) -> flashCable(snapshot, firmware, target))
                .create();
        dialog.setOnCancelListener(ignored -> progress("已取消。预检备份仍可用。"));
        dialog.show();
        Button start = dialog.getButton(AlertDialog.BUTTON_POSITIVE);
        start.setEnabled(false);
        confirmed.setOnCheckedChangeListener((view, checked) -> start.setEnabled(checked));
    }

    private void flashCable(Vl105.Snapshot snapshot, Firmware firmware, byte[] target) {
        prepared = null;
        preparedHash = null;
        current.setText("正在更新线盒...");
        run("正在核对当前镜像与备份...", () -> cable.flash(snapshot, target), sectors -> {
            current.setText(firmware.label + "\nSHA-256 " + firmware.sha256);
            progress("刷写和完整回读均通过。线盒已重新运行。原固件备份位于\n" + snapshot.savedAt);
        });
    }

    private byte[] load(Firmware firmware) throws IOException {
        try (InputStream input = getAssets().open(firmware.asset)) {
            ByteArrayOutputStream buffer = new ByteArrayOutputStream(Firmware.SIZE);
            byte[] chunk = new byte[4096];
            for (int count; (count = input.read(chunk)) != -1;) {
                if (buffer.size() + count > Firmware.SIZE) {
                    throw new IOException("内置镜像长度超过 49,152 字节。");
                }
                buffer.write(chunk, 0, count);
            }
            return firmware.verify(buffer.toByteArray());
        }
    }

    private String saveBackup(byte[] image) throws IOException {
        File directory = getExternalFilesDir("backups");
        if (directory == null || !directory.isDirectory()) {
            directory = new File(getFilesDir(), "backups");
            if (!directory.isDirectory() && !directory.mkdir()) {
                throw new IOException("无法创建线盒备份目录。");
            }
        }
        String prefix = "CV10-" + Firmware.version(image, Firmware.HEADER) + "-"
                + Firmware.digest(image).substring(0, 12) + "-";
        File file = File.createTempFile(prefix, ".bin", directory);
        try (FileOutputStream output = new FileOutputStream(file)) {
            output.write(image);
            output.getFD().sync();
        } catch (IOException failure) {
            if (!file.delete()) Log.w(UsbCableHost.TAG, "Could not remove partial backup", failure);
            throw failure;
        }
        return file.getAbsolutePath();
    }

    private <T> void run(String message, Operation<T> operation, Consumer<T> finished) {
        busy = true;
        updateButtons();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        progress(message);
        worker.execute(() -> {
            try {
                T result = operation.run();
                runOnUiThread(() -> {
                    done();
                    finished.accept(result);
                    updateButtons();
                });
            } catch (IOException | RuntimeException failure) {
                Log.e(UsbCableHost.TAG, "Operation failed", failure);
                runOnUiThread(() -> {
                    done();
                    if (prepared == null) current.setText("当前固件尚待确认");
                    progress(failure.getMessage() == null ? "线盒操作失败。" : failure.getMessage());
                    updateButtons();
                });
            }
        });
    }

    private void done() {
        busy = false;
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    private void progress(String text) {
        Log.i(UsbCableHost.TAG, text);
        runOnUiThread(() -> state.setText(text));
    }

    private Firmware selected() {
        int id = versions.getCheckedRadioButtonId();
        for (int i = 0; i < choices.length; i++) {
            if (choices[i].getId() == id) return images[i];
        }
        return null;
    }

    private void updateButtons() {
        read.setEnabled(!busy);
        backup.setEnabled(!busy);
        for (RadioButton option : choices) option.setEnabled(!busy);
        Firmware firmware = selected();
        flash.setEnabled(!busy && prepared != null && firmware != null && !firmware.sha256.equals(preparedHash));
    }

    private TextView label(String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        return view;
    }

    private Button button(LinearLayout parent, String title, int gap, Runnable action) {
        Button button = new Button(this);
        button.setText(title);
        button.setAllCaps(false);
        button.setOnClickListener(ignored -> action.run());
        addSpaced(parent, button, gap);
        return button;
    }

    private void addSpaced(LinearLayout parent, View child, int gap) {
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, -2);
        layout.topMargin = dp(gap);
        parent.addView(child, layout);
    }

    private int dp(int value) {
        return Math.round(getResources().getDisplayMetrics().density * value);
    }

    @Override public void onBackPressed() {
        if (busy) {
            Toast.makeText(this, "请等待线盒操作结束。", Toast.LENGTH_SHORT).show();
        } else {
            super.onBackPressed();
        }
    }

    @Override protected void onDestroy() {
        worker.shutdown();
        usb.close();
        super.onDestroy();
    }
}

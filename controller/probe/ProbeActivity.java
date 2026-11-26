// SPDX-License-Identifier: GPL-3.0-or-later
package org.cv10.controllerprobe;

import org.freedesktop.monado.openxr_runtime.Cv10ControllerActivity;

public final class ProbeActivity extends Cv10ControllerActivity {
    @Override
    protected boolean probeMode() {
        return true;
    }
}

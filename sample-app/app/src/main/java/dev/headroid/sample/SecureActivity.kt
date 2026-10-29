/*
 * Copyright 2026 Anand S Kale and the headroid contributors
 * SPDX-License-Identifier: Apache-2.0
 */
package dev.headroid.sample

import android.app.Activity
import android.os.Bundle
import android.view.WindowManager

class SecureActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        page("Secure") {
            addView(label(R.id.secure_text, "Secret: 4242 4242 4242 4242", "Secure text"))
        }
        logEvent("secure shown")
    }
}

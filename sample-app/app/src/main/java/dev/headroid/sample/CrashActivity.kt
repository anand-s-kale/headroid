/*
 * Copyright 2026 Anand S Kale and the headroid contributors
 * SPDX-License-Identifier: Apache-2.0
 */
package dev.headroid.sample

import android.app.Activity
import android.os.Bundle

class CrashActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        page("Crash") {
            addView(button(R.id.crash_now, "Crash now").apply {
                setOnClickListener {
                    logEvent("crash")
                    throw IllegalStateException("headroid sample crash")
                }
            })
            addView(button(R.id.anr_now, "Trigger ANR").apply {
                setOnClickListener {
                    logEvent("anr")
                    Thread.sleep(20_000)
                }
            })
        }
    }
}

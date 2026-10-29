/*
 * Copyright 2026 Anand S Kale and the headroid contributors
 * SPDX-License-Identifier: Apache-2.0
 */
package dev.headroid.sample

import android.app.Activity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.widget.TextView
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class TimerActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private val startedElapsed = SystemClock.elapsedRealtime()
    private lateinit var value: TextView

    private val tick = object : Runnable {
        override fun run() {
            val seconds = (SystemClock.elapsedRealtime() - startedElapsed) / 1000
            value.text = seconds.toString()
            if (seconds > 0 && seconds % 10 == 0L) logEvent("timer $seconds")
            handler.postDelayed(this, 1000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        page("Timer") {
            value = label(R.id.timer_value, "0", "Timer seconds")
            val startedAt = SimpleDateFormat("HH:mm:ss", Locale.US).format(Date())
            addView(value)
            addView(label(R.id.timer_started_at, startedAt, "Timer started at"))
        }
        logEvent("timer started")
        handler.post(tick)
    }

    override fun onDestroy() {
        handler.removeCallbacks(tick)
        super.onDestroy()
    }
}

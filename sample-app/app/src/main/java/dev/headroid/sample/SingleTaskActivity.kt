/*
 * Copyright 2026 Anand S Kale and the headroid contributors
 * SPDX-License-Identifier: Apache-2.0
 */
package dev.headroid.sample

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.TextView

/**
 * `launchMode="singleTask"` screen: a second launch reuses the existing task and arrives in [onNewIntent].
 * Used to check whether a launch on another display can reuse or move an existing task of this app.
 */
class SingleTaskActivity : Activity() {
    private var newIntents = 0
    private lateinit var counter: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        page("Single task") {
            addView(label(R.id.single_task_title, "Single task", "Single task title"))
            counter = label(R.id.single_task_new_intents, counterText(), "Single task new intents")
            addView(counter)
        }
        logEvent("single task created")
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        newIntents++
        counter.text = counterText()
        logEvent("single task new intent")
    }

    private fun counterText() = "new intents: $newIntents"
}

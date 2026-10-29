/*
 * Copyright 2026 Anand S Kale and the headroid contributors
 * SPDX-License-Identifier: Apache-2.0
 */
package dev.headroid.sample

import android.app.Activity
import android.text.InputType
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

const val TAG = "HeadroidSample"

fun logEvent(event: String) {
    Log.i(TAG, event)
}

fun <T : View> T.tag(id: Int, description: String): T {
    this.id = id
    this.contentDescription = description
    return this
}

fun Activity.dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

/** Vertical, scrollable page; the content column is passed to [build]. */
fun Activity.page(title: String, build: LinearLayout.() -> Unit): LinearLayout {
    val column = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(16), dp(16), dp(16), dp(16))
    }
    column.addView(TextView(this).apply {
        text = title
        textSize = 22f
    })
    column.build()
    setContentView(ScrollView(this).apply {
        isFillViewport = true
        addView(column, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
    })
    return column
}

fun Activity.button(id: Int, label: String): Button =
    Button(this).apply { text = label }.tag(id, label)

fun Activity.label(id: Int, initial: String, description: String): TextView =
    TextView(this).apply {
        text = initial
        textSize = 16f
        setPadding(0, dp(8), 0, dp(8))
    }.tag(id, description)

fun Activity.field(id: Int, hint: String, inputType: Int = InputType.TYPE_CLASS_TEXT): EditText =
    EditText(this).apply {
        this.hint = hint
        this.inputType = inputType
        if (inputType and InputType.TYPE_TEXT_FLAG_MULTI_LINE == 0) setSingleLine(true)
    }.tag(id, hint)

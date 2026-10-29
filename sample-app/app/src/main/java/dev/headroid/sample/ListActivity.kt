/*
 * Copyright 2026 Anand S Kale and the headroid contributors
 * SPDX-License-Identifier: Apache-2.0
 */
package dev.headroid.sample

import android.app.Activity
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.LinearLayout
import android.widget.ListView

class ListActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val selected = label(R.id.list_selected, "Selected: none", "Selected item").apply {
            setPadding(dp(16), dp(12), dp(16), dp(12))
        }
        val items = (1..200).map { "Item $it" }
        val list = ListView(this).tag(R.id.list_items, "Items")
        list.adapter = ArrayAdapter(this, android.R.layout.simple_list_item_1, items)
        list.setOnItemClickListener { _, _, position, _ ->
            selected.text = "Selected: ${items[position]}"
            logEvent("list selected ${items[position]}")
        }
        root.addView(selected)
        root.addView(list, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        setContentView(root)
    }
}

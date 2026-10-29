/*
 * Copyright 2026 Anand S Kale and the headroid contributors
 * SPDX-License-Identifier: Apache-2.0
 */
package dev.headroid.sample

import android.app.Activity
import android.content.Intent
import android.os.Bundle

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val screens = listOf(
            Triple(R.id.nav_login, "Login", LoginActivity::class.java),
            Triple(R.id.nav_form, "Form", FormActivity::class.java),
            Triple(R.id.nav_list, "List", ListActivity::class.java),
            Triple(R.id.nav_checkout, "Checkout", CheckoutActivity::class.java),
            Triple(R.id.nav_effects, "Effects", EffectsActivity::class.java),
            Triple(R.id.nav_crash, "Crash", CrashActivity::class.java),
            Triple(R.id.nav_secure, "Secure", SecureActivity::class.java),
            Triple(R.id.nav_timer, "Timer", TimerActivity::class.java),
        )
        page("headroid sample") {
            for ((id, name, cls) in screens) {
                addView(button(id, name).apply {
                    setOnClickListener { startActivity(Intent(this@MainActivity, cls)) }
                })
            }
        }
    }
}

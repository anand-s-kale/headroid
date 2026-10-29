/*
 * Copyright 2026 Anand S Kale and the headroid contributors
 * SPDX-License-Identifier: Apache-2.0
 */
package dev.headroid.sample

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.text.InputType
import android.view.View

class LoginActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        page("Login") {
            val email = field(R.id.login_email, "Email", InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS)
            val password = field(R.id.login_password, "Password", InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD)
            val error = label(R.id.login_error, "Invalid email or password", "Login error").apply {
                visibility = View.GONE
            }
            val submit = button(R.id.login_submit, "Sign in")
            submit.setOnClickListener {
                if (email.text.toString().trim() == "demo@headroid.dev" && password.text.toString() == "headroid") {
                    logEvent("login ok")
                    startActivity(Intent(this@LoginActivity, FormActivity::class.java))
                } else {
                    logEvent("login failed")
                    error.visibility = View.VISIBLE
                }
            }
            addView(email)
            addView(password)
            addView(error)
            addView(submit)
        }
    }
}

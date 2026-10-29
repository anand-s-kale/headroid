/*
 * Copyright 2026 Anand S Kale and the headroid contributors
 * SPDX-License-Identifier: Apache-2.0
 */
package dev.headroid.sample

import android.app.Activity
import android.os.Bundle
import android.text.InputType
import android.widget.CheckBox
import android.widget.RadioButton
import android.widget.RadioGroup

class FormActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        page("Form") {
            val name = field(R.id.form_name, "Name", InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_WORDS)
            val phone = field(R.id.form_phone, "Phone", InputType.TYPE_CLASS_PHONE)
            val notes = field(
                R.id.form_notes, "Notes",
                InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE,
            ).apply { minLines = 3 }
            val newsletter = CheckBox(this@FormActivity).apply { text = "Newsletter" }
                .tag(R.id.form_newsletter, "Newsletter")
            val plan = RadioGroup(this@FormActivity).tag(R.id.form_plan, "Plan")
            plan.addView(RadioButton(this@FormActivity).apply { text = "Free" }.tag(R.id.plan_free, "Free plan"))
            plan.addView(RadioButton(this@FormActivity).apply { text = "Pro" }.tag(R.id.plan_pro, "Pro plan"))
            val result = label(R.id.form_result, "", "Form result")
            val submit = button(R.id.form_submit, "Submit")
            submit.setOnClickListener {
                result.text = "Saved: ${name.text}"
                logEvent("form saved newsletter=${newsletter.isChecked}")
            }
            addView(name)
            addView(phone)
            addView(notes)
            addView(newsletter)
            addView(plan)
            addView(submit)
            addView(result)
        }
    }
}

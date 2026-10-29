/*
 * Copyright 2026 Anand S Kale and the headroid contributors
 * SPDX-License-Identifier: Apache-2.0
 */
package dev.headroid.sample

import android.app.Activity
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

class CheckoutActivity : Activity() {
    private var step = 1

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        lateinit var stepLabel: TextView
        lateinit var cart: TextView
        lateinit var address: LinearLayout
        lateinit var addressInput: EditText
        lateinit var pay: TextView
        lateinit var done: TextView
        lateinit var next: Button
        lateinit var back: Button

        fun render() {
            stepLabel.text = "Step $step of 3"
            cart.visibility = if (step == 1) View.VISIBLE else View.GONE
            address.visibility = if (step == 2) View.VISIBLE else View.GONE
            pay.visibility = if (step == 3) View.VISIBLE else View.GONE
            done.visibility = if (step == 4) View.VISIBLE else View.GONE
            val finished = step == 4
            stepLabel.visibility = if (finished) View.GONE else View.VISIBLE
            next.visibility = if (finished) View.GONE else View.VISIBLE
            back.visibility = if (finished) View.GONE else View.VISIBLE
            back.isEnabled = step in 2..3
            next.text = if (step == 3) "Place order" else "Next"
            next.isEnabled = !(step == 2 && addressInput.text.isBlank())
        }

        page("Checkout") {
            stepLabel = label(R.id.checkout_step, "Step 1 of 3", "Checkout step")
            cart = label(R.id.checkout_cart, "Cart: 1 x headroid sticker", "Cart")
            addressInput = field(R.id.checkout_address_input, "Address")
            address = LinearLayout(this@CheckoutActivity).apply {
                orientation = LinearLayout.VERTICAL
                addView(addressInput)
            }.tag(R.id.checkout_address, "Address step")
            pay = label(R.id.checkout_pay, "Pay: cash on delivery", "Payment")
            done = label(R.id.checkout_done, "Order placed", "Order confirmation")
            next = button(R.id.checkout_next, "Next")
            back = button(R.id.checkout_back, "Back")
            addressInput.addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
                override fun afterTextChanged(s: Editable?) = render()
            })
            next.setOnClickListener {
                step++
                if (step == 4) logEvent("checkout placed")
                render()
            }
            back.setOnClickListener {
                step--
                render()
            }
            addView(stepLabel)
            addView(cart)
            addView(address)
            addView(pay)
            addView(done)
            addView(back)
            addView(next)
        }
        render()
    }
}

/*
 * Copyright 2026 Anand S Kale and the headroid contributors
 * SPDX-License-Identifier: Apache-2.0
 */
package dev.headroid.sample

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.pm.PackageManager
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.widget.TextView
import android.widget.Toast

class EffectsActivity : Activity() {
    private lateinit var permissionResult: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        page("Effects") {
            val dialogResult = label(R.id.effects_dialog_result, "", "Dialog result")
            permissionResult = label(R.id.effects_permission_result, "", "Permission result")

            val sound = button(R.id.effects_sound, "Play sound")
            sound.setOnClickListener {
                logEvent("sound")
                val tone = ToneGenerator(AudioManager.STREAM_MUSIC, 80)
                tone.startTone(ToneGenerator.TONE_PROP_BEEP, 300)
                sound.postDelayed({ tone.release() }, 500)
            }

            val vibrate = button(R.id.effects_vibrate, "Vibrate")
            vibrate.setOnClickListener {
                logEvent("vibrate")
                val vibrator = getSystemService(VIBRATOR_SERVICE) as Vibrator
                vibrator.vibrate(VibrationEffect.createOneShot(300, VibrationEffect.DEFAULT_AMPLITUDE))
            }

            val toast = button(R.id.effects_toast, "Show toast")
            toast.setOnClickListener {
                logEvent("toast")
                Toast.makeText(this@EffectsActivity, "Hello from headroid", Toast.LENGTH_SHORT).show()
            }

            val dialog = button(R.id.effects_dialog, "Show dialog")
            dialog.setOnClickListener {
                logEvent("dialog shown")
                AlertDialog.Builder(this@EffectsActivity)
                    .setTitle("Sample dialog")
                    .setMessage("Choose one")
                    .setPositiveButton("OK") { _, _ ->
                        dialogResult.text = "OK"
                        logEvent("dialog ok")
                    }
                    .setNegativeButton("Cancel") { _, _ ->
                        dialogResult.text = "Cancel"
                        logEvent("dialog cancel")
                    }
                    .show()
            }

            val notification = button(R.id.effects_notification, "Post notification")
            notification.setOnClickListener {
                logEvent("notification")
                if (Build.VERSION.SDK_INT >= 33 &&
                    checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
                ) {
                    requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQ_NOTIFICATIONS)
                } else {
                    postNotification()
                }
            }

            val permission = button(R.id.effects_permission, "Request camera permission")
            permission.setOnClickListener {
                logEvent("permission request")
                requestPermissions(arrayOf(Manifest.permission.CAMERA), REQ_CAMERA)
            }

            for (v in listOf(sound, vibrate, toast, dialog, dialogResult, notification, permission, permissionResult)) {
                addView(v)
            }
        }
    }

    private fun postNotification() {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL, "Sample", NotificationManager.IMPORTANCE_DEFAULT),
        )
        val n = Notification.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("headroid sample")
            .setContentText("Hello from headroid")
            .build()
        manager.notify(1, n)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
        if (requestCode == REQ_CAMERA) {
            permissionResult.text = if (granted) "granted" else "denied"
            logEvent("permission camera ${permissionResult.text}")
        } else if (requestCode == REQ_NOTIFICATIONS && granted) {
            postNotification()
        }
    }

    private companion object {
        const val CHANNEL = "sample"
        const val REQ_CAMERA = 1
        const val REQ_NOTIFICATIONS = 2
    }
}

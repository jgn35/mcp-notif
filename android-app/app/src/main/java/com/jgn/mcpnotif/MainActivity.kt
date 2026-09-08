package com.jgn.mcpnotif

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* granted or not: notifications are best-effort in V1 */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        findViewById<Button>(R.id.reenroll).setOnClickListener {
            Enrollment.fetchAndEnroll()
            refreshUi()
        }

        maybeRequestNotificationPermission()
    }

    override fun onResume() {
        super.onResume()
        refreshUi()
    }

    private fun refreshUi() {
        val s = EnrollmentState.snapshot()
        findViewById<TextView>(R.id.status).text = when (s.state) {
            EnrollmentState.State.ENROLLED -> getString(R.string.status_enrolled)
            EnrollmentState.State.ENROLLING -> getString(R.string.enrolling)
            EnrollmentState.State.NOT_ENROLLED -> getString(R.string.status_not_enrolled)
            EnrollmentState.State.ERROR -> getString(R.string.status_error)
        }
        findViewById<TextView>(R.id.endpoint).text =
            "${getString(R.string.endpoint_label)}: ${s.endpoint}"
        findViewById<TextView>(R.id.token).text =
            s.deviceToken?.let { "${getString(R.string.token_label)}: $it" } ?: ""
        findViewById<TextView>(R.id.error).text =
            s.lastError?.let { "${getString(R.string.error_label)}: $it" } ?: ""
    }

    private fun maybeRequestNotificationPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val granted = ContextCompat.checkSelfPermission(
            this, Manifest.permission.POST_NOTIFICATIONS
        ) == PackageManager.PERMISSION_GRANTED
        if (!granted) requestPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
    }
}

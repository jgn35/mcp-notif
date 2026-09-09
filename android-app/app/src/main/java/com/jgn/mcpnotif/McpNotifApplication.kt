package com.jgn.mcpnotif

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build

class McpNotifApplication : Application() {

    override fun onCreate() {
        super.onCreate()
        appContext = this
        createNotificationChannel()
        // Kick off enrollment on first launch. Token rotation is handled by
        // McpNotifMessagingService.onNewToken.
        Enrollment.fetchAndEnroll()
    }

    private fun createNotificationChannel() {
        // Notification channels require API 26+; minSdk is 26, but guard anyway.
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            getString(R.string.channel_id),
            getString(R.string.channel_name),
            NotificationManager.IMPORTANCE_DEFAULT,
        )
        manager.createNotificationChannel(channel)
    }

    companion object {
        lateinit var appContext: Context
            private set
    }
}

package com.jgn.mcpnotif

import android.app.PendingIntent
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class McpNotifMessagingService : FirebaseMessagingService() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    /**
     * Data-only FCM. The server sends {"title","short_message","detailed_message"}.
     * We build the notification here (not from a notification payload) so it is
     * delivered in foreground AND background.
     */
    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        val data = remoteMessage.data
        val title = data["title"]
        val short = data["short_message"]
        // Defensive: ignore messages missing the required keys. The server
        // guarantees them, but the app must not crash on malformed input.
        if (title.isNullOrEmpty() || short.isNullOrEmpty()) return
        val detailed = data["detailed_message"]
        postNotification(title, short, detailed)
    }

    /** Token rotation: re-enroll. Server overwrites the single row. */
    override fun onNewToken(token: String) {
        scope.launch { Enrollment.enrollToken(token) }
    }

    private fun postNotification(title: String, short: String, detailed: String?) {
        val displayDetail = if (detailed.isNullOrEmpty()) short else detailed

        val intent = Intent(this, DetailActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(DetailActivity.EXTRA_TITLE, title)
            putExtra(DetailActivity.EXTRA_DETAILED_MESSAGE, displayDetail)
        }
        val pendingFlags = PendingIntent.FLAG_UPDATE_CURRENT or
            (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M)
                PendingIntent.FLAG_IMMUTABLE else 0)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent, pendingFlags
        )

        val notification = NotificationCompat.Builder(this, getString(R.string.channel_id))
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(short)
            .setStyle(NotificationCompat.BigTextStyle().bigText(short))
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()

        NotificationManagerCompat.from(this).notify(notificationId(), notification)
    }

    /** Unique per message so a new notification does not overwrite a prior one. */
    private fun notificationId(): Int =
        System.currentTimeMillis().toInt()
}

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

    /** Resolved notification content extracted from FCM data keys. */
    data class NotificationContent(val title: String, val shortMessage: String, val detailMessage: String)

    /** Maps NotificationContent fields to their notification/intent destinations. */
    data class NotificationFields(
        val contentTitle: String,
        val contentText: String,
        val bigText: String,
        val detailExtra: String,
        val titleExtra: String,
    )

    companion object {
        /**
         * Pure-Kotlin extraction of notification content from FCM data keys.
         * Static so it can be unit-tested without an Android Context.
         * Returns null if title or short_message is missing/empty (defensive skip).
         * The detail falls back to short_message when detailed_message is absent.
         */
        fun extractContent(data: Map<String, String>): NotificationContent? {
            val title = data["title"]
            val short = data["short_message"]
            if (title.isNullOrEmpty() || short.isNullOrEmpty()) return null
            val detailed = data["detailed_message"]
            val detail = if (detailed.isNullOrEmpty()) short else detailed
            return NotificationContent(title, short, detail)
        }

        /**
         * Maps NotificationContent to the fields used in the notification and
         * detail intent. Pure function so the mapping can be unit-tested without
         * an Android Context.
         */
        fun mapToFields(content: NotificationContent): NotificationFields =
            NotificationFields(
                contentTitle = content.title,
                contentText = content.shortMessage,
                bigText = content.shortMessage,
                detailExtra = content.detailMessage,
                titleExtra = content.title,
            )
    }

    /**
     * Data-only FCM. The server sends {"title","short_message","detailed_message"}.
     * We build the notification here (not from a notification payload) so it is
     * delivered in foreground AND background.
     */
    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        val content = extractContent(remoteMessage.data) ?: return
        postNotification(content)
    }

    /** Token rotation: re-enroll. Server overwrites the single row. */
    override fun onNewToken(token: String) {
        scope.launch { Enrollment.enrollToken(token) }
    }

    private fun postNotification(content: NotificationContent) {
        val fields = mapToFields(content)
        val id = notificationId()
        val intent = Intent(this, DetailActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(DetailActivity.EXTRA_TITLE, fields.titleExtra)
            putExtra(DetailActivity.EXTRA_DETAILED_MESSAGE, fields.detailExtra)
        }
        val pendingFlags = PendingIntent.FLAG_UPDATE_CURRENT or
            (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M)
                PendingIntent.FLAG_IMMUTABLE else 0)
        val pendingIntent = PendingIntent.getActivity(
            this, id, intent, pendingFlags
        )

        val notification = NotificationCompat.Builder(this, getString(R.string.channel_id))
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(fields.contentTitle)
            .setContentText(fields.contentText)
            .setStyle(NotificationCompat.BigTextStyle().bigText(fields.bigText))
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()

        NotificationManagerCompat.from(this).notify(id, notification)
    }

    /** Unique per message so a new notification does not overwrite a prior one. */
    private fun notificationId(): Int =
        System.currentTimeMillis().toInt()
}

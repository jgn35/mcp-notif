package com.jgn.mcpnotif

import android.os.Bundle
import android.text.method.LinkMovementMethod
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import io.noties.markwon.Markwon
import io.noties.markwon.ext.strikethrough.StrikethroughPlugin
import io.noties.markwon.ext.tables.TablePlugin

class DetailActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_detail)

        val title = intent.getStringExtra(EXTRA_TITLE) ?: getString(R.string.app_name)
        val detailed = intent.getStringExtra(EXTRA_DETAILED_MESSAGE).orEmpty()

        findViewById<TextView>(R.id.title).text = title

        val detailView = findViewById<TextView>(R.id.detailed_message)
        markwon.setMarkdown(detailView, detailed)
        detailView.movementMethod = LinkMovementMethod.getInstance()
    }

    companion object {
        private val markwon: Markwon by lazy {
            // Thread-safe singleton — plugins never change between notifications.
            // ApplicationContext is available via McpNotifApplication once the
            // process is alive; lazy init happens on first DetailActivity launch.
            Markwon.builder(McpNotifApplication.appContext)
                .usePlugin(StrikethroughPlugin.create())
                .usePlugin(TablePlugin.create(McpNotifApplication.appContext))
                .build()
        }

        const val EXTRA_TITLE = "com.jgn.mcpnotif.extra.TITLE"
        const val EXTRA_DETAILED_MESSAGE = "com.jgn.mcpnotif.extra.DETAILED_MESSAGE"
    }
}

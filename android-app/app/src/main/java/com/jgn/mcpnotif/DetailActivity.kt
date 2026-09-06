package com.jgn.mcpnotif

import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class DetailActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_detail)

        val title = intent.getStringExtra(EXTRA_TITLE) ?: getString(R.string.app_name)
        val detailed = intent.getStringExtra(EXTRA_DETAILED_MESSAGE).orEmpty()

        findViewById<TextView>(R.id.title).text = title
        findViewById<TextView>(R.id.detailed_message).text = detailed
    }

    companion object {
        const val EXTRA_TITLE = "com.jgn.mcpnotif.extra.TITLE"
        const val EXTRA_DETAILED_MESSAGE = "com.jgn.mcpnotif.extra.DETAILED_MESSAGE"
    }
}

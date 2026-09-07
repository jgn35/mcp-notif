package com.jgn.mcpnotif

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * JVM unit test for [McpNotifMessagingService.extractContent]. Verifies the
 * FCM data-key selection, the detailed_message→short_message fallback, and
 * the defensive skip when required keys are missing. This tests the pure-Kotlin
 * extraction logic without needing Robolectric or an Android Context.
 */
class McpNotifMessagingServiceTest {

    @Test
    fun `extracts all three keys when present`() {
        val content = McpNotifMessagingService.extractContent(mapOf(
            "title" to "Alert Title",
            "short_message" to "Short body text",
            "detailed_message" to "Detailed content here"
        ))

        assertNotNull(content)
        assertEquals("Alert Title", content!!.title)
        assertEquals("Short body text", content.shortMessage)
        assertEquals("Detailed content here", content.detailMessage)
    }

    @Test
    fun `detail falls back to short_message when detailed_message absent`() {
        val content = McpNotifMessagingService.extractContent(mapOf(
            "title" to "T",
            "short_message" to "Short fallback"
        ))

        assertNotNull(content)
        assertEquals("T", content!!.title)
        assertEquals("Short fallback", content.shortMessage)
        assertEquals("Short fallback", content.detailMessage)
    }

    @Test
    fun `detail falls back to short_message when detailed_message empty`() {
        val content = McpNotifMessagingService.extractContent(mapOf(
            "title" to "T",
            "short_message" to "S",
            "detailed_message" to ""
        ))

        assertNotNull(content)
        assertEquals("S", content!!.detailMessage)
    }

    @Test
    fun `returns null when title missing`() {
        val content = McpNotifMessagingService.extractContent(mapOf(
            "short_message" to "S",
            "detailed_message" to "D"
        ))

        assertNull(content)
    }

    @Test
    fun `returns null when short_message missing`() {
        val content = McpNotifMessagingService.extractContent(mapOf(
            "title" to "T",
            "detailed_message" to "D"
        ))

        assertNull(content)
    }

    @Test
    fun `returns null when title empty`() {
        val content = McpNotifMessagingService.extractContent(mapOf(
            "title" to "",
            "short_message" to "S"
        ))

        assertNull(content)
    }

    @Test
    fun `returns null when short_message empty`() {
        val content = McpNotifMessagingService.extractContent(mapOf(
            "title" to "T",
            "short_message" to ""
        ))

        assertNull(content)
    }

    @Test
    fun `ignores unknown data keys`() {
        val content = McpNotifMessagingService.extractContent(mapOf(
            "title" to "T",
            "short_message" to "S",
            "detailed_message" to "D",
            "unknown_key" to "should be ignored",
            "another_unknown" to "also ignored"
        ))

        assertNotNull(content)
        assertEquals("T", content!!.title)
        assertEquals("S", content.shortMessage)
        assertEquals("D", content.detailMessage)
    }

    // --- V3: field-to-display mapping (postNotification contract) ---

    @Test
    fun `mapToFields maps title to contentTitle and titleExtra`() {
        val content = McpNotifMessagingService.NotificationContent("Alert", "Short", "Detailed")
        val fields = McpNotifMessagingService.mapToFields(content)
        assertEquals("Alert", fields.contentTitle)
        assertEquals("Alert", fields.titleExtra)
    }

    @Test
    fun `mapToFields maps shortMessage to contentText and bigText`() {
        val content = McpNotifMessagingService.NotificationContent("Alert", "Short body", "Detailed")
        val fields = McpNotifMessagingService.mapToFields(content)
        assertEquals("Short body", fields.contentText)
        assertEquals("Short body", fields.bigText)
    }

    @Test
    fun `mapToFields maps detailMessage to detailExtra`() {
        val content = McpNotifMessagingService.NotificationContent("Alert", "Short", "Detailed content")
        val fields = McpNotifMessagingService.mapToFields(content)
        assertEquals("Detailed content", fields.detailExtra)
    }

    @Test
    fun `mapToFields maps fallback detail correctly`() {
        val content = McpNotifMessagingService.NotificationContent("T", "Short fallback", "Short fallback")
        val fields = McpNotifMessagingService.mapToFields(content)
        assertEquals("Short fallback", fields.detailExtra)
    }
}

package com.jgn.mcpnotif

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLConnection
import java.net.URLStreamHandler
import java.net.URLStreamHandlerFactory
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * JVM unit test for [EnrollmentClient]. Stubs [HttpURLConnection] via a
 * [URLStreamHandlerFactory] so no real network is needed. Delays in the retry
 * loop are virtualized by [runTest].
 */
class EnrollmentClientTest {

    /**
     * Mock [HttpURLConnection] that captures the request body and headers and
     * returns a configurable response code.
     */
    class StubConn(url: URL) : HttpURLConnection(url) {
        val capturedOutput = ByteArrayOutputStream()

        init {
            attemptCount.incrementAndGet()
            lastConnection.set(this)
        }

        override fun connect() {}
        override fun disconnect() {}
        override fun usingProxy(): Boolean = false
        override fun getOutputStream(): OutputStream = capturedOutput
        override fun getInputStream(): InputStream = ByteArrayInputStream(ByteArray(0))
        override fun getErrorStream(): InputStream? = null

        override fun getResponseCode(): Int {
            if (stubThrowIO.get()) throw IOException("stub network error")
            return stubResponseCode.get()
        }
    }

    companion object {
        private val stubResponseCode = AtomicInteger(200)
        private val stubThrowIO = AtomicReference(false)
        private val attemptCount = AtomicInteger(0)
        private val lastConnection = AtomicReference<StubConn?>(null)

        init {
            // Install once per JVM — URL.setURLStreamHandlerFactory is irreversible.
            try {
                URL.setURLStreamHandlerFactory(object : URLStreamHandlerFactory {
                    override fun createURLStreamHandler(protocol: String): URLStreamHandler? {
                        if (protocol != "https") return null
                        return object : URLStreamHandler() {
                            override fun openConnection(u: URL): URLConnection = StubConn(u)
                        }
                    }
                })
            } catch (e: Error) {
                // Factory already installed (e.g. by another test class); ignore.
            }
        }
    }

    @Before
    fun reset() {
        stubResponseCode.set(200)
        stubThrowIO.set(false)
        attemptCount.set(0)
        lastConnection.set(null)
    }

    // --- V1: enrollment request shape + auth header ---

    @Test
    fun `enroll sends correct body and auth header on 200`() = runTest {
        stubResponseCode.set(200)

        val result = EnrollmentClient.enroll("test-device-token")

        assertTrue(result is EnrollmentClient.Result.Success)
        assertEquals(1, attemptCount.get())

        val conn = lastConnection.get()!!
        val body = String(conn.capturedOutput.toByteArray(), Charsets.UTF_8)
        assertEquals("""{"device_token":"test-device-token"}""", body)
        assertEquals("Bearer ${BuildConfig.ENROLL_TOKEN}", conn.getRequestProperty("Authorization"))
        assertEquals("application/json", conn.getRequestProperty("Content-Type"))
    }

    // --- V2: retry classification ---

    @Test
    fun `401 stops after exactly one attempt`() = runTest {
        stubResponseCode.set(401)

        val result = EnrollmentClient.enroll("token-123")

        assertTrue(result is EnrollmentClient.Result.Failure)
        assertFalse((result as EnrollmentClient.Result.Failure).retryable)
        assertEquals(1, attemptCount.get())
    }

    @Test
    fun `503 retries to MAX_ATTEMPTS then fails as retryable`() = runTest {
        stubResponseCode.set(503)

        val result = EnrollmentClient.enroll("token-123")

        assertTrue(result is EnrollmentClient.Result.Failure)
        assertTrue((result as EnrollmentClient.Result.Failure).retryable)
        assertEquals(5, attemptCount.get())
    }

    @Test
    fun `network error retries to MAX_ATTEMPTS then fails as retryable`() = runTest {
        stubThrowIO.set(true)

        val result = EnrollmentClient.enroll("token-123")

        assertTrue(result is EnrollmentClient.Result.Failure)
        assertTrue((result as EnrollmentClient.Result.Failure).retryable)
        assertEquals(5, attemptCount.get())
    }

    @Test
    fun `400 stops after exactly one attempt`() = runTest {
        stubResponseCode.set(400)

        val result = EnrollmentClient.enroll("token-123")

        assertTrue(result is EnrollmentClient.Result.Failure)
        assertFalse((result as EnrollmentClient.Result.Failure).retryable)
        assertEquals(1, attemptCount.get())
    }
}

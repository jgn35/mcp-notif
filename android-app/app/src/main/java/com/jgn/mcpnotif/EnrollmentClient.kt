package com.jgn.mcpnotif

import java.io.IOException
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * Posts the FCM device token to the MCP server `POST /enroll` endpoint.
 *
 * Contract (from mcp-server/.../enroll.py):
 *   POST /enroll
 *   Authorization: Bearer <ENROLLMENT_TOKEN>
 *   Content-Type: application/json
 *   {"device_token": "<str>"}      -- exactly one key, no extras
 *   200 {"status":"enrolled"} | 401 (bad token) | 400 (bad body)
 */
object EnrollmentClient {

    sealed class Result {
        data object Success : Result()
        data class Failure(val retryable: Boolean, val message: String) : Result()
    }

    private const val MAX_ATTEMPTS = 5

    /** Single attempt. Returns Success or Failure(retryable, ...). */
    private suspend fun enrollOnce(deviceToken: String): Result =
        withContext(Dispatchers.IO) {
            val url = URL(BuildConfig.ENROLL_URL.trimEnd('/') + "/enroll")
            // Use the platform JSON serializer (no extra dependency) for correct
            // escaping of all characters, including control chars below U+0020.
            val body = JSONObject().put("device_token", deviceToken).toString()
            var conn: HttpURLConnection? = null
            try {
                conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = 10_000
                    readTimeout = 10_000
                    setRequestProperty("Authorization", "Bearer ${BuildConfig.ENROLL_TOKEN}")
                    setRequestProperty("Content-Type", "application/json")
                    doOutput = true
                }
                OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(body) }
                val code = conn.responseCode
                when (code) {
                    200 -> Result.Success
                    400, 401, 403, 404 -> Result.Failure(
                        retryable = false,
                        message = "enrollment rejected (HTTP $code)"
                    )
                    in 500..599 -> Result.Failure(
                        retryable = true,
                        message = "server error (HTTP $code)"
                    )
                    else -> Result.Failure(
                        retryable = true,
                        message = "unexpected HTTP $code"
                    )
                }
            } catch (e: IOException) {
                Result.Failure(retryable = true, message = "network error: ${e.message}")
            } finally {
                conn?.disconnect()
            }
        }

    /**
     * Enroll with bounded exponential backoff. Retries transient failures
     * (network, 5xx). Stops immediately on 400/401/403/404 — those are not
     * going to succeed by repeating (bad body, bad/rotated token).
     */
    suspend fun enroll(deviceToken: String): Result {
        var last: Result = Result.Failure(retryable = true, message = "not attempted")
        var backoffMs = 2_000L
        for (attempt in 1..MAX_ATTEMPTS) {
            last = enrollOnce(deviceToken)
            if (last is Result.Success) return last
            if (last is Result.Failure && !last.retryable) return last
            if (attempt < MAX_ATTEMPTS) delay(backoffMs)
            backoffMs = (backoffMs * 2).coerceAtMost(30_000L)
        }
        return last
    }
}

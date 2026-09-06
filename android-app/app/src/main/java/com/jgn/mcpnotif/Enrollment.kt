package com.jgn.mcpnotif

import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Centralized enrollment trigger: fetch the current FCM token and POST it to
 * the MCP server /enroll. Used on first launch, on manual re-enroll, and after
 * token rotation.
 */
object Enrollment {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    /** Fetch token then enroll. Updates [EnrollmentState]. Fire-and-forget. */
    fun fetchAndEnroll() {
        EnrollmentState.setEnrolling()
        // FirebaseMessaging#token is callback-based and dispatches to the main
        // thread on its own; no surrounding coroutine needed.
        FirebaseMessaging.getInstance().token
            .addOnCompleteListener { task ->
                if (!task.isSuccessful || task.result == null) {
                    EnrollmentState.setError(
                        task.exception?.message ?: "token fetch failed"
                    )
                    return@addOnCompleteListener
                }
                scope.launch { enrollToken(task.result) }
            }
    }

    /** Enroll an already-known token (e.g. from onNewToken). Updates state. */
    suspend fun enrollToken(deviceToken: String) {
        EnrollmentState.setEnrolling()
        when (val r = EnrollmentClient.enroll(deviceToken)) {
            is EnrollmentClient.Result.Success -> EnrollmentState.setSuccess()
            is EnrollmentClient.Result.Failure -> EnrollmentState.setError(r.message)
        }
    }
}

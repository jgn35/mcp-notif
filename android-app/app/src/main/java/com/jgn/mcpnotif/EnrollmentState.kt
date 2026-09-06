package com.jgn.mcpnotif

import java.util.concurrent.atomic.AtomicReference

/**
 * In-memory enrollment status, read by [MainActivity]. Volatile enough for a
 * monouser app: the enrollment coroutine writes, the UI reads on resume.
 */
object EnrollmentState {

    enum class State { ENROLLED, NOT_ENROLLED, ENROLLING, ERROR }

    data class Snapshot(
        val state: State,
        val endpoint: String,
        val lastError: String?,
    )

    private val ref = AtomicReference(
        Snapshot(state = State.NOT_ENROLLED, endpoint = BuildConfig.ENROLL_URL, lastError = null)
    )

    fun snapshot(): Snapshot = ref.get()

    fun setEnrolling() {
        ref.updateAndGet { it.copy(state = State.ENROLLING, lastError = null) }
    }

    fun setSuccess() {
        ref.updateAndGet { it.copy(state = State.ENROLLED, lastError = null) }
    }

    fun setError(message: String) {
        ref.updateAndGet { it.copy(state = State.ERROR, lastError = message) }
    }
}

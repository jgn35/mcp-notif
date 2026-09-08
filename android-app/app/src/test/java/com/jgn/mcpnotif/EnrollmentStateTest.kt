package com.jgn.mcpnotif

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test

/**
 * JVM unit tests for [EnrollmentState] — verifies that setSuccess stores the
 * device token, and that setEnrolling/setError clear it.
 */
class EnrollmentStateTest {

    @BeforeEach
    fun reset() {
        EnrollmentState.setError("reset")
    }

    @Test
    fun setSuccess_storesToken_and_setsEnrolledState() {
        EnrollmentState.setSuccess("test-token-123")

        val snapshot = EnrollmentState.snapshot()
        assertEquals(EnrollmentState.State.ENROLLED, snapshot.state)
        assertEquals("test-token-123", snapshot.deviceToken)
        assertNull(snapshot.lastError)
    }

    @Test
    fun setEnrolling_clearsToken_and_lastError() {
        EnrollmentState.setSuccess("old-token")
        EnrollmentState.setEnrolling()

        val snapshot = EnrollmentState.snapshot()
        assertEquals(EnrollmentState.State.ENROLLING, snapshot.state)
        assertNull(snapshot.deviceToken)
        assertNull(snapshot.lastError)
    }

    @Test
    fun setError_clearsToken_and_setsErrorMessage() {
        EnrollmentState.setSuccess("old-token")
        EnrollmentState.setError("enrollment failed")

        val snapshot = EnrollmentState.snapshot()
        assertEquals(EnrollmentState.State.ERROR, snapshot.state)
        assertNull(snapshot.deviceToken)
        assertEquals("enrollment failed", snapshot.lastError)
    }
}

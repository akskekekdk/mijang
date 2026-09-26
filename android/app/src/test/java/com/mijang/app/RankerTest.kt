package com.mijang.app

import org.junit.Assert.assertEquals
import org.junit.Test

class RankerTest {
    private val week = 7L * 24 * 3600
    private val now = 1_800_000_000L
    private val start = now - 261 * week

    private fun series(from: Long, vararg closes: Double) =
        Series(closes.indices.map { from + it * week * (261 / (closes.size - 1)) }, closes.toList())

    @Test
    fun sortsByReturnAndSkipsYoungListings() {
        val result = Ranker.rank(
            mapOf(
                "SLOW" to series(start, 100.0, 150.0),
                "FAST" to series(start, 100.0, Double.NaN, 400.0),
                "NEW" to series(now - 100 * week, 10.0, 100.0),
            ),
            mapOf("FAST" to "빠름"),
            now,
        )
        assertEquals(listOf("FAST", "SLOW"), result.map { it.ticker })
        assertEquals("빠름", result[0].name)
        assertEquals(3.0, result[0].return5y, 1e-9)
    }

    @Test
    fun keepsTopN() {
        val many = (1..30).associate { "T$it" to series(start, 100.0, 100.0 + it) }
        val result = Ranker.rank(many, emptyMap(), now, top = 20)
        assertEquals(20, result.size)
        assertEquals("T30", result.first().ticker)
    }
}
